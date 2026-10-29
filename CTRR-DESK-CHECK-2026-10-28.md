# CTRR desk check — 2026-10-28 (no boot, desk only)

## 0. Linear-map base — corrected, not assumed

- Config: VA_BITS_52, CONFIG_ARM64_16K_PAGES=y (~/linux-asahi/.config).
- Config PAGE_OFFSET for 52 bits is 0xFFF0000000000000 (arch/arm64/include/asm/memory.h:
  PAGE_OFFSET = -(1 << VA_BITS)), but the RUNNING kernel does NOT use that base.
- Evidence from the boots themselves: the Oops header in every run prints
  "swapper pgtable: 16k pages, 47-bit VAs" (run 3 photo, legible), and every
  fault VA starts with ffff8000. For VA_BITS_MIN=47 (16K pages, VA_BITS>48),
  _PAGE_OFFSET(47) = -(1 << 47) = 0xFFFF800000000000.
- Effective linear-map base used here: 0xFFFF800000000000.
  Fault offset = fault VA trailing 8 hex digits (the low 32 bits as printed).
- Transcribed VAs in earlier run notes carry an extra leading "f" (17-18 chars,
  impossible as a 64-bit address); the comparable part is the trailing digits,
  verified against photos for run 3 and the bisect (see section 3).
- DRAM base (m1n1 log, every run): 0x10000000000, size 0x400000000 (16 GiB).
  Usable memory starts at 0x10002780000 in every run.
  Physical fault address = 0x10000000000 + offset (memstart = DRAM base).

## 1. CTRR ranges — from the patch, not memory

Source: ~/git/j604-linux/patches/m1n1-ctrr.diff (m1n1 v2.0.0-dirty, kboot.c only).

- CTRR_C: 48 KiB at top_of_kernel_data (patch comment). Range per run:
  [top_of_kdata - 0xC000, top_of_kdata).
- CTRR_D: 912 KiB = 0xE4000, "the other secondary-core window and ends at
  the m1n1 image base" (patch comment + README). Range per run:
  [m1n1_base - 0xE4000, m1n1_base).
- Patch comment, in substance: on T8132/T8140 iBoot leaves the CTRR
  range "writable only from the boot CPU"; the stock reservation is skipped
  when Apple sysregs are unlocked, "but the range stays enforced on secondary
  cores, so reserve it here regardless of the sysreg gate."
- The DTB Linux actually received in the adoption runs (run 6 prepared-pre.dtb,
  fdtdump) has only three /memreserve/ entries: m1n1 image, boot_args/top,
  and the FDT itself. There is NO CTRR_D (and no CTRR_C) memreserve in it.
  I.e. the proxy m1n1 that prepared that DTB did NOT reserve CTRR_D for Linux.

## 2. Per-run comparison (m1n1 base from each run's own linux-boot.log)

| Run | Fault offset | m1n1 base | CTRR_D range | Inside CTRR_D? | Dist. below m1n1 base |
|-----|--------------|-----------|--------------|----------------|-----------------------|
| 1 | 0x420c000 (66.0 MiB) | 0x426c000 | 0x4188000-0x426c000 | YES | 0x60000 (384 KiB) |
| 2 (retry) | 0x5a3c000 (90.2 MiB) | 0x5aac000 | 0x59c8000-0x5aac000 | YES | 0x70000 (448 KiB) |
| 3 (flagflip) | 0x4f9c000 (79.6 MiB) * | 0x4ffc000 | 0x4f18000-0x4ffc000 | YES | 0x60000 |
| 4 | 0x58d8000 (88.8 MiB) | 0x5938000 | 0x5854000-0x5938000 | YES | 0x60000 |
| 6 | 0x55f4000 (86.0 MiB) | 0x5654000 | 0x5570000-0x5654000 | YES | 0x60000 |
| Bisect (non-adoption) | 0x46c8000 (70.8 MiB) | 0x4728000 | 0x4644000-0x4728000 | YES | 0x60000 |

Physical fault addresses = 0x10000000000 + offset (e.g. run 6: 0x100055f4000,
which is exactly the end of the ADT phram region in run 6's DTB:
adt@0x10005570000 size 0x84000 ends at 0x100055f4000 — the first page after
ADT, still inside CTRR_D).

* Run 3 correction: earlier run notes transcribed run 3's VA as
  "...0041f9c000" (offset 0x41f9c000, 1055 MiB — the apparent outlier that
  broke Grok's "~66-89 MiB" cluster). Re-reading the run 3 photo at 3x zoom,
  the VA line legibly reads "ffff800004f9c000" (offset 0x4f9c000). With that
  correction run 3 fits the pattern exactly (0x60000 below m1n1 base, inside
  CTRR_D). The 0x41f9c000 transcription is wrong and should not be used.
  Grok's "~66-89 MiB" cluster is therefore also wrong as a range: the true
  cluster is 66-90 MiB in offset, but the invariant is not the absolute
  offset — it is "0x60000 below that run's m1n1 base", because m1n1 base
  itself shifts per run (0x426c000, 0x4728000, 0x4ffc000, 0x5654000,
  0x5938000, 0x5aac000).

CTRR_C check: no fault offset falls in any run's CTRR_C range
([top_of_kdata-0xC000, top_of_kdata); e.g. run 6 top 0x60d0000, CTRR_C
0x60c4000-0x60d0000, fault 0x55f4000 is far below). The hit is CTRR_D only.

Other reserves in run 6's DTB for reference: ramoops@0x10300000000 size
0x100000 (far above all faults); m1n1 image reserve 0x5654000-0x5a14000
(run 4's fault 0x58d8000 also falls inside the m1n1 IMAGE reserve as printed
for run 6, but that reserve is run-6-specific — the per-run invariant that
holds for all six runs is CTRR_D, not the m1n1 image reserve).

## 3. Verdict: SMOKING GUN for CTRR_D

- 6 of 6 faults (after the run 3 transcription correction) land inside
  that run's own CTRR_D window, 5 of them at exactly m1n1_base - 0x60000.
  That cannot be allocator coincidence: the buddy is handing out a page in
  CTRR_D, and a secondary CPU (fault CPUs were 5, 6, 7 — never CPU 0, the
  boot CPU) writing to it (clear_page / copy_page during init page-fault
  handling) faults with ESR 0x9600004f, Level 3 permission fault,
  "write to read-only memory" — exactly the CTRR secondary-core enforcement
  described in the patch comment.
- This also explains why the fault is independent of adoption (bisect
  reproduces it), independent of the init binary's size (Go vs small init
  both fault if the allocator hands them a CTRR_D page), and why VAs vary
  per run (m1n1 base shifts per run, so CTRR_D shifts with it).
- Grok's desk-check idea is therefore CONFIRMED, with two corrections:
  (a) the base is the 47-bit effective PAGE_OFFSET 0xFFFF800000000000, not
  the 52-bit config PAGE_OFFSET and not an assumed 48-bit one without
  evidence — the 47-bit evidence is the Oops pgtable line itself;
  (b) the invariant is relative to m1n1 base, not an absolute 66-89 MiB band.

## 4. Fix this points at (reservation/DTB, not kernel bisect)

- Linux must be told CTRR_D is reserved, so the buddy never hands it out.
  Options, in order of cleanliness:
  (a) Boot through the CTRR-patched m1n1 (m1n1-ctrr tree / m1n1-ctrr.diff)
      instead of the stock proxy, so kboot_prepare_dt adds the CTRR_D
      memreserve to the DTB Linux receives. Verify the resulting DTB
      actually carries the reserve before booting Linux on it.
  (b) If the proxy cannot be changed, add the CTRR_D memreserve to the DTB
      passed to Linux by the boot tool (linux.py / producer DTB preparation),
      computed per-boot from that boot's m1n1 base (it shifts per run, so a
      hardcoded range is wrong).
  (c) Add CTRR_D to the kernel DTB reserved-memory as a stopgap — same
      per-boot shift caveat applies if m1n1 base moves; (a)/(b) are better
      because they derive the range from the live CTRR_D sysregs.
- What NOT to do next on this evidence: a blind kernel bisect, a 4K-pages
  kernel as the primary fix, or blaming the Go init — none of those address
  a reserved range the kernel was never told about. The C10 reboot (step 1)
  remains useful as a control (did the Oct 12 stack avoid CTRR_D, and why?),
  but it is no longer the primary fix path: the reservation fix is.
