# C11 — pause before embedded Linux — 2026-10-12

C10 boots a working shell through RAM chainload but its installed image loops
at the Apple logo without visible m1n1/Linux output. Restoring the preserved
standalone proxy succeeds, confirmed by the operator and USB metadata capture.
C11 adds a proxy pause before the embedded payload scanner, allowing inspection
of an installed image before a host command resumes Linux.

Artifacts: `/home/btega/j604-boot/ans-review-n6miVhGq/C11-PAUSE-20261012/`.
Results: [C11-PAUSE-RESULTS-2026-10-12.json](C11-PAUSE-RESULTS-2026-10-12.json).

## Changes and controls

The disposable C9 local source copy receives
[c10-to-c11-pause.patch](diagnostics/m1n1-c11/c10-to-c11-pause.patch).
After normal startup, `run_actions` initializes USB and prints
`C11 PRE-PAYLOAD HOLD`. It runs the proxy until `P_EXIT`, then continues the
unchanged payload scanner. A volatile phase marker distinguishes hold, resume,
and successful scanner return. The build tag is `C11-PREPAYLOAD-PAUSE`.

Build: `M1N1_VERSION_TAG=C11-PREPAYLOAD-PAUSE make -j8 USE_CLANG=1
CHAINLOADING=1 EXTRA_CFLAGS=-DNO_DISPLAY`. The raw image ends at `0x3c0000`,
matching both `_end` and `_payload_start`; entry offset remains `0x800`.

The entire C10 appended region is copied unchanged, including kernel, DTB,
initramfs, command line and terminator. Total file size stays 8,140,659 bytes.
The Linux screen therefore still labels itself C10-SHELL.

| Artifact | SHA-256 |
|---|---|
| C11 raw m1n1 | `bcfdeebd8851d4a559031daca2e13a462145b1bcc6f203982f06e1cf7a85206b` |
| C11 raw ELF | `3674caae896d31b60718804d50060fd6c701dd6126db00b58825f227dfb27bfd` |
| Combined paused image | `29ae9055603e21222e0b9785773c8c2984c055941d3b6bce7cd5b7fd0f468404` |
| Appended region, 4,208,499 bytes | `e4290ea8424bdacc3fb615d8469d43bdeaf850e180d04ff89d77d145a4c5f2ba` |

This pause changes USB state and RAM allocations before scanning the payload.
It is a diagnostic path; success does not establish that the unchanged C10
installed image works, nor does a host-resumed boot establish untethered boot.

## RAM proxy test

1. Chainload the complete C11 image with `chainload.py -n -r` from the restored
   installed proxy. Host exit 0, `Proxy is alive again`, expected C11 hold.
2. [inspect-c11-pause.py](scripts/inspect-c11-pause.py) reads the phase marker,
   bootargs, startup vectors and the entire appended region without importing
   `m1n1.setup` or `ProxyUtils`. All appended bytes and vectors match the host
   image. Marker stays at the hold value. No ANS commands are issued.
3. A second verified inspection sends `P_EXIT`. The USB log records the resume
   marker, then the transport disconnects. The operator and camera confirm
   a Linux `j604#` shell, read-only setup YES, and four historical block matches.

Raw readback and JSON are in `proxy-test/inspection` and `proxy-test/resume`.
Startup log is `proxy-test/chainload.log`. Shell evidence is
`proxy-test/shell-result.jpg`, with its hash recorded in the result JSON.
Photographs are panel evidence, not byte-verified transcripts.

## Historical hash mismatch

The unchanged verifier reports `hash mismatch LBA 4096`. Its old reference
block, preserved as `C9-PREP-20261012/F-RUN/first-lba-004096.bin`, contains
dated Oct 5 Boot Picker/StorageKit log text. The captured GPT places LBA 4096
inside `iBootSystemContainer`, spanning LBA 6 through 128005. This is a mutable
reference across Recovery sessions, not a suitable immutable test sector.

The operator runs `for i in 1 2 3; do ans-check | grep '4096'; done` and confirms
all three current hashes are identical. Each invocation opens the namespace
O_RDONLY|O_DIRECT and reads page-aligned 4 KiB buffers. Each reaches LBA 4096
after matching the other four historical hashes. The current block contents
were not captured byte-for-byte; an exact new reference hash is not adopted.
Record shell PASS and stable repeated reads, with historical comparison 4/5.
Do not recast the original 5/5 checker result as a current 5/5 PASS.

## Installed test — failed

Package served at `http://192.168.0.11:8765/c11-pause.tar.gz`, SHA-256
`d267bedc0b529a48d4b1830c3339d1f890b824a2e07608f1add58e3fcabb01d6`.
It includes the native macOS checksum helper and the now-proven preserved
standalone proxy (`dfdb3bfa…`) as its fallback. The package builder accepts
`--proxy-fallback` to keep recovery separate from the experimental prefix.

Both install and proxy modes invoke the expected raw configure-boot arguments
in mocked Recovery checks. Wrong volume UUID and wrong payload hash prevent
configure-boot. The served archive matches the host archive. The installer
still pins LabOS System UUID `46727C64-DC7F-4B50-844E-5E3CC41A2C02`.

In LabOS paired macOS Recovery Terminal:

```sh
curl -f http://192.168.0.11:8765/c11-pause.tar.gz -o /tmp/c11.tar.gz
tar -xzf /tmp/c11.tar.gz -C /tmp
bash /tmp/c11-pause/install.sh install /Volumes/LabOS
```

Shut down, keep USB-C connected, hold Power and choose LabOS. Expected:
`C11 PRE-PAYLOAD HOLD`. The operator instead reports another bootloop with
no other text. No `/dev/m1n1` is present at the host check. The hold is not
observed; the exact failure point is unestablished. The operator has returned
to paired Recovery. If a future diagnostic reaches the hold,
inspect the complete image before resuming. If it loops before the hold, the
failure is before payload scanning in this diagnostic; it does not identify
an exact instruction or establish an ANS fault.

Recovery uses the same archive with
`bash /tmp/c11-pause/install.sh proxy /Volumes/LabOS`; download/extract again
if Recovery has cleared `/tmp`.


## Next comparison: C12 preserved proxy at the same file size

[C12 size control](C12-SIZE-SESSION-2026-10-12.md) keeps the exact working
standalone proxy executable prefix and appends zero padding plus an ignored
end marker to reach C11's file size. This isolates larger installed-image
size from the C9/C11 prefix and embedded Linux data. The operator reports that C12 also bootloops. The larger installed-image
size/loading/layout change reproduces failure with the known executable
prefix and no Linux payload. An exact firmware defect or size threshold
is not identified. Work stopped at the user’s request after C12.
