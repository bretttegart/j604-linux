# Full C6 Crg8 analysis — 2026-10-09

Sources: [the C6 session](C6-SESSION-2026-10-09.md) (full optical transcription of the kernel-printed raw Crg8/Cver), prior offline decode, kernel reader struct in `/home/btega/linux-asahi/drivers/soc/apple/rtkit-crashlog.c`, firmware exception-entry code in the 27.0.1 ANS candidate (normalized 0x8d08, 0xd648), ADT capture `LABOS-ADT-20261009T141804-0600` on sunki. Read-only on sunki; no boots.

Reconstruction: parsed the transcribed hex block mechanically; length 848 B (0x350), no offset gaps, sha256 c4d6a83fa2172729f1b37c0bef37be1cd72ce8bdc714803c985f3346430437cc. Evidence limit: still a visual transcription of screen frames, not a raw buffer extraction. The session notes flag a few low-order bytes in dense rows as best-effort; the anchor fields (FAR at +0x330, ESR at +0x340) were re-verified at 3-4x zoom. Nothing below depends on the flagged low-order bytes except where noted.

## 1. Layout: reader struct vs firmware exception frame

The kernel reader struct is `unk_0 u32, unk_4 u32, regs[31], sp, pc, psr, cpacr, fpsr, fpcr, unk[64], far, unk_X, esr, unk_Z` (0x350 B). The firmware exception entry at normalized 0x8d08 builds the same frame on the exception stack: x0-x30 at frame+0x000..0x0f0, saved SP at +0x0f8, ELR at +0x100, SPSR at +0x108, CPACR at +0x110, then (written at +0x328) FAR, PAR, ESR-low, with a PACGA word at +0x340. The crashlog payload is that frame preceded by an 8-byte header (type 0x0a, length 0x348), which is exactly why the reader struct starts with unk_0/unk_4 and its fields land on the frame fields. The reporting routine at 0xd648 refreshes ESR (32-bit) and FAR into the frame at frame+0x338/+0x328, i.e. payload+0x340 low half / payload+0x330. So the reader layout is correct; the earlier "8-byte shift" is the section header, not a producer/reader bug. Only the ESR low32 is meaningful; the upper word at payload+0x344 is the adjacent frame word (padding/PACGA area), which is why it changes between runs.

| reader offset | field | value | reading |
|---|---|---|---|
| +0x000 | unk_0 (type) | 0xa | section/record type 10 |
| +0x004 | unk_4 (length) | 0x348 | 0x348 = 0x350-8, matches the firmware record length written at 0xd718 |
| +0x008 | x0 | 0x0000000000a1dc50 | __DATA (norm 0x301c50) |
| +0x010 | x1 | 0x0000000000000004 | low/non-runtime |
| +0x018 | x2 | 0x0000000000000000 | low/non-runtime |
| +0x020 | x3 | 0x0000000060000304 | not an image VA |
| +0x028 | x4 | 0x0000000000a1dd68 | __DATA (norm 0x301d68) |
| +0x030 | x5 | 0x0000000000741e14 | __TEXT (norm 0x25e14) |
| +0x038 | x6 | 0x0000000000000000 | low/non-runtime |
| +0x040 | x7 | 0x00000000009640c8 | __DATA (norm 0x2480c8) |
| +0x048 | x8 | 0x0000000000000001 | low/non-runtime |
| +0x050 | x9 | 0x0000000000000001 | low/non-runtime |
| +0x058 | x10 | 0x0000000000000000 | low/non-runtime |
| +0x060 | x11 | 0x0000000000000000 | low/non-runtime |
| +0x068 | x12 | 0x0000000000000000 | low/non-runtime |
| +0x070 | x13 | 0x0000000000000000 | low/non-runtime |
| +0x078 | x14 | 0x0000000000004844 | low/non-runtime |
| +0x080 | x15 | 0x0000000000000040 | low/non-runtime |
| +0x088 | x16 | 0x0000000000000000 | low/non-runtime |
| +0x090 | x17 | 0x0000000000a5aa70 | __DATA (norm 0x33ea70) |
| +0x098 | x18 | 0x0000000000000000 | low/non-runtime |
| +0x0a0 | x19 | 0x0000000000a1dc50 | __DATA (norm 0x301c50) |
| +0x0a8 | x20 | 0x0000000000000004 | low/non-runtime |
| +0x0b0 | x21 | 0x0000000000000004 | low/non-runtime |
| +0x0b8 | x22 | 0x0000000000000000 | low/non-runtime |
| +0x0c0 | x23 | 0x0000000000a1a000 | __DATA (norm 0x2fe000) |
| +0x0c8 | x24 | 0x00000000009fff00 | __DATA (norm 0x2e3f00) |
| +0x0d0 | x25 | 0xec7ff03c047420d8 | not an image VA |
| +0x0d8 | x26 | 0xfc032855c4741d68 | not an image VA |
| +0x0e0 | x27 | 0xa50c947e44741d78 | not an image VA |
| +0x0e8 | x28 | 0x0000000000000008 | low/non-runtime |
| +0x0f0 | x29 | 0x0000000000974fb0 | __DATA (norm 0x258fb0) |
| +0x0f8 | x30 | 0xe502afe9e472983c | not an image VA |
| +0x100 | sp (saved SP) | 0x0000000000974f60 | __DATA/stack (norm 0x258f60) |
| +0x108 | pc (ELR) | 0x00000000007324f0 | __TEXT norm 0x164f0 = reporting wrapper instruction (stp at 0x164f0) |
| +0x110 | psr (SPSR) | 0x00000000600002c5 | EL1h |
| +0x118 | cpacr | 0x0000000000000000 | plausible CPACR (0) |
| +0x120 | "fpsr" | 0x0000000000a5a738 | pointer-like (__DATA norm 0x33e738); reader name not trusted semantically |
| +0x128 | "fpcr" | 0x0000000000974d00 | pointer-like (__DATA norm 0x258d00); reader name not trusted semantically |
| +0x330 | far | 0x000000049f008000 | exception-entry FAR (see FAR section) |
| +0x338 | unk_X | 0xffffffffffffffff | frame PAR slot, overwritten to -1 by the reporting routine when its copy/validate call fails (0xd740-0xd744) |
| +0x340 | esr (u64 read) | 0xf57347b5be000000 | low32 0xbe000000 is the real 32-bit ESR; upper word is adjacent frame bytes |
| +0x348 | unk_Z | 0x9a85dbc000000000 | tail word; only upper 32 bits nonzero in transcription - flagged as possible transcription ambiguity, not load-bearing |

Producer-layout cross-check (+8 header): producer frame FAR at frame+0x328 = payload+0x330 (reader far, correct); producer ESR-low at frame+0x338 = payload+0x340 low half (reader esr low32, correct); producer PAR at frame+0x330 = payload+0x338 (reader unk_X, here -1). No field is misread except the ESR upper word, which was never part of the 32-bit ESR.

## 2. The unk[64] region (+0x130..+0x32f): interrupted context?

The exception entry writes nothing between CPACR (frame+0x110) and FAR (frame+0x328). In payload terms, +0x118..+0x327 is unwritten frame gap, so its contents are pre-existing exception-stack memory carried into the crashlog copy. That is consistent with what is actually there:

- An `RTKSTACK` marker at +0x168 followed by `RTKS`+version at +0x170. The candidate image contains a repeated `RTKSTACK` fill pattern (stack-fill), so this is stack filler/header material, not a register field.
- Repeated pointer pairs and small counts (e.g. +0x140/+0x148 duplicating +0x120/+0x128; +0x1a0/+0x1a8 both 0x965000; +0x290/+0x298 and +0x2a0/+0x2a8 both 0x300/0x965000) - descriptor/stack residue, not a saved register frame.
- High-entropy words at +0x160, +0x1e0, +0x200, +0x250, +0x2c0, +0x2d0, +0x320 interleaved with the pointer pairs - consistent with PAC/hash material in stale stack data; none is a canonical image VA.
- Classification of every qword in +0x130..+0x32f: no value falls in the __TEXT runtime range (0x71c000-0x960000). All plausible pointers are __DATA/stack addresses (0x96xxxx-0xa5xxxx image offsets) or low non-VA values. There is no second ELR, no SPSR-shaped value paired with a code address, and no LR pointing at a call site.

Register-block hunt for the callback call: the BLRAAZ at normalized 0x25ce4 calls through x24, chosen in the dispatch routine (0x25ad0) from a descriptor field or a PAC-signed default code pointer (normalized 0x25d98). The saved x24 in this frame (+0x0c8) is 0x00000000009fff00, a __DATA address (image offset 0x2e3f00; the candidate file bytes there are zero/BSS, i.e. runtime-initialized). It is not a code pointer, not the default, and not a descriptor code pointer. The other descriptor-looking saved values (x0/x19 = 0xa1dc50, image offset 0x301c50; x23 = 0xa1a000, offset 0x2fe000) likewise land in zero/BSS file regions. So the actual callback target used at 0x25ce4 is not recoverable from Crg8: these are exception-time registers of the reporting frame, and the runtime descriptor contents are not in the static image.

The one code-range value in the saved registers is x5 = 0x741e14 (normalized 0x25e14), inside the callback-dispatch function; the word there is a load, not a call site, and in this reporting frame it does not identify an interrupted instruction. The frame PC itself (0x164f0) is the reporting wrapper, as established before.

Verdict on the core question: the unk[64] region does NOT preserve an interrupted context (no original ELR/SPSR/GPR frame, no callback target). The only register context in Crg8 is the reporting frame itself (x0-x30/SP/ELR/SPSR at the wrapper), which was already known.

## 3. FAR 0x49f008000 translation attempt

Checked: captured ADT (`LABOS-ADT-20261009T141804-0600/adt.txt` + the precomputed `fault-address-adt-lookup.json`), t8132 DT (nvme@4c5cc0000, sart@485c50000 in the low-40-bit-style address map used by the ADT text), ANS ADT reg list (0x281600000/0x88000, 0x281050000/0x4000, 0x285cc0000/0x60000, 0x283000000/0x1000000, ...).

- The ADT lookup for low-40 0x49f008000 finds NO matching AP physical reg range. Nearest ranges are arm-io/apcie at 0x497000000-0x497060000; FAR is about 0x7fa8000 (~128 MiB) above the top of the highest one. Not contained.
- ADT DRAM: base 0x10000000000, size 16 GiB. As a full host physical address, 0x49f008000 is far below DRAM base. Taken as a low-40 value against a 16 GiB DRAM window starting at 0, it exceeds the window by 0x9f008000. Either way it is not a captured DRAM range.
- It is not the NVMe MMIO (0x4c5cc0000) nor SART (0x485c50000) nor any ANS ADT reg range found.
- The CasC l2c_adr low-40 equality (from C5) only shows the same 40-bit value in cache/bus telemetry; those packed words are not host physical addresses (already established).

Plainly: FAR cannot be translated with the data available. It is an ANS-internal/bus-space value or an asynchronous-error artifact, not a captured AP physical range.

## 4. ESR EC 0x2f (SError, ISS 0): what it does and does not say

Verified: low32 be000000, EC (bits 31:26) = 0x2f = SError interrupt, ISS = 0. An SError is asynchronous: the saved ELR is the instruction boundary where the error was reported (here, inside the reporting wrapper), not the faulting instruction. For SError, FAR_EL1 is not architecturally guaranteed to identify a faulting access; with ISS=0 there is no syndrome detail to recover one. The exact repetition of FAR and low32 across C5/C5-repeat/C6 (with three different runtime bases) shows the value is deterministic, but determinism alone does not make it a fault address - a fixed telemetry/last-transaction value would repeat the same way. Nothing in ESR/FAR identifies a missing clock/power domain or a specific bad access. The task name `power` (Ccst task 14) identifies the reporting task context, not a cause.

## 5. Conclusion

(c) Inconclusive on the fault. The full Crg8 closes the register question (no hidden interrupted context in unk[64]; reader layout verified correct; ESR is 32-bit with a meaningless upper word) and FAR is untranslatable with available data, so Crg8 cannot name the faulting access or indict a Linux action. No narrow Linux cold-restart suspect is established by this payload.

Firmware-version-split assessment: UNCHANGED (split proven; causation neither strengthened nor weakened by Crg8 - the crash frame is the 27.0.1 reporting machinery behaving as its code dictates).

Smallest next datum: the crashlog mailbox-history section from the same crash buffer (the IOP power-state request/ack exchange Linux drove before the reset). It is already in the buffer the diagnostic dumps, so it is capturable by a diagnostic-only extension of the same dump (no behavior change), and it is the one remaining record that could show a malformed/unexpected power message (Linux suspect) versus a firmware-internal death with a clean exchange (firmware suspect). The callback target at 0x25ce4 would also help but is firmware-internal state not capturable from Linux.
