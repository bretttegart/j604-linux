#!/usr/bin/env python3
"""Prepare a hash-checked LabOS boot package; does not install or serve it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


INSTALLER = r'''#!/bin/bash
set -eu
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
j604_actual=$(shasum -a 256 "$j604_image" | awk '{print $1}')
if [ "$j604_actual" != "$j604_sha" ]; then
    echo 'Payload SHA-256 mismatch; stopping.' >&2
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


def prepare(manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    inputs = {
        "linux-shell.bin": manifest["combined"],
        "proxy-fallback.bin": manifest["m1n1"],
    }
    for name, record in inputs.items():
        raw = Path(record["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError(f"Changed input: {name}")
    output.mkdir(parents=True, exist_ok=False)
    for name, record in inputs.items():
        shutil.copyfile(record["path"], output / name)
    installer = INSTALLER.replace("@LINUX_SHA@", manifest["combined"]["sha256"]).replace(
        "@PROXY_SHA@", manifest["m1n1"]["sha256"])
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
    args = parser.parse_args()
    prepare(args.manifest.resolve(), args.output.resolve())
