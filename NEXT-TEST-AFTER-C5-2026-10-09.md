# Next steps after C5 — Oct 9

> **Later Oct 9 update:** the offline Crg8/Cver decode and diagnostic-only
> C6 described below are now complete; see [C6](C6-SESSION-2026-10-09.md)
> and [the full Crg8 analysis](CRG8-ANALYSIS-2026-10-09.md). The remaining
> mailbox-history datum is parked. This file is retained as the after-C5
> plan that led to C6.

**The unchanged C5 repeat is complete.** It again reaches the pager and
fails ANS cold restart. All ten stack addresses match the first C5 run
once normalized by Cver's runtime base. Matching firmware acquisition and
fresh LabOS live identity checks are complete. Next is offline decoding,
then one targeted diagnostic; another unchanged C5 boot adds little.

Read [the repeat result](C5-REPEAT-SESSION-2026-10-09.md),
[its selected transcription](C5-REPEAT-TRANSCRIPTION-2026-10-09.json),
and [firmware provenance](FIRMWARE-INVENTORY-2026-10-09.md).
The first [C5 result](C5-SESSION-2026-10-09.md) and
[C4 comparison](C4-VIDEO-REVIEW-2026-10-09.md) remain historical evidence.

## What is established

- Fresh LabOS's ANS manifest is byte-identical to collected SFR/current.
  Apple's 27.0.1/26A434 ANS container matches its signed ANS digest.
  Live __TEXT differs from the candidate in six startup metadata bytes;
  the investigated instruction bytes match.
- Cver's little-endian word at payload +16 supplies a runtime base of
  `0x184000` in first C5 and `0xc0c000` in the repeat. Subtracting those
  bases gives the same ten Ccst addresses:
  `164f0 d838 8c58 25ce4 3a408 3e8a0 3b370 21ad8 21978 216bc`.
  All nine noninitial values point to call instructions in matching code.
- Both C5 runs identify task 14 (`power`), report low ESR `be000000`,
  FAR `0x49f008000`, and the same low 40-bit address in both packed
  CasC words. The upper l2c_adr bits change between runs.
- Both fail ANSBR 2 with CPU_CONTROL `10`, BOOT_STATUS `0`, no namespace,
  and final Linux error `-62`. The repeat retains 2,587 lines/zero gaps.
- The user reports a complete 26.6.2 restore. Current macOS is 26.6.2,
  LabOS restore files 26.7.1, SFR/current 27.0.1. These facts do not date
  the component changes or establish that a firmware combination causes
  the crash. No reflash was performed during this investigation.

## Next: decode the matched code and record format offline

1. Trace the Crg8 producer and original exception context. At normalized
   `0xd728` firmware reads ESR_EL1 and stores **32 bits** at context +0x338;
   FAR is stored as 64 bits at +0x328. The existing reader has an eight-byte
   prefix and reads a 64-bit ESR at payload +0x340. Verify that relationship
   before assigning meaning to the changing upper ESR word. The reported
   PC is inside a reporting wrapper, so it is not evidence of the original
   faulting access. Find the preserved interrupted context if one exists.
2. Trace the callback chain around normalized `0x25ce4`, `0x3a408`,
   `0x3e8a0`, and `0x3b370`. Establish its objects and address mappings
   from code/data, rather than nearby strings or the task name alone.
3. Decode CasC's packed address/status and translate `0x49f008000` through
   the firmware's mappings. The captured ADT contains no direct register
   range covering that value. Do not equate a firmware VA, IOVA, or packed
   word with AP physical MMIO. Asynchronous SError and FAR alone do not
   identify one access or prove a missing clock/power domain.

Keep raw values, normalized offsets, disassembly, and confidence together.
C4's runtime base is still unknown; its raw PC cannot yet support a
normalized cross-run comparison. The initial zero-slide disassembly is
superseded by `C5-normalized-stack.txt` in the candidate artifact directory.

## If the existing capture leaves the context ambiguous

Prepare one **diagnostic-only C6**, separately named and hashed, to expose
fields the current decoder may hide:

- Dump the complete bounded Crg8 payload (expected 0x350 bytes) and Cver
  payload (expected 0x90 bytes), preserving section lengths and raw bytes.
  Keep safe truncation checks; do not add firmware/MMIO reads.
- Print the Cver runtime-base candidate explicitly alongside raw data.
  Retain the full reported ESR while distinguishing its low 32 bits.
- Correct the bounded CLHE footer recognition before ordinary section-size
  validation, and verify it offline against captured/truncated fixtures.
  This corrects log interpretation; it is not an ANS restart fix.

Do not build/send C6 merely to reproduce the known outcome: first specify
which missing context field will settle the code-path or format question.
Keep stage1 behavior, firmware, DTB, init and reset/mailbox behavior fixed.
At the time of this after-C5 plan, C6 had **not** yet been built or sent;
it was later built and sent on Oct 9 (see the update at the top of this file).

## Then: one measured path change

If the address resolves to a peripheral, compare its existing PMGR,
clock/reset state across shutdown and Linux restart, using cached state or
reads after reset deassertion. If it resolves to shared RAM/DMA, compare
SART entries and buffer lifetimes at the first relevant divergence.
No ANS MMIO reads while reset is asserted: those caused C/C2's wedge.

Choose one functional change only after the identified path supports it.
Compare against C5 and recheck the working tethered control after a driver
behavior change. Pass requires a namespace, 4Kn logical block size,
**500,277,792,768-byte** capacity, GPT signature, and matching repeated
block reads. Absence of a timeout alone is insufficient.

## Desktop track

The [original roadmap](REVIEW-2026-10-07.md#roadmap-to-a-graphical-desktop)
remains applicable: use the proven tethered boot for a normal userspace and
framebuffer desktop while fixing cold ANS restart. Verify current partition
layout before installing rootfs. Then validate a compatible Gravity kernel
and Mesa GPU combination; the new GPU branches are a separate integration
track and do not resolve this storage failure by themselves.
