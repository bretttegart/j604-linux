# Linux on the M4 MacBook Pro 14" (Mac16,1 / T8132 / J604) — WIP

Work-in-progress bare-metal Linux bring-up for the base-M4 14" MacBook Pro.
This repo is a public snapshot of a live investigation: patches, device
trees, and the test init, published for backup and because the current
blocker (NVMe) could use more eyes.

**Machine:** Mac16,1, T8132 (J604), Board-ID 0x22, macOS 26.6.2 (25G83).
(A DFU restore on Oct 5, 2026 removed the earlier 27.0 firmware from the
equation; 26.6.2 is now the only firmware in play.)

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
| Rootfs on disk | ⏳ partitions carved (998 MB ESP + 60 GB root), not yet formatted |

Boot methods: tethered (a patched m1n1 is chainloaded raw,
`chainload.py -n -r`, never the .macho; kernel via `linux.py`), and —
since Oct 5 — a blessed m1n1 stage1 on a dedicated macOS volume that
chainloads a combined `stage2.bin` (m1n1 + kernel + DTB + initramfs)
from a FAT ESP partition via a `chainload=<partuuid>;<path>` payload
variable. Cmdline: `idle=nop nokaslr loglevel=8 console=tty0
fbcon=nodefer`.

## Contents

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
- `patches/m1n1-nvme-reboot-handoff.diff` — experimental, refuted
  (raw47, Oct 5): `src/nvme.c` stop → reset → `rtkit_boot()` handoff so
  the next stage would find a freshly m1n1-booted IOP, plus a `wcslen`
  build fix in `src/string.c`. The kernel still crashed the ANS
  identically. Kept for the record; not part of the working path.
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
  ~8.2 MB, so the init is built stripped.

## NVMe: solved (tethered) — Oct 5, 2026

The ANS2 enable failure turned out to be one line. In
`apple_nvme_reset_work()`, the branch taken when iBoot has left the ANS
booted (`BOOT_STATUS == 0xde71ce55`) must call `apple_rtkit_wake()` —
the full IOP INIT → endpoint-map → IOP ACK → AP ON negotiation, the
same sequence Gravity Linux uses on the M4 Mac mini (commit
`8178b0adc214` on `gravity-m4`) — not
`apple_rtkit_set_ap_power_on()`, which never completes on T8132.
With that, `/dev/nvme0n1` enumerates, the GPT reads (header at byte
4096 — the ANS is 4Kn), and block reads verify. ~150 prior boot cycles
(raw13–raw34) eliminated everything else: NVMMU window layouts, power
domains, IOQ sizing, IRQ order, and the complete published Gravity
recipe item for item.

## The current blocker: kernel cold-boot crashes the ANS firmware

Untethered booting splits in two, and only the second half fails:

1. **The chain mechanism works.** The blessed stage1 (CTRR m1n1 with
   chainloading) read `stage2.bin` off the FAT ESP, booted the kernel —
   chain, GPT, and FAT all proven end-to-end.
2. **The kernel cannot cold-boot the ANS.** In the chain boot, m1n1's
   shutdown leaves the IOP stopped, so Linux takes its cold path
   (assert reset → `apple_rtkit_boot()`). The 26.6.2 firmware boots,
   negotiates, then *crashes* and hands the kernel a crashlog:
   `RTKit: co-processor has crashed`, `ANS did not boot`,
   `Reset failure status: -62`. Register snapshot at the decision
   point: branch 2 (cold), `CPU_CONTROL=0`, `BOOT_STATUS=0`.

Eliminated so far, one variable at a time: Gravity's EP7 RTKit
endpoint port (necessary-looking, not sufficient); m1n1 leaving the
firmware running (warm-leave); m1n1 fully rebooting the firmware fresh
before handoff. All fail identically once the kernel negotiates RTKit
after an m1n1 NVMe session — while the iBoot→kernel wake path, with
the ANS untouched by m1n1, works every time.

Open suspects, roughly ranked:

1. Something m1n1's own NVMe session (SART entries? queue teardown?
   controller disable?) leaves behind that the IOP firmware trips over
   on its next boot — versus the pristine post-iBoot state.
2. The firmware crashlog itself (sections `Csta`/`Cnvr`) has not been
   decoded; it should name the fault.
3. A missing piece of Gravity's RTKit support (crashlog completion
   during boot, running-IOP adoption) that the mini never needs because
   its path stays warm.

One diagnostic avenue is already closed: ramoops/pstore records
nothing in these boots (a working tethered boot paints
`STO 0 C 0 F 0` — `/sys/fs/pstore` exists but stays empty), so the
crash log cannot be harvested that way.

Next diagnostic: dump the full filtered kernel log of the failing
chain boot (the init parks on it for a photograph; payload
`stage2-diag.bin`, sha256 c608401b…). If you know ANS2
RTKit cold boot on T8132 firmware, issues and patches are very welcome.

## Safety

The test init never mounts or writes the internal disk, and no test has
written to it. Nothing here touches macOS: experiments run from an
initramfs under a tethered bootloader. Do not use any of this on a
machine you are not prepared to DFU-restore.

## Provenance

Hardware testing and direction by the machine's owner; kernel/DT work
was done in an agent-assisted session (Grok and Muse) and is published
as-is, unreviewed, for other bring-up efforts. Bases: AsahiLinux/linux,
AsahiLinux/m1n1, with the T8132 NVMe lineage from Yureka Lilian's series
as integrated by the Gravity Linux project.
