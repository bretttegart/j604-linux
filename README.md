# Linux on the M4 MacBook Pro 14" (Mac16,1 / T8132 / J604) — WIP

Work-in-progress bare-metal Linux bring-up for the base-M4 14" MacBook Pro.
This repo is a public snapshot of a live investigation: patches, device
trees, and the test init, published for backup and because the current
blocker (NVMe) could use more eyes.

**Machine:** Mac16,1, T8132 (J604), Board-ID 0x22, macOS 26.6.2 (25G83),
system FW 27.0 / OS FW 26.6.2.

## Status

| Area | State |
|---|---|
| SMP (10/10 CPUs) | ✅ working — needed CTRR_C + CTRR_D reservations (see m1n1 patch) |
| SMC (macsmc, GPIO keys) | ✅ working |
| Built-in keyboard (MTP dockchannel → hid-apple) | ✅ working, keys reach the VT console |
| Tethered boot to userspace | ✅ working (initramfs) |
| NVMe (apple,t8132-nvme-ans2) | ❌ ANS firmware dies during controller enable — see below |
| Untethered boot / rootfs | ⏳ blocked on NVMe |

Boot method: tethered. A patched m1n1 is chainloaded raw
(`chainload.py -r`, never the .macho) from a proxy host; the kernel is
booted with `linux.py`. Cmdline: `idle=nop nokaslr loglevel=8
console=tty0 fbcon=nodefer`.

## Contents

- `patches/linux-asahi.diff` — against AsahiLinux/linux `asahi` branch
  @ 77cb8f24c238. NVMe/ANS/SART nodes for T8132, J604 DT, the ANS2 driver
  changes (incl. a pre-write register snapshot print), RTKit AP-power
  helper, SART protected-mask helper, plus two boot-hack fixes
  (`delay.c`, `irq-apple-aic.c`).
- `patches/m1n1-ctrr.diff` — against m1n1 v2.0.0-dirty (ce2b8a43).
  Reserves the second CTRR window (CTRR_D, 912 KiB ending at the m1n1
  image base) in kboot.c; this is what lets secondary CPUs start.
- `dts/t8132-j604-ramoops.dts` — the boot DT used for all tests.
- `init/init.go` — the test initramfs init (Go): never mounts the disk,
  paints status lines the host reads via webcam.

## The NVMe blocker (help wanted)

The ANS2 driver binds, queues are created, and the ANS firmware then
dies during `nvme_enable_ctrl`: CSTS reads 0, reset returns −19. ~150 s
cycle, every time. The same driver recipe enumerates the internal SSD
on the M4 Mac mini (J773g, Gravity Linux), so this is J604-specific.

What the last boots established (read-only probe snapshot taken *before
any driver write to the ANS*, painted by the init):

- `BOOT_STATUS` = `0xde71ce55` — iBoot left the ANS booted and healthy.
- SART bootloader mask `0x005f` — 6/16 slots protected, 10 free.
- `CSTS` = `0x00000000` at probe; `CC` = `0x00474000` — controller
  arrives disabled, EN clear, a normal-shutdown notification still set.
- iBoot's own ANS boot works; Linux's enable never completes.

Already eliminated (single-variable boots, raw13–raw27): NVMMU single
vs split windows, three power-domain variants/orders (`ps_ans` +
`ps_apcie_sys_st`, ADT ids 148/150), the 0x1210 IOQ-size write on/off,
pre-shutdown of the ANS in m1n1 (made it worse: ANS BOOT/−62), and the
complete published Gravity recipe. The driver matches Gravity's known-
good combination item for item.

Open suspects, roughly ranked:

1. Whether Linux's CC write lands at all (read-back on the failure
   path) — next test.
2. Mailbox IRQ order: the DTS carries 1003,1004,1005,1006; the J604
   ADT lists 1004,1003,1006,1005 (pairs swapped).
3. The RTKit crashlog (sections Cstr/Cver/Cmbx/Ctim/Crg8 in this tree)
   has not been decoded yet.
4. Firmware: this Mac runs system FW 27.0; all public success is on
   26.6.2. A DFU restore would test it but wipes the machine — last
   resort.

If you know ANS2 on T8132, or spot what a laptop does differently from
the mini here, issues and patches are very welcome.

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
