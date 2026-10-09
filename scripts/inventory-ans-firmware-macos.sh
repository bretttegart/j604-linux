#!/bin/bash
# Run on macOS. Read boot metadata; write reports only under Downloads.
set -eu
if [ "$(uname -s)" != Darwin ]; then
    echo 'Run this inventory on the Mac in macOS.' >&2
    exit 1
fi
j604_inventory="$HOME/Downloads/j604-firmware-inventory-$(date +%Y%m%dT%H%M%S)"
mkdir "$j604_inventory"
sw_vers > "$j604_inventory/sw-vers.txt"
diskutil apfs list > "$j604_inventory/apfs-list.txt"
mount > "$j604_inventory/mounts.txt"
ioreg -p IODeviceTree -n chosen -r -l -w 0 > "$j604_inventory/chosen-ioreg.txt"
echo 'Reading boot firmware paths with sudo; no boot files are changed.'
sudo -v
: > "$j604_inventory/firmware-paths.txt"
: > "$j604_inventory/find-errors.txt"
: > "$j604_inventory/scan-status.txt"
for j604_search_root in /System/Volumes/iSCPreboot /System/Volumes/Preboot; do
    if [ -d "$j604_search_root" ]; then
        if sudo find -H "$j604_search_root" \
            \( -name .TemporaryItems -o -name .Trashes -o -name .Spotlight-V100 \) -prune -o \
            -type f \( \
            -iname '*ans*.im4p' -o -iname '*ans*.img4' -o \
            -iname '*ans*.bin' -o -name BuildManifest.plist -o \
            -name RestoreVersion.plist -o -name SystemVersion.plist \
        \) >> "$j604_inventory/firmware-paths.txt" \
            2>> "$j604_inventory/find-errors.txt"; then
            echo "complete: $j604_search_root" >> "$j604_inventory/scan-status.txt"
        else
            echo "partial (see find-errors.txt): $j604_search_root" >> "$j604_inventory/scan-status.txt"
        fi
    fi
done
echo "Inventory: $j604_inventory"
echo 'Copy this report directory to Fedora. Review paths to identify LabOS and system firmware before copying candidate images.'
