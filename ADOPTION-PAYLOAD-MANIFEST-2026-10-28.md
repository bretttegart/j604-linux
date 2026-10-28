# Adoption RAM-boot payload — manifest, 2026-10-28 (draft, untested on hardware)

Branch: `adoption-ram` in `~/git/j604-linux` (base 1cefd1b). No push.
No hardware boot, no LabOS enrollment, no NVMe writes were performed
for this build. The preserved proxy binary was NOT rebuilt or replaced:
`~/m1n1-upstream/build/m1n1.bin` still hashes to
`dfdb3bfa56e7f5266f0e4c3c1fa27a61c03d2ec921e7771ae1aabaf7dce23dfd`.

## Commits

- `b0fd76b` Adoption producer: RUNNING (not quiesced) Option A handoff,
  E5 diff documented — `ADOPTION-2026-10-28.md`,
  `scripts/prepare-adoption.py`, `diagnostics/m1n1-adoption.patch`.
- `e27723c` Adoption consumer: adopt-running RTKit path, no
  INIT/HELLO/EPMAP before first I/O — `scripts/apply-kernel-adoption.py`,
  `patches/linux-adoption-2026-10-28.diff` (applies on top of the
  October C9 kernel tree, base 77cb8f2 + its uncommitted C9 diffs).

## Build logs (sunki, `~/j604-boot/adoption-build/`)

- `baseline-kernel.log` — baseline build, exit 0 (before any adoption
  change; proves the toolchain/kernel path still works).
- `adoption-kernel.log` — patched kernel build, exit 0.
- `m1n1-adoption.log` — adoption producer m1n1 build, exit 0.
- `kernel-oct-snapshot/` — the three October kernel sources before the
  adoption patch (the diff baseline).
- `C9-PREP-ADOPT/` (sibling dir) — disposable C9 + adoption m1n1
  source copies and the generated `m1n1-adoption.patch`.

## Payload (`~/j604-boot/adoption-build/payload/`)

| File | Bytes | SHA-256 |
|---|---|---|
| `Image.gz` | 2956710 | `610eeedc27f4b7a1c3168e87c3d838a5fb16751968c458857749c507061cea39` |
| `t8132-j604-ramoops.dtb` | — (October DTB, unchanged by this patch) | `d7091e7449a92d8ca62d6c4613cff8fe0ae86451d4e81af52c5eb56e1d84dc01` |
| `initramfs.cpio.gz` | 1030592 | `f2d99d8c39782308e4b92488d7e6c057b6890ef42faacf14467189f96532a941` |
| `m1n1-adoption.bin` (producer, NOT enrolled) | 3932160 | `2bf344d672ad0e835b1758f68a6b7c35d9c4accd20c50222c981ec393a17f4ef` |

Verified in the built kernel (decompressed strings): `ADOPT-PRE`,
`ADOPT-OK`, `ADOPT-POST`, `ADOPT-PRE-FAILED`, `ADOPT-OFFERED`,
`ADOPT-REFUSED`, `ADOPT-SKIP-SHUTDOWN`, and
`RTKit: adopting already-running session (no INIT/HELLO/EPMAP sent)`.
Verified in the producer binary: `C9-ADOPT` variant tag and the
`ADOPT: retain running ANS` strings. The producer binary is larger
than the preserved proxy (3,932,160 vs 3,866,624 bytes) because it
carries the C9 diagnostic instrumentation; it is delivered via the
proxy as a diagnostic stage, never enrolled over the preserved proxy.

## Recommended run command (untested, for the hardware session)

Producer first (via proxy op `0xf06`, after the E5 prep pattern of
init → five checked reads → restart → five checked reads, LBAs
0, 1, 2, 128, 4096), then RAM boot via `linux.py` with a command line
including `j604.test=ADOPT` (selects the initramfs `testStorage` path:
wait for `/dev/nvme0n1`, require 4096-byte blocks, read the five LBAs,
compare SHA-256, no unbind, no sleep):

```
idle=nop nokaslr loglevel=8 console=tty0 fbcon=nodefer j604.test=ADOPT
```

## What still has to be proven on hardware (not proven by this build)

- That the producer's arm check passes: IOP + AP power ON after reads
  (guess G1). If it refuses, dump the power states; do not weaken it.
- That `j604,ans-live` properties survive the FDT handoff (guess G3) —
  check for `ADOPT-OFFERED` in the kernel log.
- That adoption proof is complete: `ADOPT-PRE` + `ADOPT-OK` +
  `ADOPT-POST` with identical SART masks, plus the producer trace tail
  with no SLEEP/stop/reset/free, plus initramfs `READS MATCH`.
- Open, unchanged: T8132 NVMMU/linear-doorbell placement (C9 mapping
  reused), syslog/crashlog re-request behaviour, AP-ON follow-up
  variant, adopted-session shutdown path, DMA ownership on abort.
