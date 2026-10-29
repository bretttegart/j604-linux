# Live-session adoption runs, 2026-10-28 (Mac16,1 / T8132 / J604)

RAM-only adoption tests. Producer: m1n1 patch, proxy op 0xf06, arms only if
the ASC CPU is RUNNING with IOP+AP power ON. Default handoff: RUNNING, not
quiesced; Option A only (controller DISABLED, queues deleted, ANS running;
Linux creates fresh queues). Forbidden before first I/O: INIT, HELLO,
HELLO_REPLY, EPMAP renegotiation, STARTEP for inherited endpoints, AP/IOP
power renegotiation, SLEEP, PMGR reset, SART/buffer reallocation.
Full contract: adoption-handoff-contract-2026-10-28.md (workspace copy).
Payload baseline for runs 1-6: m1n1-adoption.bin 2bf344d6, DTB d7091e74,
run-2 initramfs 1057580b (rebuilt hash table). Kernel patch snapshot for
runs 4-6: patches/linux-adoption-full-2026-10-28.diff in this repo.

## Run 1 — adoption proven, enable failed

ADOPT-OFFERED (controller-state=disabled), ADOPT-PRE, and ADOPT-OK
(ret=0, adopted=1) with no INIT/HELLO/EPMAP sent. Then NVMe RTKit
"failed buffer request for 0x5000 bytes (-22)"; "Device not ready;
aborting initialisation, CSTS=0x0"; probe removed -19 before any
identify/read. ADOPT-POST absent (printed only after nvme_enable_ctrl()
succeeds). Separate Oops after probe failure: PID 1, swapper/0,
clear_page, write to read-only memory. Initramfs READS verdict not
applicable (no namespace).

## Run 2 — retry, explicit OFFERED, CSTS 0x2

Same adoption lines, now with ADOPT-OFFERED explicit. Probe failed again:
messages to undiscovered endpoints 0x02 then 0x01; "Device not ready",
CSTS best-read 0x2. Oops reproduced in kind but not identically (init
PIDs 116/115, userspace fault path). READS not applicable.

## Run 3 — flag-flip test: hypothesis 1 killed as sufficient, test valid

Single variable: .separate_nvmmu_region = false -> true in
apple_nvme_t8132_hw (apple.c:1934). Write-proof: built vmlinux T8132
struct bytes [1,1,1,0,64]; diff exactly one line; all TCB writes use
mmio_nvmmu mapped by-name "nvmmu" (probe fails otherwise); DT nvmmu reg
0x485cc0000; probe proceeded past alloc; new kernel Image.gz 9545ec20,
kernel #29, provably booted. No runtime register readback (deliberately
skipped to keep the test single-variable).
Result: ADOPT-OK repeats, yet enable still failed: "Device not ready,
CSTS=0x2", NVME-SNAP2 cc=00464001 csts=00000002 (EN set, CFS set, RDY
clear — fatal status, not a silent timeout). Wrong-window TCB writes are
NOT the sufficient cause. Flag flip kept as baseline, not reverted.
Oops, third form: PID 1 init via load_elf_binary, copy_highpage,
VA fffff8000041f9c000.

## Run 4 — buffer serving: hypothesis 2 killed as sufficient

Variant, on top of the flag flip, buffer serving only: adopted-mode-only
SART-allow of a preset IOVA in apple_nvme_sart_dma_setup() (reply path
uses iova/size only), endpoint bits 0x01/0x02 set in
apple_rtkit_adopt_running() with NO STARTEP, plus a NULL-buffer guard.
Result: "Inherited endpoints 0x01/0x02 marked discovered (no STARTEP)",
NO "failed buffer request for 0x5000 bytes (-22)" line — both fix halves
demonstrably worked — yet enable still failed: CSTS=0x2, NVME-SNAP2
cc=00460001 csts=00000002, reset failure -19. Buffer serving alone is
not the sufficient cause. Oops, fourth form: after /init started,
VA fffff8000058d8000. READS not applicable.
Build note: the first run-4 detached build (Image.gz f3e6ef53) was
INVALID (x86_64 .config from an un-ARCHed make/olddefconfig, no NVMe
driver, 0 ADOPT strings) and was never booted. Build 2 (9749c46b) was
verified (EXIT=0, hash matches disk, rebuilt objects, ADOPT strings)
on a restored October snapshot config before booting. Lesson: hash
alone is never a build gate.

## Run 5 — pre-enable NVMMU readback: registers-misprogrammed killed

Variant: read-only NVME-RB dump immediately before nvme_enable_ctrl().
Every programmed register matched its intended value exactly:
NUM_TCBS 63, ASQ_TCB_BASE 0x000001000b9dc000,
IOSQ_TCB_BASE 0x000001000b9e8000, TCB_STAT 0, LINEAR_SQ_CTRL 1,
AQA 0x00010001, ASQ 0x000001000b9d8000, ACQ 0x000001000b9d4000,
doorbells 0, CC/CSTS 0 pre-enable (after disable_ctrl; this does not
contradict the ADOPT-PRE cc=00474000, read before the disable).
Enable still failed: CSTS=0x2, SNAP2 cc=00460001 (same as run 4),
reset -19, ADOPT-POST absent, READS not applicable. Registers as
programmed are not the problem.
The "two log pages rotating" seen during this run was a post-boot log
display cycling LOGPAGE 1/2 (CRC 7B967394) <-> 2/2 (CRC CE86EF30), not a
pre-enable loop. No Oops line was visible on either log page; that does
not prove no Oops occurred later in run 5.

## Run 6 — TCB-contents dump: FIRST ADOPT-POST

Variant: read-only NVME-TCB dump before enable. Admin base
0x000001000b9dc000 and I/O base 0x000001000b9e8000, 64 entries each,
bytesum 0, nonzero bytes 0, first nonzero entry -1, entries [0]-[3]
all zero — the expected pre-enable state for unpopulated queues, not a
bug finding on its own.
Then, first time in six runs:
"ADOPT-POST cpu=00000010 bst=de71ce55 sart=01ff cc=00460001
csts=00000001" — CSTS RDY=1, enable SUCCEEDED. Followed by "passthrough
uses implicit buffer lengths" and "Alternate GPT is invalid, using
primary GPT" (namespace/block scan reached GPT parsing).
Remaining blocker: Oops, fifth form, after /init started:
write to read-only memory at fffff8000055f4000, PID 1 init, kernel
7.1.9-g77cb8f24c230-dirty #33, pc copy_page, lr copy_user_highpage,
trace copy_page -> copy_user_highpage -> handle_mm_fault ->
do_page_fault -> do_translation_fault -> do_mem_abort. Userspace never
ran, so READS is still not applicable.
Why enable succeeded this time is UNPROVEN. Live hypotheses only:
dump-read side effect, printk delay/timing, build/config delta.
None is presented as fact. Run-6 kernel: Image.gz
6c78e8b8f494c4e48e1dd1b88e9153017610db41bc6f13ef84a38cb206ddf029.

## Run-6 repeat — INCONCLUSIVE (hung at log page 1)

Identical payload (Image.gz 6c78e8b8, same initramfs/m1n1/DTB/cmdline),
producer armed, page 1 of the log display reached (LOGPAGE 1/2, CRC
2AF94F1A; readback/TCB matching intended, with new per-boot allocation
addresses asq_tcb 0000010002dfc000 / iosq_tcb 0000010002e08000), then
stuck on page 1 for 10+ minutes. A keypress produced no response,
ruling out an input-waiting viewer. Page 2 never appeared; no enable
outcome was observed — neither ADOPT-POST nor CFS. The repeat neither
confirms nor refutes run 6's ADOPT-POST. Run 6 remains a single,
unconfirmed data point.

## Non-adoption Oops bisect — Oops reproduces WITHOUT adoption

Control boot: no m1n1-adoption chainload, no 0xf06, no retained ranges,
DTB d7091e74 with 0 ans-live strings, cmdline without j604.test=ADOPT,
same run-6 kernel and initramfs (session mode the only variable).
Result: Oops, same fault class — write to read-only memory, Level 3
permission fault, ESR 0x9600004f, kernel 7.1.9-g77cb8f24c230-dirty #33,
after "Run /init as init process" and before any userspace code. NVMe
enable outcome in this boot was not resolved (early lines illegible at
webcam resolution) and does not affect the verdict.
Photo confirmation (Brett's phone photo, which supersedes the webcam
reading of CPU 6 / copy_page): CPU 5, PID 1, Comm init, fault VA
fffff8000046c8000, pc clear_page+0x30/0x68, trace clear_page ->
folio_alloc -> handle_mm_fault -> do_page_fault (translation /
mem-abort tail cut off in the frame). This is a different entry point
from run 6's copy_page / copy_user_highpage, but the same fault class,
during init ELF loading.
VA comparison conclusion: the bisect VA 0046c8000 differs from run 6's
0055f4000, run 4's 0058d8000, run 3's 0041f9c000, run 2's 005a3c000, and
run 1's 00420c000. VAs vary across runs, so the defect is
timing/layout-dependent, NOT a fixed mapping defect. This strengthens
(does not change) the bisect verdict below.
Conclusion: the shared-state explanation (adopted reservations
corrupting later MM) is killed as necessary. The Oops is an independent
kernel/MM defect, and is the live track.

## Hypotheses status

- Wrong-window TCB writes: KILLED as sufficient (run 3).
- Inherited buffer serving: KILLED as sufficient (run 4).
- Registers misprogrammed: KILLED (run 5, intended-vs-observed match).
- TCB contents wrong: NOT supported as a cause (run 6, all zero as
  expected pre-enable) — and enable succeeded in that same boot.
- Adopted-reservation corruption as Oops cause: KILLED as necessary
  (non-adoption bisect reproduces the Oops).
- Enable success cause in run 6: UNPROVEN (see above).
- Oops cause: OPEN — independent kernel/MM defect in the init
  ELF-loading / page-fault path.

## Next steps, in order (one variable each)

1. Same kernel (6c78e8b8), trivial static init (print + halt, or the
   Oct 3-era initramfs that reached userspace). If it runs clean, the
   fault tracks the current Go /init ELF mapping, not the kernel alone.
2. If the trivial init also Oopses, kernel bisect: pre-adoption
   October baseline kernel, then page-size/config variants, with
   CONFIG_ARM64_16K_PAGES=y as the first config suspect for a
   copy_highpage fault.
3. Separately, after the Oops track moves: retry the run-6 repeat to
   confirm ADOPT-POST reproducibility. Enable and Oops are now proven
   to be independent blockers.

## Status as of 18:36 MDT, Oct 28, 2026

- Push: commit 8be4185 was pushed by Brett from his sunki terminal at
  18:34 MDT; branch adoption-ram is live at
  github.com/bretttegart/j604-linux/tree/adoption-ram.
- GitHub auth discrepancy (UNRESOLVED, neither side settled): Muse's
  sunki session offers only sunki's local key (SHA256:6G0rx...,
  btega@fedora, no agent) and GitHub rejects it with publickey denied,
  while Brett's terminal push succeeded. Brett states sunki's pubkey is
  already registered on GitHub. Distinguishing test pending, not yet
  run: `ssh -o IdentitiesOnly=yes -T git@github.com` on sunki. This
  note does not claim sunki's key is unregistered, nor that agent
  forwarding caused Brett's push — both are unverified.
- Pending decisions / state: the trivial static init test (same kernel,
  print + halt, or the Oct 3-era initramfs) is the recommended next
  boot, awaiting Brett's tap on the options widget (unanswered as of
  18:36 MDT). At photo time the Mac was still in the bisect boot,
  frozen at the Oops header; reboot to the proxy was pending Brett's
  action, and /dev/m1n1 was still absent on sunki at this update, so
  the Mac had not yet returned to the proxy.
