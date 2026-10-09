# C4 video review — Oct 9

**The firmware reports an asynchronous SError before the IOP ACK timeout.**
Reset deassertion succeeds and CPU RUN is set. The six Cnvr/Csta records
captured in the still photos are only the tail of the crashlog: the video
also reveals Ccst, CasC, and Crtk records. The next boot is
[C5](C5-SESSION-2026-10-09.md), a parser diagnostic that makes these records
and the version/footer bytes easier to capture. No firmware-state fix is
justified yet.

## Evidence

Original: `/home/btega/Downloads/PXL_20261009_180639619.mp4`.
Preserved copy, extracted frames, page index, and OCR search aid are in
`/home/btega/j604-boot/ans-review-n6miVhGq/C4-RUN-20261009T115319-0600/`.
Video SHA-256: `ffb8d01ba6f1ad32f027fec0952cea19f89c5226dfae08db5ab4b07b37345008`;
1,070,373,852 bytes; 481.603 seconds. This is the same C4 boot, not a rerun.

Extracted frame numbers correspond to nominal two-second sample intervals.
The pager has grown to 77 pages / 2498 retained lines, with 0 gaps, compared
with the earlier 76 pages / 2492 lines. OCR is a search aid and contains
character errors; the key observations below were checked against images.
Focus degrades late in the video, particularly around pages 37–47, so the
recording is not a complete exact transcription of all retained logs.

## Verified chronology

| Pager page / frame | Observation |
|---|---|
| 16 / frame-143 | [261] ANSRST pre-assert: ret=0, cpu=00000000, bst=00000000, t=+0us |
| 16 / frame-143 | [263] post-deassert: ret=0, cpu=00000000, bst=00000000, t=+1270us |
| 16 / frame-143 | [265] post-cpu-run: ret=0, cpu=00000010, bst=00000000, t=+2477us |
| 16–17 / frames 143,146 | NVMe HELLO min=max=want=12; endpoint maps base 0 / bitmap 0x51f and base 1 / bitmap 0x3, last=1; outgoing management sends return 0 |
| 19 / frame-152 | Crash buffer allocated: size=0x8000, IOVA=0x10003370000; I/O report buffer reply carries address 0x10003220000 |
| 19 / frame-152 | [298] boot waits for endpoint-map completion; [299] NVMe RTKit co-processor crashed |
| 20 / frames 155–156 | Exception from EL1h: PSR=0x600002c5, PC=0xd24c8, ESR=0xbe000000, FAR=0x49f008000, SP=0x314f80 |
| 21 / frames 158–159 | Ccst at 0x440, payload 0x60; first u32 is task ID 12 using the local m1n1 format |
| 22 / frames 160–162 | CasC at 0x4b0, payload 0x40; nonzero async-error information |
| 33 / frame-194 | Crtk at 0x1130, payload 0x720; names include rtk_ep_work, mbox_work_loop, tracekit_ep, tracekit_log_tx, Update |
| 34 / frame-197 | Further task names include Read, PreRead, DataXfer, Timer, power, System Thread, aspcore timer tick |

The original still photograph also shows the later endpoint-map wait
returning 0, then the IOP ACK wait returning -62. The last timeout is not
the initiating fault. The monotonic reset deltas include diagnostic logging
and interleaving with MTP; they are not pure reset-pulse duration measurements.

## Interpretation and remaining uncertainty

The kernel's `arch/arm64/include/asm/esr.h` defines EC shift 26 and SError
EC 0x2f. `(0xbe000000 >> 26) & 0x3f == 0x2f`. This is an asynchronous
exception, so the printed PC/FAR must not be treated as a proven offending
instruction/address. The available syndrome supplies no validated FAR
indicator. See Arm's [exception model](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/Exception%20model.pdf)
and [A-profile known issues on SError/FAR validity](https://documentation-service.arm.com/static/6894bc07e7f7ce6150e88fca?token=).

The local `/home/btega/m1n1-ctrr/proxyclient/m1n1/fw/asc/crash.py` describes
Ccst as task ID plus stack addresses, CasC as L2/LSU/FED/MMU async-error
register values, and Crtk as variable-length task records. These formats
give a grounded decoding route. Do not equate task ID 12 with the twelfth
printed name or assign bit meanings to CasC without validating them.

The printed RTKit Version line is empty. Firmware provenance therefore
remains unresolved; MTP's interleaved firmware build/version is not ANS's.
The available 26.6.2 IPSW is a candidate for later offline comparison, not
proof of the firmware running on this boot. No candidate firmware was flashed.

SART mapping and power/clock state remain hypotheses. The shared crash
buffer is readable, but that alone does not validate every firmware mapping
or DMA access. Neither the zeros in storage-prev-assert nor the malformed
footer diagnostic establishes the cause of the SError.

## Next experiment

C5 keeps C4's reset, RTKit handshake, bootloaders, DTB, and initramfs. It adds
bounded shadow-buffer summaries for Ccst/CasC/Crtk and raw version/header/
rejected-footer bytes. First identify task 12, the call stack, and the async
error fields. If those indicate a specific address or hardware path, compare
that path against the successful tethered control before making one
functional change. Otherwise instrument only the relevant SART mapping or
power dependency; do not combine power-state, reset, and mapping changes.
