#!/bin/bash
set -euo pipefail
[ "$(uname -s)" = Darwin ] && [ "$(id -u)" = 0 ] || { echo 'Run in paired macOS Recovery Terminal as root.' >&2; exit 1; }
j604_dir=$(cd "$(dirname "$0")" && pwd)
j604_volume=${1:-/Volumes/LabOS}
j604_actual=$("$j604_dir/c10-sha256" "$j604_dir/proxy.bin")
[ "$j604_actual" = 'dfdb3bfa56e7f5266f0e4c3c1fa27a61c03d2ec921e7771ae1aabaf7dce23dfd' ] || { echo 'Proxy hash mismatch; stopping.' >&2; exit 1; }
j604_info=$(mktemp /tmp/j604-restore.XXXXXX)
diskutil info -plist "$j604_volume" > "$j604_info"
j604_uuid=$(plutil -extract VolumeUUID raw -o - "$j604_info")
[ "$j604_uuid" = '46727C64-DC7F-4B50-844E-5E3CC41A2C02' ] || { echo "Wrong target volume: $j604_uuid; stopping." >&2; exit 1; }
echo "Restoring standalone v2.0.0-dirty proxy on $j604_volume"
echo "SHA-256: $j604_actual"
kmutil configure-boot -c "$j604_dir/proxy.bin" --raw --entry-point 2048 --lowest-virtual-address 0 -v "$j604_volume"
echo 'Proxy boot configuration completed. Shut down, hold Power, and choose LabOS.'
