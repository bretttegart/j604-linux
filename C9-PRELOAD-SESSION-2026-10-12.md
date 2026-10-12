# C9 Linux RAM-preload comparison — Oct 12, 2026

**L0 PASS; L1 FAIL with cold ANS crash, reset `-62`, no namespace.** This extends the
[completed m1n1 U/F restart tests](C9-RESTART-SESSION-2026-10-12.md).
The comparison keeps the C8 kernel and DTB unchanged and replaces the
pager init with a bounded, fixed-screen direct-read verifier.

Directory: `/home/btega/j604-boot/ans-review-n6miVhGq/C9-L-PREP-20261012/`.
Nothing was copied onto the ESP or installed/blessed. No internal partition
is mounted and no SSD write command is issued.

## Reporting and preparation

After the owner asked about viewing the camera feed, the Nikon was checked
and used to capture the single fixed result panel. Full pager/long-video
capture remains parked. The first frame on opening the Nikon UVC stream
was cached; discarding the first 60 input frames produced the live panel.
One settled frame is sufficient to read the ten large status lines.
Do not interpret the first startup frame as the current Mac display.

For L1 the Nikon battery was exhausted. The owner connected a Logitech
HD Pro Webcam C920 (`046d:08e5`) and rebooted to a fresh LabOS proxy.
The webcam was verified before handoff; bounded 1920×1080 MJPEG stills
with 60 startup frames discarded clearly show the complete result panel.
This changes the external reporting camera, not any boot component.

The native Linux kernel still has USB/gadget support disabled. These
camera frames are the Linux result evidence; the USB proxy carries only
pre-handoff loader/diagnostic evidence. A raw Linux kernel log has not been
exported to Fedora by this method.

[`init/c9_status.go`](init/c9_status.go) waits for the namespace, checks a
4096-byte logical block size, opens it **read-only with O_DIRECT**, uses
an anonymous page-aligned buffer, and reads LBAs 0, 1, 2, 128 and 4096.
Every read must return 4096 bytes and match the saved C9 U/F SHA-256.
There is no buffered-read fallback. Kernel messages are summarized with
explicit ANS device attribution; MTP cannot set the ANS crash/branch fields.
The init paints one layout indefinitely; no reboot or pager is included.
Its JSON output lives only on tmpfs, not the SSD.

Native host checks passed actual O_DIRECT fixture reads, detected a modified
block and cancelled work, and verified MTP/ANS attribution and kmsg gaps.
The stripped static ARM64 init compiled. Its newc/gzip archive was decoded
offline and verified to contain the exact built init and required directories.
The framebuffer renderer derives geometry from fbdev and checks its bounds.

| Component | Bytes | SHA-256 |
|---|---:|---|
| C8 Image.gz | 2944930 | `f17f1c9c835af2f130c0371188f33a97e68d45463bafd7d08dca6d47bd074e0f` |
| Original common DTB | 35374 | `d7091e7449a92d8ca62d6c4613cff8fe0ae86451d4e81af52c5eb56e1d84dc01` |
| Fixed-screen initramfs | 858052 | `9202d830a7765987a6a09cf5fadfeb749f3dc97feb23238e87e6550d04cda32e` |
| Temporary local m1n1 | 3932160 | `8497c947355557e4dacbc9bc70226ec68894424f6a65b3e2214e3d977165fbcf` |

The m1n1 image is the same observed local image used for F. It retains
the CTRR_C/D reservations and C9 mailbox/SART hooks. No kernel source,
reset sequence, endpoint or power request was changed for this comparison.
The new init changes console presentation/timing; it is matched between
L0 and L1, rather than asserted equivalent to the historical pager init.

## Matched loader

[`run-c9-preload.py`](scripts/run-c9-preload.py) performs the standard
component loading, SMP startup, DT preparation, gzip decompression and
cache maintenance before any optional m1n1 storage cycle. It records the
prepared DTB, addresses and reservations. The actual FDT pointer is read
from the pinned raw ELF's `dt` symbol in normal DRAM, with pointer/magic/
size checks. This adds no device MMIO probe.

Both cells allocate the same dummy aligned read buffer. L0 issues no m1n1
NVMe init/read/shutdown. L1 issued exactly one init/read/shutdown and
no second m1n1 initialization. Queue/RTKit buffer intervals are checked
against the preloaded components. Complete kernel/initramfs/prepared-DTB
readbacks are hashed before and after the optional cycle. Handoff is
stopped if an input changes, allocations overlap, shutdown is not proven,
or the observed warm/cold CPU state contradicts the cell.

The kernel command lines differ only in `j604.test=C9-L0` / `C9-L1`;
the same m1n1, kernel, input DTB and initramfs are used. Dynamic FDT
fields and physical addresses can differ across fresh iBoot sessions and
are recorded; they are not presumed identical across sessions.

## L0 — completed

One m1n1 send and one Linux handoff, Oct 12 around 12:16 MDT.
Pre-handoff RUN=`0x10`, BOOT_STATUS=`0xde71ce55`. The C9 trace contains
**zero INIT_BEGIN events**, proving that this temporary m1n1 instance did
not perform an NVMe session. All payload readbacks match the host inputs
and remain unchanged through the no-storage control window.

The settled camera frame reports:

| Field | Observed |
|---|---|
| Cell / result | C9 L0 / PASS |
| Direct reads | MATCH 5 OF 5 |
| Namespace | YES |
| ANS branch | 3 (warm wake) |
| ANS crash / reset error | NO / NONE |
| Boot ID prefix | `eb10f668` |
| Phase / error | READS MATCH / NONE |

Primary frame: `L0-RUN/status-settled.jpg`, SHA-256
`4bcd54e3c123adad79573091dec9748b1861333c46104f193cddcd4be2f43a4f`.
`L0-RUN/linux-result.json` is a manual transcription checked directly
against that frame, not an OCR inference.

An initial **host-only classification bug** labeled this handoff rejected:
the Python `kboot_boot()` wrapper discards its request's return, so the
caller got `None` and incorrectly compared it to zero. The wrapper's
request completed without exception, the proxy disappeared as expected,
and the live camera proves Linux PASS. No repeat send occurred. The original
host result remains in `host-result-original.json`, with a correction in
`host-result.json`. The loader now requests the exact boot opcode directly
to retain the reply value. Neither a host status nor a successful upload
alone establishes the Linux outcome.

## L1 — completed

One temporary m1n1 send and one Linux handoff, Oct 12 at 12:55 MDT,
after a fresh LabOS reboot. All four boot component hashes match L0;
the fresh ANS manifest is byte-identical to L0's capture. m1n1 read all
five expected blocks successfully, then completed one normal shutdown.
There was no second m1n1 initialization.

The trace has 223 events and ten SART snapshot records, with zero drops
and no m1n1 ANS crash. Actual AP QUIESCED and IOP SLEEP ACKs precede
successful internal sleep-switch completion, CPU RUN clear, and the
resolved ANS PMGR reset. The unresolved ANS2 alias returns `-1`; its
snapshot is explicitly skipped (status 2), not evidence of zeroed slots.
SART entries remain identical across sleep and the resolved reset.
RTKit release removes slots 5, 7 and 8; all protected slots
0–4 and 6 (`0x5f`) retain their complete values.

Kernel, initramfs and prepared-DTB readback hashes are unchanged across
the cycle. Queue and RTKit buffers do not overlap the preloaded payloads.
Pre-handoff CPU_CONTROL=`0x0`, BOOT_STATUS=`0x0`. The boot request
acknowledges with integer zero; Linux outcome comes from the camera.

| Field | Observed |
|---|---|
| Cell / result | C9 L1 / FAIL |
| Direct reads | MATCH 0 OF 5; no Linux reads attempted without namespace |
| Namespace | NO |
| ANS branch | 2 (cold reset/boot) |
| ANS crash / reset error | YES / `-62` |
| Boot ID prefix | `4e688ed5` |
| Phase / error | NO NAMESPACE / NO NVME |

The early frames report WAIT while already showing the ANS crash and
reset error. The final frame, after the namespace deadline, reports FAIL.
Primary frame: `L1-RUN/status-final.jpg`, SHA-256
`d67f562c23c587c807d45ce7ba14b234ed9da0e36943635939f4d6ee49d77010`.
`L1-RUN/linux-result.json` is a manual transcription checked against this
frame. `evidence-analysis.json` records the offline trace/hash checks.
The [machine summary](C9-PRELOAD-RESULTS-2026-10-12.json) includes both
cells and evidence hashes; raw blocks and camera images remain local.

## Interpretation and next discriminator

L0 validates the new preload layout/reporting path and actual Linux direct
I/O without prior m1n1 storage use. L1 reproduces the cold ANS failure
after one proven m1n1 init/read/shutdown cycle, with the Linux payload
already in RAM and verified unchanged. FAT loading and stage2 relocation
are therefore unnecessary to reproduce this failure. This supports
investigating Linux's cold restart and the firmware-visible handoff state;
it does not identify a specific faulty operation or establish that all
chain-specific factors are irrelevant. The kernel still lacks digital
USB log export, so this run does not provide a raw Linux crash log.

One additional observation from U/F is preserved for possible follow-up:
their first and second init reused the exact same three RTKit buffer
physical intervals. Their PASS results therefore do not yet test a restart
that relocates those buffers. This is a capture fact, not proof of a stale
buffer defect. An address-changing m1n1 restart would be a useful later
discriminator now that L1 fails. The subsequent
[FR cell passed](C9-RELOCATE-SESSION-2026-10-12.md) with all three buffers
at new, non-overlapping intervals; the measured m1n1 restart does not need
exact address reuse. The next selected comparison is a grouped Linux
RTKit/EP7 parity screen, with a warm control before its cold test.
