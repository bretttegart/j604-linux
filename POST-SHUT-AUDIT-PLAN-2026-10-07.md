# Next test after SHUT-AUDIT — 2026-10-07

> **Superseded after C/C2/C3:** The mid-reset MMIO snapshots in this original
> plan caused a boot wedge. C3 removes them and reaches the pager. Continue
> with [the C4 session](C4-SESSION-2026-10-09.md): C4 restored the bounded
> crashlog content dump and reaches the pager. The
> [video review](C4-VIDEO-REVIEW-2026-10-09.md) exposes an SError plus
> additional structured sections; [C5](C5-SESSION-2026-10-09.md) decoded them
> and reproduced the failure in task 14 (`power`). Continue with the
> [post-C5 plan](NEXT-TEST-AFTER-C5-2026-10-09.md). Six tail payloads were captured in still photos;
> they are not a complete unknown-section inventory.
> No ANS register reads are valid here while reset
> remains asserted.

## Decision

The ANS shutdown handed off in a measured clean state, and stage2 A still
crashed in two SHUT-AUDIT runs. Do not change the handoff power state yet.
The next useful test is a **diagnostic kernel A rebuild that reveals the
unknown firmware crashlog sections and prints the Linux reset sequence**.
Keep behavior, stage1, DTB, and initramfs fixed. This should show where
firmware first objects and whether reset/mailbox setup differs from the
successful stage1 shutdown.

Muse's proposed IOP OFF experiment is not the next test. Linux defines
RTKit IOP OFF (`0x00`) as “power off, cannot be restarted”; it defines SLEEP
(`0x01`) as restartable. T8132 Linux already tried an explicit INIT after
CPU RUN on cold startup and still timed out. Asking the firmware to go OFF
could destroy the state needed for the next stage. That does not prove OFF
can never be recovered by a full hardware reset, but the current evidence
does not justify taking that risk.

## Evidence from the completed audit

- The repeated tethered control passes with the same kernel A, current m1n1,
  DTB, and common init.
- The stage1 audit made no Linux outcome change in two runs. It read the
  existing 7,614,162-byte stage2 A from the ESP; its full SHA-256 is
  `e0acf3db6ad6b2eea4c8668a270d5fb76b13c2081a80a7050a5e19e20ae3746a`.
- m1n1 received the AP QUIESCED and IOP SLEEP acknowledgements, stopped the
  CPU, pulsed the active 0.ANS reset, and then freed its RTKit/SART/ASC and
  queue allocations. The missing ANS2 name is an expected alias miss.
- Linux's T8132 DT sets `ps_ans` as an always-on domain and as the NVMe reset.
  The PMGR reset provider asserts device-disable and reset, then clears both
  on deassert. Linux performs this assert, reinitializes its RTKit mailbox and
  frees old RTKit buffers, deasserts reset, sets CPU RUN, then waits for
  firmware. Kernel B adds INIT after CPU RUN. Both chain variants fail after
  endpoint-map completion while waiting for the IOP power ACK.
- The kernel crashlog parser knows `Cstr`, `Cver`, `Cmbx`, `Ctim`, and
  `Crg8`; it only prints the fourcc for unknown sections such as the reported
  `Cnvr` and `Csta`. It already copies the received crashlog to a shadow
  buffer before parsing. The missing evidence may therefore be recoverable
  with a bounded parser diagnostic; no firmware-state change is needed to
  try to read it.

The m1n1 and Linux reset sequences look structurally similar, but exact
timing, register values across Linux reset, and firmware-visible buffer
ownership have not been compared. Do not claim reset equivalence or infer
the crash cause from the final timeout.

## Muse test: CRASHLOG-DIAG-A

Build kernel A with **diagnostics only**. Preserve the current Asahi source,
the A kernel configuration, and all existing functional patches. Do not
apply kernel B's explicit-INIT change.

Add guarded logging to the RTKit crashlog parser and ANS cold-start path:

1. Before reading any section header, verify that the header and 16-byte
   section header fit inside the declared crashlog size. Reject malformed
   lengths rather than reading past the shadow buffer.
2. For unknown sections, print the fourcc, offset, and validated payload
   length. Print contiguous printable ASCII strings of at least four bytes
   from the payload, with offsets. Also emit the full payload in bounded
   hex rows if its length is at most 4096 bytes; otherwise emit the first
   and last 256 bytes and clearly record the omitted length. Keep the full
   in-memory crashlog unchanged. This may expose an assertion, internal
   message, or raw state useful for later decoding; do not label the section
   based only on its fourcc.
3. Around the cold path in `drivers/nvme/host/apple.c`, log CPU_CONTROL and
   BOOT_STATUS immediately before reset assert, after successful reset
   deassert, and after CPU RUN. **Do not read ANS MMIO between reset assert
   and successful deassert: C/C2 wedged on those reads and C3 removed them.**
   If a reset/reinit operation fails, log its return code without reading
   the disabled block. Include
   each return code and a monotonic timestamp or elapsed delta. Log the INIT
   send return and the first RTKit crash notification in the same chronology.
   Do not add delays or alter reset, power, mailbox, buffer, or SART behavior.

Create an isolated kernel C build and a newly named stage2, using the same
stage2 m1n1 prefix as stage2 A, the unchanged DTB and common initramfs, and
bootargs label `j604.test=CRASHLOG-DIAG-A`. Use the same stage1 audit binary
and existing LINUXESP path from a fresh LabOS proxy. Verify component hashes
and record the exact source diff and config. Do not overwrite the existing
stage2 A or any installed boot object.

Run once first. Film the Mac display continuously through shutdown and the
full Linux pager. Preserve all pages around RTKDIAG startup and the crashlog,
especially the first crash notification, unknown-section output, reset
snapshots, and final summary. Record the host command status separately from
the Mac result. If the diagnostic build changes the result, repeat the
unchanged audit A control before interpreting the change.

## How to choose the following experiment

- **Crashlog includes a readable assertion or fault address:** decode that
  evidence and make one corresponding kernel fix, retaining kernel A as
  the control.
- **Crashlog contains structured binary only:** preserve the emitted bytes
  and offsets. Decode the format offline from the captured data before
  making another hardware change.
- **No crash notification payload arrives or the shadow buffer is empty:**
  capture mailbox message order and crash-buffer allocation/IOVA lifecycle.
  Keep this distinct from the IOP power-state timeout.
- **Linux reset state diverges from expectations:** investigate only the
  first observed difference, with no simultaneous IOP power-state change.
- **Diagnostics are identical and no assertion is exposed:** next compare
  SART mappings and buffer addresses/lifetimes across stage1 and kernel,
  then design one narrow change from those measurements.

Leave the BASE-0 anomaly deferred while both current tethered controls pass.
Keep the long-term desktop work on its separate track in
[the review roadmap](REVIEW-2026-10-07.md#roadmap-to-a-graphical-desktop).
