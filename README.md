# Linux on the M4 MacBook Pro 14" (Mac16,1 / T8132 / J604) — WIP

Work-in-progress bare-metal Linux bring-up for the base-M4 14" MacBook Pro.
This repo is a public snapshot of a live investigation: patches, device
trees, and the test init, published for backup and because the current
blocker (NVMe) could use more eyes.

**Machine:** Mac16,1, T8132 (J604), Board-ID 0x22. The user reports a full
26.6.2 (25G83) restore. Oct 9 collection confirms running macOS 26.6.2,
LabOS restore files 26.7.1, and SFR/current 27.0.1. Fresh LabOS uses the
same captured SFR ANS manifest. The timing of component changes remains
unknown; these version facts do not establish an incompatible combination
or a cause of the ANS crash. See the firmware provenance record below.
> **Start here (Oct 9):** [C6](C6-SESSION-2026-10-09.md) reaches the pager
> and reproduces the cold ANS failure, but completes the diagnostic
> payload capture: full Crg8 (0x350 B) and Cver (0x90 B). The
> [full Crg8 analysis](CRG8-ANALYSIS-2026-10-09.md) verifies the reader
> layout, finds no hidden interrupted context in `unk[64]`, leaves FAR
> `0x49f008000` untranslated, and keeps the firmware version-split as an
> observation rather than a proven cause. The next single datum would be
> the crashlog mailbox-history section (IOP power-state request/ack);
> it is parked as of Oct 9. No C7 has been built or sent.
> [Firmware acquisition and live LabOS capture](FIRMWARE-INVENTORY-2026-10-09.md)
> verify the matching 27-family ANS code image; running macOS/stage-two
> remains 26.6.2. [C4 video findings](C4-VIDEO-REVIEW-2026-10-09.md) and
> [C5](C5-SESSION-2026-10-09.md) are prior comparisons; C/C2's wedge came
> from ANS reads during reset. The
> [detailed review](REVIEW-2026-10-07.md) contains the desktop roadmap, and
> [test results](TEST-RESULTS.md) preserve the hardware observations.

> **Snapshot note (Oct 7, 2026):** patches and init were regenerated
> from the live trees this day, so the files below now include the
> `apple_rtkit_wake()` NVMe fix, the Gravity EP7 port (insufficient on
> its own), the ANSCHK/ANSBR diagnostics, and the KMSG DIAG init.

## Status

| Area | State |
|---|---|
| SMP (10/10 CPUs) | ✅ working — needed CTRR_C + CTRR_D reservations (see m1n1 patch) |
| SMC (macsmc, GPIO keys) | ✅ working |
| Built-in keyboard (MTP dockchannel → hid-apple) | ✅ working, keys reach the VT console |
| Tethered boot to userspace | ✅ working (initramfs) |
| NVMe (apple,t8132-nvme-ans2) | ✅ working tethered — enumerate + GPT + block read proven (see below) |
| Untethered boot | ❌ kernel cold-boot of the ANS firmware crashes the IOP — see below |
| Rootfs on disk | ⏳ 998 MB ESP + 60 GB Linux-root partition reported; ESP file loading proven, Linux root not yet installed; verify current layout before deployment |

Boot methods: tethered (a patched m1n1 is chainloaded raw,
`chainload.py -n -r`, never the .macho; kernel via `linux.py`), and —
since Oct 5 — a blessed m1n1 stage1 on a dedicated macOS volume that
chainloads a combined `stage2.bin` (m1n1 + kernel + DTB + initramfs)
from a FAT ESP partition via a `chainload=<partuuid>;<path>` payload
variable. Cmdline: `idle=nop nokaslr loglevel=8 console=tty0
fbcon=nodefer`.

## Contents

- `NEXT-TEST-AFTER-C5-2026-10-09.md` — after-C5 plan; its Crg8/Cver capture
  items are completed by C6 and the mailbox-history datum is parked.
- `C5-CRASHLOG-TRANSCRIPTION-2026-10-09.json` — selected manually captured
  bytes/values and source frame hashes.

- `C5-SESSION-2026-10-09.md` — completed hardware result, hashes, validation,
  staging and capture instructions; source delta in
  `patches/linux-c4-to-c5-crashlog-diag.diff`.
- `C5-REPEAT-SESSION-2026-10-09.md` — unchanged repeat and cross-run address
  normalization; selected values and photo hashes in
  `C5-REPEAT-TRANSCRIPTION-2026-10-09.json`.
- `C6-SESSION-2026-10-09.md` — diagnostic-only C6 run: same ANS failure,
  complete raw Crg8/Cver capture, artifacts, staging, and hardware result.
- `CRG8-ANALYSIS-2026-10-09.md` — full Crg8 layout/register/FAR analysis;
  no hidden interrupted context, FAR untranslated, conclusion inconclusive.
- `C4-VIDEO-REVIEW-2026-10-09.md` — verified reset/exception chronology and
  limits of the video transcription.
- `C4-SESSION-2026-10-09.md` — current payload hashes, staging/run commands,
  corrected reset diagnostics, and required crashlog capture.

- `FOLLOWUP-2026-10-07.md` — A/B results review, diagnostic corrections,
  and the original stage1 shutdown audit plan.
- `POST-SHUT-AUDIT-PLAN-2026-10-07.md` — updated diagnosis and next kernel
  diagnostic test.
- `HANDOFF-2026-10-07.md`, `SHUT-AUDIT-RESULT-2026-10-07.md`, and
  `TEST-RESULTS.md` — Muse's hardware results.
- `MUSE-RUNBOOK.md` — original A/B preparation, controlled test matrix,
  pass/fail criteria, and results handoff format (now executed).
- `REVIEW-2026-10-07.md` — static audit and desktop roadmap, including the
  supplied Gravity GPU and hypervisor research leads.
- `patches/linux-asahi.diff` — against AsahiLinux/linux `asahi` branch
  @ 77cb8f24c238. NVMe/ANS/SART nodes for T8132, J604 DT, the ANS2 driver
  changes (the `apple_rtkit_wake()` fix, a pre-write register snapshot
  print, and ANSCHK/ANSBR cold-boot diagnostics), the Gravity EP7 RTKit
  endpoint port, RTKit AP-power helper, SART protected-mask helper, plus
  two boot-hack fixes (`delay.c`, `irq-apple-aic.c`). This is a working
  tree snapshot, diagnostics included — not a cleaned-up upstream series.
- `patches/m1n1-ctrr.diff` — against m1n1 v2.0.0-dirty (ce2b8a43),
  `src/kboot.c` only. Reserves the second CTRR window (CTRR_D, 912 KiB
  ending at the m1n1 image base); this is what lets secondary CPUs start.
- `patches/m1n1-nvme-reboot-handoff.diff` — historical experiment (raw47),
  **not a valid test of the intended successful handoff**. The restart
  was added to `nvme_init()` error cleanup, while normal `nvme_shutdown()`
  still stops ANS. That error path also frees buffers/mappings immediately
  after restarting the IOP. Preserved unchanged as evidence, including
  the `wcslen` build fix; do not copy it as a handoff solution.
- `dts/t8132-j604-ramoops.dts` — the boot DT used for all tests.
- `init/init.go` — the test initramfs init (Go): never mounts the disk,
  paints status lines the host reads via webcam, verifies block reads
  (RDOK), checks pstore, and on a failed chain boot parks and dumps a
  filtered kernel log (`===== KMSG DIAG =====`).
- `assemble_boot.py` — builds the untethered payloads: appends kernel /
  DTB / initramfs payloads and `chainload=` variables to an m1n1 binary
  at its payload offset (0x3b0000 for our build). Payload kernels must
  be `Image.gz` — m1n1's minimal LZMA rejects modern `.xz` block
  headers — and small: the proxy chainload path rejects images over
  the protected-memory boundary (about 8.2 MB in prior runs), so the init
  is built stripped. This is not a universal kernel/initramfs size limit;
  `linux.py` loads the separate components by a different path.

## NVMe: solved (tethered) — Oct 5, 2026

The ANS2 enable failure turned out to be one line. In
`apple_nvme_reset_work()`, the branch taken when iBoot has left the ANS
booted (`BOOT_STATUS == 0xde71ce55`) must call `apple_rtkit_wake()` —
the full IOP INIT → endpoint-map → IOP ACK → AP ON negotiation, the
same sequence Gravity Linux uses on the M4 Mac mini (commit
`8178b0adc214` on `gravity-m4`) — not
`apple_rtkit_set_ap_power_on()`, which never completes on T8132.
With that, `/dev/nvme0n1` enumerates, the GPT reads (header at byte
4096 — the ANS is 4Kn), and block reads verify. Prior experiments
(raw13–raw34) explored NVMMU window layouts, power domains, IOQ sizing,
IRQ order, and the published Gravity recipe. Those results deprioritize
repeating the same permutations without new evidence; they do not eliminate
every possible interaction. Muse reproduced enumeration, the GPT signature,
and matching buffered header reads with kernel A on Oct 7 (TETHER-A2).
Use that exact combination as the current control. Its diagnostic capacity
display was eight times too large; corrected capacity is 500,277,792,768 bytes.

## The current blocker: kernel cold-boot crashes the ANS firmware

Untethered booting splits in two, and only the second half fails:

1. **The chain mechanism works.** The blessed stage1 (CTRR m1n1 with
   chainloading) read `stage2.bin` off the FAT ESP, booted the kernel —
   chain, GPT, and FAT all proven end-to-end.
2. **The kernel cannot cold-boot the ANS.** In the chain boot, m1n1's
   shutdown leaves the IOP stopped, so Linux takes its cold path
   (assert reset → reinitialize → deassert reset → CPU RUN →
   `apple_rtkit_boot()`). The firmware boots,
   negotiates, then *crashes* and hands the kernel a crashlog:
   `RTKit: co-processor has crashed`, `ANS did not boot`,
   `Reset failure status: -62`. Register snapshot at the decision
   point: branch 2 (cold), `CPU_CONTROL=0`, `BOOT_STATUS=0`.

Gravity's EP7 RTKit endpoint port did not fix the recorded failure by itself.
The warm-leave experiment was recorded as unsuccessful, but its precise
handoff state needs verification. The reboot-before-handoff experiment
modified the wrong control-flow path, so that strategy remains untested
in the intended form. The successful iBoot→kernel wake path was reproduced
by Muse's TETHER-A2 test on Oct 7 and remains the control.

Open suspects, roughly ranked:

1. Incomplete shutdown/reset or stale firmware-visible state after an m1n1
   NVMe session. `rtkit_sleep()` mishandles a Boolean failure result; callers
   also ignore the outcome. Audit the actual ACKs before changing behavior;
   the source defect alone does not establish why firmware crashes.
2. SART/shared-buffer lifetime or stage relocation differences. A running
   IOP cannot safely inherit buffers that the next stage frees or overwrites.
3. Cold-start protocol differences beyond the tested explicit INIT.
   CHAIN-B changed only T8132's cold call to `apple_rtkit_wake()` and still
   crashed. Both A and B reached an IOP-ACK wait timeout; the early B trace
   was not fully photographed, so protocol equivalence remains unproven.

The crashlog should guide further changes. Capture the first assertion and
actual section identifiers before assuming the meaning of `Csta`/`Cnvr`.
The current parser already understands several other section types.

The existing ramoops/pstore attempt returned no records (`STO 0 C 0 F 0`).
That recovery path has not worked; it does not prove persistent logging is
impossible. Prefer complete current-boot logs for the next experiment.

Next: follow [the post-audit diagnostic plan](POST-SHUT-AUDIT-PLAN-2026-10-07.md).
The older
`stage2-diag.bin` (`c608401b…`) embeds a diagnostic init that truncates lines
and retains only the final 45 matching lines, and `ANSBR 3` is commented out
in its kernel. Muse's A/B artifacts supersede it for the current comparison.
Preserve those artifacts and verify the ESP copy of stage2 as well as the
host file. The follow-up records remaining common-init reporting defects.

## Safety

The Linux diagnostic init never mounts or writes the internal disk. LabOS
configuration, partition preparation, and ESP payload staging are separate
operations that have changed disk state. The next driver experiments remain
read-only from Linux; they require no repartitioning, formatting, firmware
restore, or change to the installed boot object. Keep known working boot
files when staging individually named experiments on the existing ESP.

## Provenance

Hardware testing and direction by the machine's owner; kernel/DT work
was done in an agent-assisted session (Grok and Muse) and is published
as-is, unreviewed, for other bring-up efforts. Bases: AsahiLinux/linux,
AsahiLinux/m1n1, with the T8132 NVMe lineage from Yureka Lilian's series
as integrated by the Gravity Linux project.
