# C9 m1n1 restart with different RTKit buffer addresses — Oct 12, 2026

**FR PASS.** A fresh LabOS session completed m1n1 init → five block reads →
one proven shutdown → second init → the same five reads, with all three
RTKit buffers at new, non-overlapping physical intervals. Exact address
reuse is not required for this measured m1n1 restart. The separate
[Linux RAM-preload comparison](C9-PRELOAD-SESSION-2026-10-12.md) remains
L0 PASS / L1 FAIL with cold ANS crash, reset `-62`, and no namespace.

Run directory:
`/home/btega/j604-boot/ans-review-n6miVhGq/C9-PREP-RELOCATE-20261012/`.
One temporary raw m1n1 send, one restart cell, Oct 12 at 13:04 MDT.
No Linux payload was booted in FR. No SSD writes, partition mounts,
ESP changes, installed bootloader replacement, blessing or push occurred.

## Controlled change

The previous upstream/local U/F cells reused all three RTKit buffer
intervals exactly. FR uses a disposable copy of the same observed local
source/build configuration as F. The only source changes from that copy
are `rtkit.c`, `c9diag.c`, and `c9diag.h`:

- After successful first init and all five reference reads, the host arms
  one-shot retention through diagnostic selector 3.
- The normal ANS RTKit buffer-release hook removes each SART mapping first.
  For the first three `nvme` buffers only, it then skips the heap `free`.
  It retains at most three allocations totaling 64 KiB, until reboot.
- Reset, power requests, mailbox messages, buffer allocation calls, queue
  operations and the existing release-function return are preserved.
  Other RTKit clients follow their original release behavior.
- The host requires exactly three retained intervals matching the first
  init's maps before requesting the second init. Before second reads, it
  requires equal buffer sizes and no overlap between any old/new intervals.

This is an allocator-release experiment, not observation-only tracing or
a proposed production fix. Old backing memory remains allocated. Its
retention can change other heap placements; we do not claim that only
three physical addresses differ. It does not exclude every stale-state
defect or establish Linux/m1n1 protocol equivalence.

Reproducible overlay:
[`prepare-c9-relocate.py`](scripts/prepare-c9-relocate.py).
The script refuses live Git trees and source paths outside disposable
`C9-PREP-*` copies. The generated `relocate-from-local.patch` is preserved
with the run. Original F/audit/active source trees were not modified.
Label `C9-LOCAL-R`; raw image 3932160 bytes, SHA-256
`596d97e87303843ef30940e26ecacc0c1263b2a203e5662c3f5638f929910add`.
Build flags match F: `USE_CLANG=1 CHAINLOADING=1 EXTRA_CFLAGS=-DNO_DISPLAY`,
`RUSTFLAGS=-C llvm-args=-disable-loop-idiom-wcslen`.

## Hardware result

| Buffer / preceding request endpoint | First init | Second init | Bytes |
|---|---|---|---:|
| Crashlog / 1 | `0x100071b8000` | `0x100071d4000` | 32768 |
| IOReport / 4 | `0x100071c4000` | `0x100071e0000` | 16384 |
| Syslog / 2 | `0x100071cc000` | `0x100071e8000` | 16384 |

Both read sets match the saved C9 SHA-256 for namespace 1's 4Kn LBAs
0, 1, 2, 128 and 4096. Every read begins with a host-written RAM sentinel;
the GPT signature/disk bound is checked at LBA 1. No write/flush command
is issued to NVMe. ANS is deliberately left running after success; any
next comparison needs a fresh LabOS boot.

The final trace records 380 events and 15 SART snapshot records, with zero
drops, zero unstable measured slots, and no ANS crash. It proves two real
initializations and one shutdown. The shutdown includes actual AP QUIESCED
and IOP SLEEP ACKs, successful internal sleep-switch completion, CPU RUN
clear and the resolved ANS reset. The absent ANS2 alias returns `-1`; its
status-2 snapshot skips MMIO and is not evidence of cleared slots.

SART entries are unchanged across sleep and the resolved reset. Release
removes old RTKit slots 5, 7 and 8 even though the allocations are retained;
the second init maps new addresses in those slots. All protected entries
0–4 and 6 retain their complete values through every measured phase.
The fresh ANS manifest is byte-identical to the earlier F capture.
No EP7 send or receive appears in this m1n1 trace.

## Validation and next comparison

The temporary image built successfully. A native ASan/UBSan harness uses
the actual prepared diagnostic code and release hook to verify normal
unmapping, ANS-only scope, one-shot arming, invalid-input rejection,
failed-unmap exclusion, the three-buffer/64-KiB cap, unchanged ABI and
the original release return. Seven
[offline host checks](diagnostics/m1n1-c9/test_restart_relocation.py)
reject identical/partially overlapping replacement ranges, missing or
failed maps and partial/wrong retention. The updated decoder also accepts
the saved U/F captures and proves their original shutdowns.

[`run-c9-restart.py`](scripts/run-c9-restart.py) now supports
`--relocate-buffers`, requires the corresponding image label and verifies
the raw image hash before connecting. The same stop-on-first-failure and
per-operation host deadlines apply; a host deadline does not cancel target
code. No automatic retry or failure cleanup is sent.

The [machine summary](C9-RELOCATE-RESULTS-2026-10-12.json) records the
manifest, result, offline analysis and evidence hashes. Raw block captures,
ADT and mailbox/SART records remain in the local run directory.

With U, F and FR all passing but Linux L1 failing, the next selected
comparison is the [grouped Linux parity screen](C9-REVIEW-2026-10-12.md#strip-for-parity-recommendation):
retain the required T8132 hardware support and warm wake behavior while
removing the extra EP7 handling/start, early controller-disable call and
extra branch together. First prove a warm control with that kernel, then
repeat the cold preload/read/shutdown handoff using the same fixed-screen
verifier. This is a screen; a pass would require restoring deltas separately
to attribute the change. The parity kernel is not yet built or booted.
