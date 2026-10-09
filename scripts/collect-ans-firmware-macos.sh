#!/bin/bash
# J604 installed-firmware collection. Run as your normal user in macOS.
# Reads boot volumes; mounts the inventoried LabOS Preboot read-only if needed.
# Copies selected firmware/manifest files into Downloads; never installs them.
set -eu
if [ "$(uname -s)" != Darwin ]; then
    echo 'Run this collector on the Mac in macOS.' >&2
    exit 1
fi
j604_uuid=F759066A-59CD-4808-BF39-2BBD8BBF07D6
j604_bundle="$HOME/Downloads/j604-firmware-collection-$(date +%Y%m%dT%H%M%S)"
mkdir "$j604_bundle"
echo "Collection: $j604_bundle"
sw_vers > "$j604_bundle/sw-vers.txt"
diskutil apfs list > "$j604_bundle/apfs-list.txt"
diskutil apfs list -plist > "$j604_bundle/apfs-list.plist"
ioreg -p IODeviceTree -n chosen -r -l -w 0 > "$j604_bundle/chosen-ioreg.txt"
diskutil info -plist "$j604_uuid" > "$j604_bundle/labos-preboot-before.plist"
j604_actual_uuid=$(plutil -extract VolumeUUID raw -o - "$j604_bundle/labos-preboot-before.plist")
if [ "$j604_actual_uuid" != "$j604_uuid" ]; then
    echo 'LabOS Preboot UUID did not match; stopping before mounting.' >&2
    exit 1
fi
j604_device=$(plutil -extract DeviceIdentifier raw -o - "$j604_bundle/labos-preboot-before.plist")
if j604_lab_mount=$(plutil -extract MountPoint raw -o - "$j604_bundle/labos-preboot-before.plist" 2>/dev/null); then
    :
else
    j604_lab_mount=''
fi
j604_mounted_here=0
cleanup() {
    if [ "$j604_mounted_here" = 1 ]; then
        if sudo diskutil unmount "$j604_device" >> "$j604_bundle/mount-actions.txt" 2>&1; then
            rmdir "$j604_bundle/labos-preboot-readonly" || true
        else
            echo "Could not unmount $j604_device; see mount-actions.txt." >&2
        fi
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
sudo -v
if [ -z "$j604_lab_mount" ]; then
    j604_lab_mount="$j604_bundle/labos-preboot-readonly"
    mkdir "$j604_lab_mount"
    sudo diskutil mount readOnly -mountPoint "$j604_lab_mount" "$j604_device" \
        > "$j604_bundle/mount-actions.txt" 2>&1
    j604_mounted_here=1
    diskutil info -plist "$j604_device" > "$j604_bundle/labos-preboot-mounted.plist"
    j604_verified_mount=$(plutil -extract MountPoint raw -o - "$j604_bundle/labos-preboot-mounted.plist")
    if [ "$j604_verified_mount" != "$j604_lab_mount" ]; then
        echo 'Unexpected mount point; stopping collection.' >&2
        exit 1
    fi
else
    echo "Using already-mounted LabOS Preboot: $j604_lab_mount" > "$j604_bundle/mount-actions.txt"
fi
mount > "$j604_bundle/mounts.txt"
: > "$j604_bundle/errors.txt"
: > "$j604_bundle/scan-status.txt"
: > "$j604_bundle/copied-files.tsv"
: > "$j604_bundle/SHA256SUMS"
j604_index=0
j604_copied=0
for j604_root in /System/Volumes/iSCPreboot /System/Volumes/iSCPreboot/SFR/current \
    /System/Volumes/Preboot "$j604_lab_mount"; do
    j604_index=$((j604_index + 1))
    if [ ! -d "$j604_root" ]; then
        echo "missing: $j604_root" >> "$j604_bundle/scan-status.txt"
        continue
    fi
    echo "Scanning $j604_root"
    j604_label="root-$j604_index"
    printf '%s\t%s\n' "$j604_label" "$j604_root" >> "$j604_bundle/roots.tsv"
    if sudo find -H "$j604_root" \
        \( -name .TemporaryItems -o -name .Trashes -o -name .Spotlight-V100 \) -prune -o \
        -type f -print0 > "$j604_bundle/$j604_label.paths.nul" 2>> "$j604_bundle/errors.txt"; then
        echo "complete: $j604_root" >> "$j604_bundle/scan-status.txt"
    else
        echo "partial (see errors.txt): $j604_root" >> "$j604_bundle/scan-status.txt"
    fi
    tr '\000' '\n' < "$j604_bundle/$j604_label.paths.nul" > "$j604_bundle/$j604_label.paths.txt"
    while IFS= read -r -d '' j604_file; do
        j604_name=${j604_file##*/}
        j604_lower=$(printf '%s' "$j604_name" | tr '[:upper:]' '[:lower:]')
        j604_select=0
        case "$j604_lower" in
            *ans*.im4p|*ans*.img4|*ans*.bin|ans|ansf|rans|ans.*|ansf.*|rans.*|\
            *applestoragefirmware*|*ans*firmware*|\
            buildmanifest.plist|restoreversion.plist|systemversion.plist|\
            apticket.der|*.im4m|*manifest*.der|*manifest*.img4|*manifest*.plist)
                j604_select=1 ;;
        esac
        if [ "$j604_select" = 0 ]; then
            case "$j604_file" in
                *.im4p|*.img4|*.bin|*.der|*/SFR/*|*/firmware/*|*/Firmware/*)
                    # IMG4/IM4P type and description are normally in the first 512 bytes.
                    # grep -a handles binary input without developer tools or strings.
                    if sudo head -c 512 "$j604_file" 2>> "$j604_bundle/errors.txt" | \
                        LC_ALL=C /usr/bin/grep -a -q -e ansf -e rans -e AppleStorageFirmware \
                            2>> "$j604_bundle/errors.txt"; then
                        j604_select=1
                    fi ;;
            esac
        fi
        [ "$j604_select" = 1 ] || continue
        j604_bytes=$(sudo stat -f %z "$j604_file" 2>> "$j604_bundle/errors.txt" || true)
        case "$j604_bytes" in
            ''|*[!0-9]*)
                printf 'size unavailable: %s\n' "$j604_file" >> "$j604_bundle/errors.txt"
                continue ;;
        esac
        if [ "$j604_bytes" -gt 67108864 ]; then
            printf 'selected file over 64 MiB, path retained only: %s\n' "$j604_file" >> "$j604_bundle/errors.txt"
            continue
        fi
        j604_relative=${j604_file#"$j604_root"/}
        j604_dest="$j604_bundle/files/$j604_label/$j604_relative"
        mkdir -p "${j604_dest%/*}"
        # Shell opens the destination as the normal user; sudo only reads the source.
        if sudo cat "$j604_file" > "$j604_dest" 2>> "$j604_bundle/errors.txt"; then
            j604_copied=$((j604_copied + 1))
            printf '%s\t%s\t%s\n' "$j604_file" "${j604_dest#"$j604_bundle"/}" "$j604_bytes" \
                >> "$j604_bundle/copied-files.tsv"
            (cd "$j604_bundle" && shasum -a 256 "${j604_dest#"$j604_bundle"/}") >> "$j604_bundle/SHA256SUMS"
        else
            rm -f "$j604_dest"
            printf 'copy failed: %s\n' "$j604_file" >> "$j604_bundle/errors.txt"
        fi
    done < "$j604_bundle/$j604_label.paths.nul"
done
printf 'selected files copied: %s\n' "$j604_copied" >> "$j604_bundle/scan-status.txt"
echo "Copied $j604_copied selected files. Review scan-status.txt and errors.txt for coverage."
echo "Copy $j604_bundle back to Fedora Downloads for analysis."
