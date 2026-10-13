#!/usr/bin/env python3
"""Prepare a hash-checked LabOS boot package; does not install or serve it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct


INSTALLER = r'''#!/bin/bash
set -euo pipefail
if [ "$(uname -s)" != Darwin ] || [ "$(id -u)" != 0 ]; then
    echo 'Run in Terminal in LabOS paired Recovery, as root.' >&2
    exit 1
fi
j604_mode=${1:-install}
j604_volume=${2:-/Volumes/LabOS}
j604_dir=$(cd "$(dirname "$0")" && pwd)
case "$j604_mode" in
    install) j604_image="$j604_dir/linux-shell.bin"; j604_sha=@LINUX_SHA@ ;;
    proxy) j604_image="$j604_dir/proxy-fallback.bin"; j604_sha=@PROXY_SHA@ ;;
    *) echo 'Usage: bash install.sh [install|proxy] [LabOS mount point]' >&2; exit 1 ;;
esac
if [ -x "$j604_dir/c10-sha256" ]; then
    j604_actual=$("$j604_dir/c10-sha256" "$j604_image")
elif command -v openssl >/dev/null 2>&1; then
    j604_hash_line=$(openssl dgst -sha256 "$j604_image")
    j604_actual=${j604_hash_line##* }
elif command -v shasum >/dev/null 2>&1; then
    j604_hash_line=$(shasum -a 256 "$j604_image")
    j604_actual=${j604_hash_line%% *}
else
    echo 'No SHA-256 tool is available in this Recovery environment; stopping.' >&2
    exit 1
fi
if [ "$j604_actual" != "$j604_sha" ]; then
    echo 'Payload SHA-256 mismatch; stopping.' >&2
    echo "Expected: $j604_sha" >&2
    echo "Actual:   $j604_actual" >&2
    exit 1
fi
j604_info=$(mktemp /tmp/c10-volume.XXXXXX)
diskutil info -plist "$j604_volume" > "$j604_info"
j604_uuid=$(plutil -extract VolumeUUID raw -o - "$j604_info")
if [ "$j604_uuid" != '46727C64-DC7F-4B50-844E-5E3CC41A2C02' ]; then
    echo "Target UUID $j604_uuid does not match the inventoried LabOS System volume." >&2
    echo "Volume metadata retained at $j604_info. Stopping before configure-boot." >&2
    exit 1
fi
echo "Installing $j604_mode image on $j604_volume ($j604_uuid)"
echo "SHA-256: $j604_sha"
kmutil configure-boot -c "$j604_image" --raw --entry-point 2048 \
    --lowest-virtual-address 0 -v "$j604_volume"
echo 'Boot configuration completed. Shut down, hold Power, then choose LabOS.'
'''


def prepare(manifest_path, output, checksum_helper=None, proxy_fallback=None):
    manifest = json.loads(manifest_path.read_text())
    if proxy_fallback:
        raw = proxy_fallback.read_bytes()
        manifest['proxy_fallback'] = {
            'path': str(proxy_fallback), 'sha256': hashlib.sha256(raw).hexdigest(),
            'bytes': len(raw)}
    inputs = {
        "linux-shell.bin": manifest["combined"],
        "proxy-fallback.bin": manifest.get('proxy_fallback', manifest["m1n1"]),
    }
    for name, record in inputs.items():
        raw = Path(record["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError(f"Changed input: {name}")
    if checksum_helper:
        raw = checksum_helper.read_bytes()
        if struct.unpack_from("<II", raw) != (0xfeedfacf, 0x0100000c):
            raise ValueError("Checksum helper must be a 64-bit ARM64 Mach-O")
        manifest["recovery_checksum_helper"] = {
            "path": str(checksum_helper), "sha256": hashlib.sha256(raw).hexdigest()}
    output.mkdir(parents=True, exist_ok=False)
    for name, record in inputs.items():
        shutil.copyfile(record["path"], output / name)
    if checksum_helper:
        shutil.copyfile(checksum_helper, output / "c10-sha256")
        (output / "c10-sha256").chmod(0o755)
    installer = INSTALLER.replace("@LINUX_SHA@", manifest["combined"]["sha256"]).replace(
        "@PROXY_SHA@", inputs["proxy-fallback.bin"]["sha256"])
    (output / "install.sh").write_text(installer)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    checksums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
                        for path in sorted(output.iterdir()) if path.is_file())
    (output / "SHA256SUMS").write_text(checksums)
    print(f"Prepared {output}; no boot object changed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checksum-helper", type=Path)
    parser.add_argument("--proxy-fallback", type=Path,
                        help="Use a separately proven installed proxy as the recovery image")
    args = parser.parse_args()
    prepare(args.manifest.resolve(), args.output.resolve(), args.checksum_helper,
            args.proxy_fallback.resolve() if args.proxy_fallback else None)
