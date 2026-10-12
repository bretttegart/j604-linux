#!/usr/bin/env python3
"""Build the static C9 verifier and a checked, deterministic newc initramfs."""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import struct
import subprocess


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(CGO_ENABLED="0", GOOS="linux", GOARCH="arm64")
    binary = output / "init"
    subprocess.run(["go", "build", "-trimpath", "-ldflags=-s -w", "-o", str(binary),
                    str(root / "init/c9_status.go"), str(root / "init/c9_runtime.go")], env=env, check=True)
    blob = binary.read_bytes()
    if blob[:5] != b"\x7fELF\x02" or struct.unpack_from("<H", blob, 18)[0] != 183:
        raise ValueError("Expected ARM64 ELF")
    archive = bytearray()

    def add(name, data, mode, ino):
        encoded = name.encode() + b"\0"
        fields = [ino, mode, 0, 0, 2 if mode == 0o40755 else 1, 0, len(data), 0, 0, 0, 0, len(encoded), 0]
        archive.extend(b"070701" + b"".join(f"{n:08x}".encode() for n in fields))
        archive.extend(encoded)
        archive.extend(b"\0" * (-len(archive) % 4))
        archive.extend(data)
        archive.extend(b"\0" * (-len(archive) % 4))

    for ino, name in enumerate(("dev", "proc", "sys", "run"), 1):
        add(name, b"", 0o40755, ino)
    add("init", blob, 0o100755, 5)
    add("TRAILER!!!", b"", 0, 6)
    compressed = gzip.compress(archive, mtime=0)
    path = output / "initramfs.cpio.gz"
    path.write_bytes(compressed)
    raw = gzip.decompress(path.read_bytes())
    position = 0
    decoded = {}
    while position < len(raw):
        if raw[position:position+6] != b"070701":
            raise ValueError("Invalid newc magic")
        fields = [int(raw[position+6+8*i:position+14+8*i], 16) for i in range(13)]
        end = position + 110 + fields[11]
        name = raw[position+110:end-1].decode()
        position = (end + 3) & ~3
        data = raw[position:position+fields[6]]
        position = (position + fields[6] + 3) & ~3
        decoded[name] = data
    if set(decoded) != {"dev", "proc", "sys", "run", "init", "TRAILER!!!"} or decoded["init"] != blob:
        raise ValueError("Archive verification failed")
    print(f"Verified ARM64 init/newc: {len(blob)} bytes; gzip {len(compressed)} bytes; SHA-256 {hashlib.sha256(compressed).hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output.resolve())
