# Unchanged C5 repeat — Oct 9, 14:24 MDT

**Linux reached the pager; ANS cold restart still fails.** This repeat
localizes a reproducible firmware path: all ten Ccst addresses become
identical to the first C5 run after subtracting each run's runtime base.
The firmware identity was verified from fresh LabOS immediately beforehand.

## Run and evidence

- Fresh LabOS proxy, after bounded ADT/ANS manifest/text capture at 14:18.
- One unchanged upload at **14:24:17 MDT** using `scripts/run-c5.sh`.
- Stage2 SHA-256:
  `b0cac1a4a8948dc40281d73b9966a3dd97783ac25060e470b98fc97981c64f20`.
  All local component checksums passed. ESP used the previously staged C5
  file; its destination hash was not independently reread for this repeat.
- Stage1 camera confirms C5 filename/7,615,911-byte read and clean SHUT audit.
- Run: `/home/btega/j604-boot/ans-review-n6miVhGq/C5-RUN-20261009T142417-0600/`.
- Camera: `/home/btega/j604-boot/ans-review-n6miVhGq/C5-REPEAT-CAMERA-20261009T1427/`.
  Its directory label is not the start time: `context.json` records 14:24:34.
  Nine MP4 segments total 661.5 seconds. Recording stopped after the summary
  was captured; no second upload or reset was performed.
- Host exited 1 with UART timeout after handoff. Camera proves Linux booted;
  that host status does not establish a Linux boot failure.

[Selected transcription](C5-REPEAT-TRANSCRIPTION-2026-10-09.json) preserves
raw bytes and frame hashes. It is manual optical transcription, not direct
acquisition of the crash buffer. OCR only located pages; digits were checked
against images. The camera retains a pager cycle, but a complete text log
has not been transcribed or checked line by line.

## Summary and repeated error

PAGE 1/80 shows kernel `7.1.9-g77cb8f24c238-dirty`, build #32, boot ID
`9f24e8f4-a15d-4c48-a068-62eac9c56bc7`. ANSBR 2,
CPU_CONTROL `00000010`, BOOT_STATUS `00000000`; namespace absent after
60 seconds, GPT/read tests not run. First crash [299], final reset [1063]
status `-62`; 2,587 retained kmsg lines, zero gap markers.

The repeat's main CLHE header declares `0x4bc0` bytes (first C5: `0x4be0`),
version 771, flags `0x0a`, allocated `0x8000`. Do not carry the first run's
footer offset into this run without checking the actual section walk.

PAGE 40 independently maps task 14 to `power`, flags `8000`, zero task-table
frames. PAGE 22/23 Ccst contains ten frames for task 14. These are distinct
records, so the task-table frame count does not contradict Ccst.

| Field | First C5 | Unchanged repeat |
|---|---|---|
| Cver payload +16, inferred runtime base | `0x184000` | `0xc0c000` |
| Reported PC | `0x19a4f0` | `0xc224f0` |
| PC minus base | `0x164f0` | `0x164f0` |
| SP minus base | `0x258f60` | `0x258f60` |
| Reported ESR | `25642912be000000` | `c71ce3b0be000000` |
| FAR | `0x49f008000` | `0x49f008000` |
| CasC l2c_adr | `030004049f008000` | `030000049f008000` |
| CasC lsu_sts | `238000049f008000` | `238000049f008000` |

Both runs have CasC l2c_sts `80`, l2c_inf `0000000100000002`, and zero
fed/mmu words. The l2c_adr upper bits differ; only the repeated low 40-bit
address is identical. Its translation and FAR validity remain unresolved.

## Runtime mapping resolved for C5

Cver's first 16 bytes are startup instructions, followed by a little-endian
64-bit value at +16, then the RTKit text at +24. Treating +16 as the runtime
base produces the same entire Ccst sequence in both boots:

```text
164f0 d838 8c58 25ce4 3a408 3e8a0 3b370 21ad8 21978 216bc
```

In the matching Mach-O, normalized address `a` maps to file offset
`a + 0x4000` within __TEXT. All nine noninitial addresses point directly to
`BL`/`BLRAAZ` instructions, rather than the following return addresses.
This cross-run agreement strongly validates the mapping and explains why
the previous unslid disassembly did not align. ADT __TEXT IOVA 0 is not the
runtime code base. C4's runtime base remains unknown; do not compare its raw
PC `0xd24c8` against these normalized addresses.

The local candidate directory retains `C5-normalized-stack.txt` and
`C5-normalized-caller-regions.txt`. The earlier
`C5-stack-and-C4-PC-candidate.txt` uses an unvalidated zero slide and is
superseded for address-level conclusions.

## Exception format: measured code, remaining inference

The normalized path includes exception dispatch at `0x8c58`, calling
`0xd648`, and reporting through `0xd838 -> 0x164e8`. The first reported PC
`0x164f0` is a stack-save instruction in that reporting wrapper. It does
not identify the access that triggered an asynchronous SError.

At `0xd728` the matched firmware executes `mrs x8, esr_el1`, followed by
`str w8, [x19, #0x338]`. It reads FAR and stores 64 bits at context +0x328.
The existing Crg8 reader has an eight-byte prefix and reads ESR as 64 bits
at payload +0x340, FAR at +0x330. An eight-byte prefix plus this context
would explain the changing upper ESR word as adjacent/padding contents.
That serialization relationship is still an inference: trace the producer
before changing the format. Preserve the full printed word and use the
repeated low 32 bits `be000000` for the current SError interpretation.

## Next work

Trace the matched exception-context producer and callback path, then resolve
the repeated address through the firmware's own mappings. The live ADT has
no direct peripheral-register-range match for `0x49f008000`; that negative
lookup does not prove an invalid access or identify a missing power domain.
Select one narrow measurement once the address/path is identified. Do not
repeat unchanged C5 again, reflash firmware, or add mid-reset MMIO reads.
The [updated plan](NEXT-TEST-AFTER-C5-2026-10-09.md) defines the next
diagnostic and subsequent namespace/read pass criteria.
