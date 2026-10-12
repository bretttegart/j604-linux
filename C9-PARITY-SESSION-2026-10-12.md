# C9 grouped Linux parity comparison — Oct 12, 2026

**P0 warm PASS; P1 cold FAIL.** The grouped parity kernel preserves warm
Linux storage operation but does not resolve the cold ANS failure:
branch 2, firmware crash, reset `-62`, and no namespace. This follows
[L0 PASS / L1 FAIL](C9-PRELOAD-SESSION-2026-10-12.md) and
[m1n1 FR PASS with different RTKit buffers](C9-RELOCATE-SESSION-2026-10-12.md).

Run directory:
`/home/btega/j604-boot/ans-review-n6miVhGq/C9-PARITY-20261012/`.
The owner supplied a fresh LabOS proxy separately for P0 and P1.
Each cell used one temporary raw m1n1 send and one Linux handoff.
No SSD write commands, internal partition mounts, ESP changes, blessing,
installed bootloader replacement or push occurred.

## Source and build

The original C8 source tree remains preserved. A separate copy retains
its pinned base `77cb8f24c2381a8abb7272d7bbdec548d6426a8a` and all existing
M4 support/diagnostics, with only these grouped changes:

- Remove EP7 start/receive handling, its buffer-reply variant and buffer
  state/release sites from RTKit.
- Remove the early T8132 `nvme_disable_ctrl()` block before admin-queue
  programming, including its preparatory capability read.
- Restore the baseline two-case decision: CPU RUN clear uses reset/reinit/
  boot; CPU RUN set uses wake. Retain ANSBR 2/3 reporting and proven wake.

T8132 MMIO/NVMMU/IOQ support, DT/PMGR/AIC changes, CTRR reservations,
normal reset/power operations and C8 diagnostic hooks remain. No delay
sweep, IOP OFF request or firmware intervention is introduced.

[`prepare-c9-parity.py`](scripts/prepare-c9-parity.py) applies the changes
only to a disposable `C9-PARITY-*/kernel-src` copy. The exact
[C8-to-parity patch](diagnostics/kernel-c9/c8-to-parity.patch) is reviewable.
The baseline dirty-source patch and per-file before/after hashes are
preserved locally. Comparing every tracked source with the C8 tree finds
changes only in `drivers/nvme/host/apple.c`, `drivers/soc/apple/rtkit.c`
and `drivers/soc/apple/rtkit-internal.h`. Applying the generated patch in
check-only mode against the preserved C8 sources succeeds.

`make -j4 ARCH=arm64 LLVM=1 Image.gz` succeeds. The config is byte-identical
to C8, SHA-256
`58555ef341ff0ed8f2bec3078fce1882d8e97c9086e53f14369664161447bcfb`.
Release: `7.1.9-g77cb8f24c238-dirty`. USB/gadget support remains disabled;
Linux results come from the fixed panel, not a USB console.

| Kernel artifact | Bytes | SHA-256 |
|---|---:|---|
| Parity Image.gz | 2944858 | `aeb4b1562c410084bd88280f6b0f036243f93d0396fa4672de9cdfd09b571fa7` |
| Decompressed Image | 10686976 | `c4676e6305ccbdba485c02eb38040084d03b5711b0857be2ee3c1caf537927ec` |

The m1n1 image, input DTB, fixed-screen initramfs and reference block hashes
match L0/L1 exactly. P0/P1 use identical parity components and loader steps,
differing in their cell label and P1's one storage cycle. The existing
[preload runner](scripts/run-c9-preload.py) now accepts P0/P1 labels using
the same warm/cold paths as L0/L1; no additional proxy operation is added.
The prepared DTB and physical addresses are recorded per fresh session.
They are not presumed identical across sessions.

## Hardware comparison

| Field | P0 — warm control | P1 — cold handoff |
|---|---|---|
| Handoff time (MDT) | 13:12 | 13:14 |
| Prior m1n1 NVMe use | None; zero INIT_BEGIN events | One init, five matching reads, one proven shutdown |
| Pre-handoff CPU / BOOT_STATUS | `0x10` / `0xde71ce55` | `0x0` / `0x0` |
| Linux result | PASS | FAIL |
| Namespace | YES | NO |
| Linux direct reads | MATCH 5 OF 5 | 0 OF 5; none attempted without namespace |
| ANS branch | 3 — warm wake | 2 — cold reset/boot |
| ANS crash | NO | YES |
| Reset error | NONE | `-62` |
| Boot ID prefix | `2c7790d0` | `575df85c` |
| Final phase / error | READS MATCH / NONE | NO NAMESPACE / NO NVME |

All kernel/initramfs/prepared-DTB readback hashes are unchanged across each
cell's control/storage window. Both kernels match the decompressed host
image. P1's queue/RTKit intervals do not overlap the preloaded components.
Both boot requests acknowledge with integer zero; camera evidence supplies
the Linux outcomes. Fresh ANS manifests match between P0 and P1.

P1's pre-handoff trace has 223 events and ten SART snapshot records,
zero drops, stable measured slots and no m1n1 ANS crash. Actual AP QUIESCED
and IOP SLEEP ACKs precede successful internal sleep, CPU stop and the
resolved ANS reset. SART entries remain unchanged across sleep/reset;
normal release returns the table to its initial protected entries by
removing slots 5, 7 and 8. The unresolved ANS2 snapshot is explicitly
skipped (status 2), not a measurement of cleared slots.

The C920 captures bounded 1920×1080 MJPEG stills, discarding 60 startup
frames. Early P1 evidence shows WAIT plus the ANS crash/reset error; the
final frame after the namespace deadline shows FAIL. Manual result
transcriptions in each `linux-result.json` were checked against the frames.
No raw Linux log or new crash fault-register context is exported here.

Final frame hashes:

- `P0-RUN/status-final.jpg`:
  `af45165f93b3eedca49a40f6d763ac5e5f103a4f88965e1adb1a062af0cb3d88`.
- `P1-RUN/status-final.jpg`:
  `5e2a5e23303f593b78e16524f0d1a6dc0859e6580306cc182a86ba6b1c6933e8`.

Both cells' machine summaries and evidence hashes are recorded in
[C9-PARITY-RESULTS-2026-10-12.json](C9-PARITY-RESULTS-2026-10-12.json).

## Interpretation and next test

The grouped changes do not fix the observed cold-start failure. The failure
class matches L1's panel, but this capture cannot establish identical fault
registers or instruction location. A grouped failure does not prove the
individual deltas irrelevant: interactions and masking remain possible.
The early controller-disable call is after successful RTKit boot, and the
removed extra branch was not used in recorded branch-2 failures.

The next selected comparison is R from the existing matrix: warm Linux
boot with verified direct reads, one unbind/rebind of the actual ANS platform
device, then repeated direct reads and explicit phase/result reporting.
It tests a Linux-managed ownership transition rather than the m1n1-to-Linux
handoff. The runtime path has different starting state/buffers, so either
result needs that qualification. R is not prepared or executed in this run.
SART/reset/buffer chronology can then target the transition that fails.
