#!/usr/bin/env python3
"""Build a deterministic shell initramfs from checked static ARM64 tools."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile


def build(busybox, verifier, output, font_source=None):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    blobs = {"bin/busybox": busybox.read_bytes(), "bin/ans-check.bin": verifier.read_bytes()}
    for name, blob in blobs.items():
        if blob[:5] != b"\x7fELF\x02" or struct.unpack_from("<H", blob, 18)[0] != 183:
            raise ValueError(f"Not ARM64 ELF: {name}")
        source = busybox if name == "bin/busybox" else verifier
        if "INTERP" in subprocess.check_output(["readelf", "-l", str(source)], text=True):
            raise ValueError(f"Dynamic interpreter required: {name}")
    subprocess.run(["qemu-aarch64-static", str(busybox), "sh", "-n",
                    str(root / "init/c10_shell.sh")], check=True)
    applets = set(subprocess.check_output(
        ["qemu-aarch64-static", str(busybox), "--list"], text=True).splitlines())
    required = {"sh", "setsid", "mount", "blockdev", "sha256sum", "dmesg", "stty"}
    if font_source:
        required.add("setfont")
    if not required <= applets:
        raise ValueError(f"Missing BusyBox applets: {required - applets}")
    with tempfile.TemporaryDirectory(prefix="c10-applets-") as directory:
        subprocess.run(["qemu-aarch64-static", str(busybox), "--install", "-s", directory], check=True)
    archive = bytearray()
    entries = {}

    def add(name, data, mode):
        encoded = name.encode() + b"\0"
        fields = [len(entries) + 1, mode, 0, 0, 2 if mode == 0o40755 else 1,
                  0, len(data), 0, 0, 0, 0, len(encoded), 0]
        archive.extend(b"070701" + b"".join(f"{n:08x}".encode() for n in fields))
        archive.extend(encoded)
        archive.extend(b"\0" * (-len(archive) % 4))
        archive.extend(data)
        archive.extend(b"\0" * (-len(archive) % 4))
        entries[name] = data

    for name in ("bin", "dev", "proc", "sys", "run", "root", "etc", "tmp"):
        add(name, b"", 0o40755)
    for name, blob in blobs.items():
        add(name, blob, 0o100755)
    add("bin/sh", b"busybox", 0o120777)
    add("bin/ans-check", b"#!/bin/sh\nexec /bin/ans-check.bin --verify\n", 0o100755)
    add("init", (root / "init/c10_shell.sh").read_bytes(), 0o100755)
    if font_source:
        # Double the kernel's VGA 8x16 bitmap into a 16x32 PSF2 font.
        text = re.sub(r"/\*.*?\*/", "", font_source.read_text(), flags=re.S)
        bitmap = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})\b", text))
        if len(bitmap) != 4096:
            raise ValueError("Expected the kernel's 256-glyph VGA 8x16 font")
        scaled = bytearray()
        for row in bitmap:
            wide = 0
            for bit in range(7, -1, -1):
                wide = (wide << 2) | (3 if row & (1 << bit) else 0)
            scaled.extend(wide.to_bytes(2, "big") * 2)
        font = struct.pack("<8I", 0x864ab572, 0, 32, 0, 256, 64, 32, 16) + scaled
        add("etc/console.psf", font, 0o100644)
    add("TRAILER!!!", b"", 0)
    compressed = gzip.compress(archive, mtime=0)
    path = output / "initramfs.cpio.gz"
    path.write_bytes(compressed)
    raw = gzip.decompress(compressed)
    position = 0
    decoded = {}
    while position < len(raw):
        if raw[position:position + 6] != b"070701":
            raise ValueError("Invalid newc magic")
        fields = [int(raw[position + 6 + 8*i:position + 14 + 8*i], 16) for i in range(13)]
        end = position + 110 + fields[11]
        name = raw[position + 110:end - 1].decode()
        position = (end + 3) & ~3
        decoded[name] = raw[position:position + fields[6]]
        position = (position + fields[6] + 3) & ~3
    if decoded != entries:
        raise ValueError("Archive readback mismatch")
    manifest = {
        "busybox": {"path": str(busybox), "sha256": hashlib.sha256(blobs["bin/busybox"]).hexdigest()},
        "verifier": {"path": str(verifier), "sha256": hashlib.sha256(blobs["bin/ans-check.bin"]).hexdigest()},
        "init_script_sha256": hashlib.sha256(entries["init"]).hexdigest(),
        "font_source": str(font_source) if font_source else None,
        "initramfs": {"path": str(path), "bytes": len(compressed),
                      "sha256": hashlib.sha256(compressed).hexdigest()},
        "validation": "ARM64/static ELF checks; newc entries byte-exact after gzip readback",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--busybox", type=Path, required=True)
    parser.add_argument("--verifier", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font-source", type=Path)
    args = parser.parse_args()
    build(args.busybox.resolve(), args.verifier.resolve(), args.output.resolve(), args.font_source)
