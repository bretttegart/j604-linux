# C12 — preserved proxy at the failed image size — 2026-10-12

**Installed result: FAIL, operator reports another bootloop.** This image
contains the exact proxy executable that previously booted from LabOS, with
padding to the C10/C11 file size. It contains no Linux payload or C9/C11
diagnostic changes. The user requested that work stop after this result.

Artifacts: `/home/btega/j604-boot/ans-review-n6miVhGq/C12-SIZE-20261012/`.
Results: [C12-SIZE-RESULTS-2026-10-12.json](C12-SIZE-RESULTS-2026-10-12.json).

## Construction and control

The 3,866,624-byte preserved `m1n1-pre-ctrr.bin` is byte-identical to the
surviving Oct 3 `m1n1-upstream/build/m1n1.bin`. It successfully restored the
installed proxy after C10: the operator confirmed it, and a read-only USB
capture confirmed `v2.0.0-dirty` and `Running proxy`.

C12 appends 4,273,971 zero bytes and a 64-byte end marker, giving exactly
8,140,659 bytes, the C10/C11 installed-image length. Its entire executable
prefix is unchanged. The original payload scanner stops at the first zero
word at offset `0x3b0000`; the marker is beyond that terminator and is not
executed. The marker would permit checking that the full larger image was
loaded if the proxy became available.

| Artifact | SHA-256 |
|---|---|
| Working smaller proxy | `dfdb3bfa56e7f5266f0e4c3c1fa27a61c03d2ec921e7771ae1aabaf7dce23dfd` |
| Padded proxy, 8,140,659 bytes | `d7fa57f0ae498ced7e6b56df20c24d1bab5c433c4eb41ebfa5ea23dc11354ee6` |
| Recovery/install archive | `b3d8231e0c6daeb3f9d5aa76f355d984529b4531a092c4bfdae7c174e6a378dc` |

The marker is the following string, padded to 64 bytes with NUL:
`J604 C12 SIZE CONTROL: preserved proxy; unexecuted end marker.` followed
by a newline. The zero padding starts immediately after the preserved file.
The marker starts at file offset 8,140,595. Exact offsets and marker bytes
are recorded in the local manifest and result JSON.

## Installation and evidence

The package is `C10-EMBED-20261012/serve/c12-size.tar.gz` and contains
`probe.bin`, the known smaller `proxy-fallback.bin`, the native ARM64 macOS
checksum helper, guarded `install.sh`, a manifest and checksums. Its `padded`
mode selects the larger control; `proxy` selects the proven smaller image.
Both use raw entry offset 2048 and lowest virtual address 0, targeting only
LabOS System UUID `46727C64-DC7F-4B50-844E-5E3CC41A2C02`.

Host checks verify the executable prefix, zero terminator, padding, marker,
total file size and package checksums. Bash syntax and mocked Recovery
checks pass: both modes select the expected file and configure-boot arguments;
wrong image hash or wrong volume UUID prevents configure-boot. The served
archive matches the host archive byte-for-byte.

The operator installs `padded` mode from paired macOS Recovery, reboots, and
reports **“Bootloop again.”** No working proxy or installed image readback
was obtained. This verdict is an operator report, not a captured exception
or verified firmware panic. The exact stage and cause are unestablished.

[inspect-c12-size.py](scripts/inspect-c12-size.py) was prepared to read the
startup vectors and complete padding/marker over USB without issuing boot,
power, or ANS commands. It passes Python syntax validation but was **not run
against hardware**, because the installed proxy did not become available.

## Interpretation and limits

The known smaller proxy succeeds, while its padded counterpart fails.
The larger installed image/loading/layout change can reproduce a bootloop
with the known executable prefix, without Linux or the C9 diagnostic code.
This establishes a boot-path blocker separate from the measured ANS sleep
failure. It does not identify a universal image-size limit, a threshold,
an iBoot defect, the exact faulting instruction, or the state of ANS.

No new firmware restore or storage-driver change follows from this evidence.
On resumption, restore the known smaller proxy first, preserve its metadata,
and investigate the loading/layout difference with a bounded comparison.
Do not present the C10/C11 proxy shell passes as installed-boot success.

## Recovery and stopping state

The last attempted LabOS boot object is the **failing padded C12 proxy**.
The smaller proxy has not been restored after C12; the user stopped testing.
Testing stopped here at the user's request.

Recovery instructions are preserved for later use. In LabOS's paired macOS
Recovery Terminal, with the Fedora package server available:

```sh
curl -f http://192.168.0.11:8765/c12-size.tar.gz -o /tmp/c12.tar.gz
tar -xzf /tmp/c12.tar.gz -C /tmp
bash /tmp/c12-size/install.sh proxy /Volumes/LabOS
```

The package server was left available for recovery, serving only
`/home/btega/j604-boot/ans-review-n6miVhGq/C10-EMBED-20261012/serve` on
`192.168.0.11:8765`. Do not assume it survives a Fedora restart. The standalone
`proxy-restore.tar.gz` package is another preserved route to the same smaller
image. No repartitioning or Linux root filesystem installation was performed.
