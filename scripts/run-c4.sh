#!/usr/bin/env bash
# Launch exactly one C4 SSD-chain test from the Fedora host terminal.
set -euo pipefail

j604_run_root=/home/btega/j604-boot/ans-review-n6miVhGq
j604_payload="$j604_run_root/C4/stage1-shut-audit-cd4.bin"
j604_proxy=/home/btega/bootloader/proxyclient
j604_device=/dev/m1n1

if [[ ! -e "$j604_device" ]]; then
    echo "No /dev/m1n1. Run this in the Fedora host terminal with the Mac at a fresh LabOS proxy." >&2
    exit 1
fi
if command -v fuser >/dev/null && fuser -s "$j604_device"; then
    echo "/dev/m1n1 is already in use. Close the other serial client before this test." >&2
    exit 1
fi
if [[ ! -r "$j604_device" || ! -w "$j604_device" ]]; then
    echo "The current user cannot read/write /dev/m1n1." >&2
    exit 1
fi

cd "$j604_run_root/C4"
sha256sum -c SHA256SUMS
j604_evidence="$j604_run_root/C4-RUN-$(date +%Y%m%dT%H%M%S%z)"
mkdir "$j604_evidence"
cp manifest.json "$j604_evidence/"
printf '%s\n' "$j604_evidence" > "$j604_run_root/C4/LAST_RUN.txt"
date --iso-8601=seconds > "$j604_evidence/start.txt"
printf '%s\n' 'ESP stage2 SHA-256 confirmed by operator: f72fba61ccdf6bc9d1420cc5f478956e03c95189af1ba1665349443c0e5b7855' > "$j604_evidence/staging.txt"

echo "One C4 upload; evidence: $j604_evidence"
echo "Capture the Mac pager label, boot ID, six unknown-section headers and all hex rows."
echo "USB reconnection failure after Linux handoff is a host status; read the Mac display for the result."
cd "$j604_proxy"
set +e
script -q -e -c "env M1N1DEVICE=/dev/m1n1 timeout 120 $j604_proxy/venv/bin/python $j604_proxy/tools/chainload.py -n -r $j604_payload" "$j604_evidence/chainload.log"
j604_host_status=$?
set -e
printf '%s\n' "$j604_host_status" > "$j604_evidence/host-exit-status.txt"
date --iso-8601=seconds > "$j604_evidence/host-command-end.txt"
echo "Host exit status: $j604_host_status. Evidence saved: $j604_evidence"
echo "Allow roughly 100 seconds from upload for the pager. Capture Cnvr/Csta bytes and the exact final parser message."
exit "$j604_host_status"
