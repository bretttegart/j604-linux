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

## CORRECTION NOTE (evening, Oct 28) - VA transcriptions and the bisect conclusion

Run-3 fault VA, verified from the photo at zoom: ffff800004f9c000 (16 hex digits), NOT the earlier transcription 0041f9c000, which produced a fake 1056 MiB outlier. Transcribed VAs in earlier notes in this file carry an extra leading f (17 digits, impossible as a 64-bit address); region analysis in the evening section uses trailing-digit offsets. The bisect section conclusion that varying VAs prove the defect is timing/layout-dependent, NOT a fixed mapping defect, is SUPERSEDED by the CTRR_D finding in the evening section: the defect is a fixed protected region (CTRR_D) with variable allocations inside it, plus a per-run m1n1 base shift. What the bisect correctly proves, and still proves, is narrower: adoption is not required for that observed Oops failure. It does not establish independence from NVMe initialization, DMA, the bootloader, or other shared changes - and in fact the root cause turned out to be a shared DTB reservation defect. GitHub auth note, resolved Oct 28, 18:35-18:41 (supersedes the UNRESOLVED status in the status section below): sunki's key IS registered; Muse's sunki session has no agent for the passphrase-protected private key, so GitHub's Permission denied (publickey) is misleading. Brett pushes himself; a deploy key or agent change is Brett's call, never unilateral.

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
## EVENING, Oct 28 — CTRR_D smoking gun, reserve boots, and four refutations

No "eliminated" label is used below unless the evidence logically
excludes it. Claims are marked webcam-only vs Brett-photo-confirmed;
Brett's phone photos supersede webcam frames everywhere.

### 1. CTRR_D smoking gun (desk check, 18:50)

Full desk check: CTRR-DESK-CHECK-2026-10-28.md in this repo.

- Effective linear-map base is `0xFFFF800000000000` (47-bit VAs per the
  Oops header "swapper pgtable: 16k pages, 47-bit VAs"), NOT the 52-bit
  config PAGE_OFFSET `0xFFF0000000000000`. DRAM base `0x10000000000`
  (16 GiB); physical fault = DRAM base + VA trailing offset.
- CTRR ranges from the patch itself (patches/m1n1-ctrr.diff, m1n1
  v2.0.0-dirty, kboot.c only): CTRR_C = 48 KiB at top_of_kernel_data,
  `[top - 0xC000, top)`; CTRR_D = 912 KiB = `0xE4000`,
  `[m1n1_base - 0xE4000, m1n1_base)`. Patch comment: iBoot leaves the
  range "writable only from the boot CPU"; stock reservation is
  skipped when sysregs are unlocked, "but the range stays enforced on
  secondary cores, so reserve it here regardless."
- The DTB Linux received in the adoption runs (run 6
  `prepared-pre.dtb`, fdtdump) had NO CTRR_D and NO CTRR_C memreserve
  — only m1n1 image, boot_args/top, FDT. The proxy m1n1 never told
  Linux CTRR_D was reserved.
- Per-VA verdict: 6 of 6 faults inside that run's own CTRR_D window,
  5 at exactly `m1n1_base - 0x60000` (run offsets: run 1 base
  0x426c000 fault 0x420c000; run 2 base 0x5aac000 fault 0x5a3c000,
  -0x70000; run 3 base 0x4ffc000 fault 0x4f9c000; run 4 base 0x5938000
  fault 0x58d8000; run 6 base 0x5654000 fault 0x55f4000; bisect base
  0x4728000 fault 0x46c8000). Fault CPUs were 5/6/7 — never CPU 0 (the
  boot CPU). Mechanism: the buddy allocator hands out a CTRR_D page;
  a secondary CPU writing it (`clear_page`/`copy_page` in init
  page-fault handling) faults ESR `0x9600004f` — exactly CTRR
  secondary-core enforcement. No fault in any CTRR_C range. This
  explains adoption-independence, init-binary independence, and
  per-run VA variation (m1n1 base shifts per run, CTRR_D shifts with
  it). Grok's absolute "66–89 MiB" band is wrong as an invariant —
  the invariant is relative to that run's m1n1 base.

### 2. C10 reboot attempt BLOCKED (18:53), no Linux ran

Image re-verified (hash/size match Oct 12); method resolved as
embedded `.bin` via proxy chainload
(`~/bootloader/proxyclient/tools/chainload.py -r`), NOT linux.py.
Failure verbatim: `RuntimeError: Chainload image
0x10004e84000..0x10005c5c000 overlaps protected range
0x100058f4000..0x10005900000`. Cause: today's proxy m1n1 base
`0x10004e84000`, top_of_kernel_data `0x10005900000`; chainload.py
guards the 48 KiB CTRR_C region and refuses any image ending past it;
today's total region is 14.5 MiB (8 MB image + SEPFW + preoslog +
bootargs) vs a base-to-protected gap of only 10.75 MiB
(top-base constant `0xa7c000`); Oct 12's total region was only
7.8 MiB. Growth is in SEPFW/preoslog handling in current
chainload.py and/or today's firmware (unknown mBoot-20457.41.3 today
vs 27.0 / mBoot-20457.1.29 on Oct 12) — not investigated further; a
reboot to proxy alone does NOT fix this (gap is constant). Mac stayed
at the proxy (no reboot needed). Options not taken: retry chainload
with `-n/--no-sepfw`, or diff Oct 12 chainload.py vs current.

### 3. CTRR-RESERVE BOOT, non-adoption (19:01–19:08): PID 1 SURVIVED

Route chosen (Brett, 18:57): per-boot DTB memreserve (reversible,
boot-specific) — NOT replacing the enrolled proxy with CTRR-patched
m1n1 (separate, later decision).

- This run's m1n1 base read query-only, twice: `0x10004e84000`.
  CTRR_D computed `[0x10004da0000, 0x10004e84000)`, size `0xE4000`.
- Augmented DTB SHA-256 `8ea91c18…`, dtc round-trip adding exactly
  one line `/memreserve/ 0x10004da0000 0xe4000;` vs original
  `d7091e74…` (memreserve map empty); DTS diff = only that line in
  both directions; memreserve map bytes = one entry + terminator;
  size 35390 (+16). Non-overlap vs this boot's allocations verified:
  kernel `0x10010048240..0x1001031a003`, DTB load `0x1001031a040`,
  Kernel_base `0x10010400000`, initramfs `0x10030400000`, final FDT
  `0x10007f38000` — all above CTRR_D end. Residual gap (stated, not
  hidden): the proxy's own in-memory FDT edits are not directly
  observable from the host; the DTB file is verified, behaviour is
  the check.
- Boot: kernel #33 (`6c78e8b8`), initramfs `1057580b…`, augmented
  DTB, NO adoption, cmdline without `j604.test`. Host log:
  "Preparing to boot kernel at 0x10010400000 with fdt at
  0x10007f38000", jump confirmed. Recording: cam-boot.mkv 201 MiB,
  285.7 s, finalized.
- Cross-check (agent checked, did not assume): Brett's 4 photos
  (19:02) ARE from this boot — webcam 60s/90s frames show LOGPAGE
  3/3 CRC `48BAB139` identical to his third photo; panel format /
  logpage header match Go init source `~/git/j604-linux/init/
  c9_status.go` (cell defaults to "C9 UNLABELED" with no `j604.test=`
  word; testStorage runs by default, waits for /dev/nvme0n1,
  direct-reads 5 blocks).
- Result: Go /init ran to panel `C9 UNLABELED / PASS / DIRECT MATCH
  5 OF 5 / NAMESPACE YES / ANS BR NA / ANS CRASH NO / RESET NONE /
  BOOT F78AE613 / PHASE READS MATCH / ERROR NONE`; logpages 1/3 CRC
  `7809910E`, 2/3 `9062BB9B`, 3/3 `48BAB139`; NO Oops on any
  photographed page/frame. Pre-fix fault would have been at
  base-0x60000 = `0x10004e24000`, inside CTRR_D; none appeared.
- Reframe: non-adoption NVMe enable/namespace worked here, so
  earlier -19/CSTS failures were adopted-controller-path-specific,
  not general NVMe failure.
- Limits: "no Oops" proven only up to the last photographed screen
  (Brett's 19:02 reboot ended the boot); whether the display was
  cycling or stopped at 3/3 is not proven; there is no 4th logpage.

### 4. ADOPT+RESERVE BOOT (~19:17–19:28): ADOPT-POST REPRODUCED

- This boot's m1n1 base re-read query-only, twice:
  `0x1000560c000` (shifted +0x788000 from the reserve run after the
  reboot — reserve run's base/DTB NOT reused). CTRR_D computed
  `[0x10005528000, 0x1000560c000)`, size `0xE4000`. Pre-fix fault
  would have been at `0x1000554c000`, inside CTRR_D; none appeared.
- Augmented DTB SHA-256
  `e4e901977615cba74a578c6345879fe81a25c6e84c76cf2106451b5c2abfc5e02`,
  dtc round-trip, only the memreserve line vs original `d7091e74…`;
  size 35390 (+16). Non-overlap vs this boot: kernel
  `0x10010830240..0x10010b02003`, DTB `0x10010b02040`, Kernel_base
  `0x10010c00000`, initramfs `0x10030c00000`, final FDT
  `0x100086c0000`.
- Critical implementation detail: the augmented DTB was used for
  BOTH the producer input and the linux.py input, because
  `kboot_prepare_dt` uses `fdt_open_into`, which preserves existing
  memreserve entries and then adds its own — passing the original
  DTB to linux.py would have lost the CTRR_D reserve at the second
  prepare.
- Producer: chainload of `payload/m1n1-adoption.bin` from the
  enrolled preserved proxy, exit 0, "Proxy is alive again", enrolled
  proxy NOT replaced. Producer script (repeat pattern, first +
  restart read sets kept): reads A == B == probe hashes, 9 retained
  ranges, 163,840 bytes. Arm 0xf06 return 1; trace C9_ADOPT_ARM
  index 403 result 1, c=0xde71ce55. The producer script then failed
  at phase=adopt-dt with `ValueError: subsection not found` in its
  hand FDT parser — the known host-side parser bug; its
  `host-result.json` "PREPARING" status is misleading. The
  `prepared-adopt.dtb` written before the parse was verified offline
  with dtc: memreserve entries include first `0x10005528000` size
  `0xe4000` (CTRR_D, preserved through producer prepare), plus
  m1n1 image `0x1000560c000` size `0x3c0000`, DTB
  `0x100086c0000`, all 9 retained ranges; `/chosen`:
  `j604,ans-live = 1`, controller-state `"disabled"`, boot-status
  `0xde71ce55`, sart-mask `0x5f`.
- Boot: kernel #33, initramfs `1057580b…`, reserve-augmented DTB,
  cmdline with `j604.test=ADOPT`. RAM-only, reads only. Recording
  cam-boot.mkv 96 MiB, 183.6 s, finalized; frames 30–180 s
  extracted.
- Verdict (webcam frames; Brett's photos supersede): ADOPT-OFFERED /
  PRE / OK (frame-90s, LOGPAGE 1/3): ADOPT-PRE `cpu=00000010
  bst=de71ce55 sart=01ff cc=00474000 csts=00000000`; inherited
  endpoints 0x01/0x02 marked discovered (no STARTEP);
  "ADOPTING ALREADY-RUNNING SESSION (NO INIT/HELLO/EPMAP SENT)";
  ADOPT-OK RET=0 ADOPTED=1. ADOPT-POST (frame-100s, LOGPAGE 2/3):
  `ADOPT-POST cpu=00000010 bst=de71ce55 sart=01ff cc=00460001
  csts=00000001` — CSTS RDY=1, CFS clear, same CC as run 6 —
  enable SUCCEEDED, second independent ADOPT-POST; run 6 was NOT a
  fluke. Repeated "RTKIT: RECEIVED SYSLOG MESSAGE BUT NO
  SYSLOG_MSG_BUFFER" lines on pages 2/3 (adoption-mode syslog path;
  producer session consumed SYSLOG_INIT) did not block enable.
  Panel (frame-45s): cell ADOPT / PASS / DIRECT MATCH 5 OF 5 /
  NAMESPACE YES / ANS BR NA / ANS CRASH NO / RESET NONE / BOOT
  C2E1747E / PHASE READS MATCH / ERROR NONE. Oops: none on any
  sampled frame (logpages 1/3, 2/3, 3/3 cycling — 45 s panel, 55–60 s
  page 3/3, 80–110 s page 1/3, 100 s page 2/3, 180 s page 1/3; NOT
  frozen, unlike the run-6 repeat). "No Oops" proven only up to the
  last sampled frame (180 s); Mac was still in the Linux boot at
  recording end.
- Brett's photos of this boot arrived 19:36: LOGPAGE 3/3 CRC
  `AE495444` (syslog-no-buffer line), LOGPAGE 1/3 (ADOPT-OFFERED,
  ANSCHK, ADOPT-PRE, inherited endpoints, ADOPT-OK, NVME-RB/TCB
  with ASQ_TCB `00000100038BC000` in the photo; the agent's webcam
  CRC reading for page 1/3 was `012CCF41` — the photo is
  authoritative for exact digits where they differ), LOGPAGE 2/3
  CRC `0552EBCE` with ADOPT-POST `cpu=00000010 bst=de71ce55
  sart=01ff cc=00460001 csts=000001` legible. Note: logpage 1/3 CRC
  in his photo reads `812CCF41` vs agent webcam frame `012CCF41`
  — first-digit difference, ADOPT-POST line itself matches exactly,
  so confirmation stands. Brett rebooted to proxy 19:36.
- Meaning: (a) CTRR_D reservation hypothesis CONFIRMED in adoption
  mode as well as non-adoption — with CTRR_D reserved, PID 1
  survives AND adoption enable succeeds. (b) Run 6 ADOPT-POST
  reproducibility CONFIRMED (at this point). (c) Remaining open is
  NOT enable or PID 1 at this point: (i) what the Go init does
  after READS MATCH in ADOPT mode (currently it cycles panel /
  logpages; an interactive shell / disk-write path is a separate
  step), and (ii) making the reserve durable.

### 5. REPEAT adopt+reserve boot: FAILED, stability NOT confirmed

Brett-photo-confirmed (logpages 1/2 CRC `80B537C9`, 2/2 CRC
`68A5AF84`).

- Base `0x10005f74000`, CTRR_D `[0x10005e90000, 0x10005f74000)`,
  reserve correctly applied and verified, arm return 1,
  C9_ADOPT_ARM index 409 result 1, ADOPT-OFFERED/PRE
  (cc=00474000)/OK, TCB all zero (admin `0x0000010002DF8000`, io
  `0x0000010002E04000`), then DEVICE NOT READY CSTS=0x2, SNAP2
  cc=00460001 csts=00000002, RESET -19, NO ADOPT-POST, no Oops on
  either photographed page, no Go panel reached.
- Conclusion: stability NOT confirmed; reserve fixes Oops/PID1 but
  does NOT by itself explain enable; enable is flaky. Brett
  rebooted to proxy 20:46 and chose a different approach: offline
  donor-comparison investigation (no boot) to explain flaky enable
  before any further hardware test.

### 6. Astra critique of 23caaf6 (Oct 28)

Four donor differences (RTKit reception order, CC.SHN handoff,
inherited-buffer handling, writeq vs paired 32-bit writes), none a
proven root cause; narrowed overstated 'eliminated' labels
(different fault addresses do not exclude a fixed reservation
defect; non-adoption Oops does not prove independence from
NVMe/DMA/bootloader/shared changes; register readback does not
prove programming correct; tiny init passing would not identify
Go's ELF layout as the cause); 17-digit VA transcription flag;
recommendations (baseline, donor integration, platform isolation,
log retrieval, one-decision-per-run). Response: corrections
accepted, logging/baseline points accepted, full reorganization
NOT adopted because the CTRR_D fix changed the state under review.
Note: Astra reviewed 23caaf6, which predates the CTRR_D desk check,
reserve boots, and adopt+reserve boot — several of its cautions
were already acted on, and some of its "do not conclude" points
were later resolved by new evidence, not by argument.

### 7. Donor comparison (offline)

Full review: DONOR-COMPARISON-2026-10-28.md in this repo (485
lines, sources cited, gaps marked unverified).

- Verified: Aurora `apple_nvme_writeq()` uses `lo_hi_writeq` when
  `needs_ioq_registers` is set, with the comment that post-M4 ANS
  "consumes the queue and NVMMU TCB base addresses as paired
  32-bit registers" matching firmware/m1n1/U-Boot sequence. Pro's
  `w64lh()` is the same idea (two 32-bit stores, low then high).
- Pro's `l1_ans_leave()` verified: delete IO queues, CC.EN=0,
  explicitly no CC.SHN, bounded RDY-clear wait, no RTKit power
  message, no PMGR, CPU_CONTROL untouched, SART entries stay.
- Aurora's inherited-buffer validation is real and strict
  (page-by-page reserved/linear-map/SART-region checks, memremap +
  DMA map, reject if DMA address ≠ firmware identity IOVA). J604's
  version just SART-allows the preset IOVA and leaves the CPU
  buffer pointer NULL.
- Two corrections to Astra: (1) `c9_ctrl_shutdown()` is
  producer-side m1n1, not a Linux call — it's in
  `diagnostics/m1n1-adoption.patch`'s `nvme_adopt_handoff()`
  (delete SQ/CQ, shutdown, disable, then arm gate). Its exact
  register writes were NOT verified in a fetched m1n1 source.
  (2) Aurora's "prepares adopted state before mailbox reception"
  claim was NOT located in the fetched Aurora rtkit.c — the
  inherited flags are consumed in rx handlers there, but their
  setters live elsewhere in the Aurora tree (unfetched). The
  structural difference is real; Astra's phrasing of it is
  unverified.
- One error in J604's own note: `ADOPTION-2026-10-28.md` claims
  paired lo-hi access is "already handled" by the IOQ writes. The
  patch contains ZERO `lo_hi_writeq` occurrences — all six address
  writes (ASQ, ACQ, ASQ_TCB, IOSQ_TCB pre-enable; IOQ_CMDS/CQES
  post-enable) are plain `writeq`, even though J604's `t8132_hw`
  sets `needs_ioq_register = true`, the exact condition under
  which Aurora switches to lo-hi.
- Ranked hypotheses: (1) plain `writeq` to 32-bit-only post-M4 ANS
  address registers intermittently mis-delivered/latched —
  MEDIUM. Only hypothesis with an explicit donor hardware comment,
  a J604 code fact in the opposite direction, and a genuinely
  intermittent mechanism. It fits the one hard fact nothing else
  fits: SNAP2 CC is identical (00460001) in success and failure —
  only CSTS differs (RDY=1 vs CFS=1) — so this is firmware
  reporting a fatal status, not a missing CC write.
  Counter-evidence stated plainly: two successes used plain
  `writeq`, so it's intermittent, not deterministically broken.
  Run-5 readback does NOT refute it: readback reads the register
  file, not what ANS's consumer latched. (2) Producer SHN leaves
  sticky firmware shutdown state — MEDIUM-LOW. ADOPT-PRE CC
  (00474000) decodes to SHN_NORMAL still set at handoff, cleared
  by Linux before enable — so SHN alone can't be sufficient (both
  successes went through it too). (3) RTKit message arriving
  before `adopt_running()` marks its endpoint — LOW-MEDIUM. Real
  race (mailbox starts at probe, endpoints marked only later in
  reset_work), but syslog messages are ACKed even without a buffer
  in J604, and syslog spam appeared in a success; no management
  message is evidenced in any failure photo. (4) No-retry
  amplifying a transient CFS — structural fact, not a cause.
  Enable failure goes straight to probe failure (-19); there's no
  second attempt in a boot. (5) Inherited-buffer handling — LOW
  for CFS, MEDIUM as later-phase debt. Run 4 already showed
  buffer-serving working while enable still failed, and the repeat
  photos show no buffer-request lines at all. (6) Enable timeout,
  DMA/SART collision, AP-ON, queue order — LOW each. Enable waits
  a CAP-derived timeout, not a short fixed deadline, and failure
  is CFS, not bare slowness; CAP.TO itself is never printed
  (cheap missing observation). AP-ON is weak because the producer
  arm gate requires IOP+AP ON and returned 1 in the repeat.
- Log retrieval: ramoops is configured (PSTORE_RAM=y,
  PSTORE_CONSOLE=y, 1 MiB reserved at `0x10300000000`, no overlap
  with boot load addresses) but survival across Brett's actual
  manual-reboot return-to-proxy path and any proxy-side read-back
  are both UNVERIFIED. Cheapest check: boot a kernel printing a
  unique marker, return to proxy the usual way, attempt a
  proxy-side physical read of that region and grep for the
  marker. USB EEM (Air/J713) is not assumed — nothing for J604 is
  built or verified there, and it's larger work than the ramoops
  check.
- Donor-branch timing (from the donor report): start it now in
  parallel as source-only, do not boot it yet. Port as a
  reviewable diff (not a wholesale import): Aurora's writeq
  wrapper, inherited-buffer validation, and the CFS adopt-gate
  (noting that gate would NOT have changed any run so far, since
  ADOPT-PRE CSTS was 0 throughout — it's safety, not a fix), plus
  RTKit inherited flags — keeping J604 addresses,
  `j604,ans-live` names, Option A, and the `0x485cc0000` NVMMU
  window explicit. (Not executed Oct 28; see standing state.)

### 8. LO-HI TEST: REFUTED as sole cause (Brett-photo-confirmed)

- Exactly four writeq → lo_hi_writeq in
  `apple_nvme_reset_work()` (ASQ, ACQ, ASQ_TCB_BASE, IOSQ_TCB_BASE;
  include already present at line 19, no duplicate added;
  post-enable IOQ writes left plain writeq; producer SHN
  unchanged; initramfs/cmdline unchanged). Diff:
  patches/linux-lohi-2026-10-28.diff in this repo.
- Build gates passed (detached, EXIT=0, Image.gz `cc9dd230`,
  2,956,920 bytes, apple.o rebuilt 20:59 after 20:58 edit, 7 ADOPT
  strings).
- Boot: base `0x10005044000` (read twice), CTRR_D
  `[0x10004f60000, 0x10005044000)`, augmented DTB `5c02beac…`,
  reserve verified, producer arm return 1, C9_ADOPT_ARM index 388
  result 1 (first producer attempt failed at trace-pointer op
  `0xf04` "Bad Command" because enrolled proxy alone does not
  implement adoption ops — adoption m1n1 chainloaded first, base
  unchanged, reserve DTB stayed correct).
- Result: logpages 1/2 CRC `7186905B`, 2/2 CRC `CA642ABB` (both
  exact-match in Brett's photos), ADOPT-OFFERED/PRE/OK, TCB all
  zero, then DEVICE NOT READY CSTS=0x2, SNAP2 cc=00460001
  csts=00000002, RESET -19, NO ADOPT-POST, panel ADOPT WAIT 0/5
  RESET -19 BOOT 810D523D, no Oops to 280 s.
- Conclusion: lo-hi alone does not fix enable (could still be a
  contributing factor, or the failure could be intermittent on
  top of it — but lo-hi alone does not fix enable). Enable score
  with reserve after this test: 1/3; overall 2/9.

### 9. SHN-FREE PRODUCER TEST: REFUTED as sole cause (Brett-photo-confirmed)

- Producer source verified first:
  `C9-PREP-ADOPT/m1n1-local/src/nvme.c`, `nvme_adopt_handoff()`
  (line 577); `c9_ctrl_shutdown()` is `nvme_ctrl_shutdown()` in
  `bootloader/src/nvme.c:207` — mask32 CC, SHN field =
  SHN_NORMAL, wait for CSTS SHST == DONE; `c9_ctrl_disable()` then
  clears CC.EN and waits RDY clear. So at handoff CC previously
  carried SHN_NORMAL (the 0x4000 bit in ADOPT-PRE CC 00474000).
- Edit (copied tree `m1n1-shnfree`, original untouched): dropped
  `c9_ctrl_shutdown()` from the handoff condition, so the
  sequence is delete SQ, delete CQ, disable only — no CC.SHN,
  bounded RDY-clear wait, no RTKit power message, no PMGR,
  CPU_CONTROL untouched, SART entries stay. Diff vs original
  `nvme.c`: one condition line + a 3-line comment, nothing else.
  Diff: patches/m1n1-shnfree-2026-10-28.diff in this repo.
- Producer build gates: detached build, EXIT=0, no warnings /
  errors. New producer `m1n1-adoption-shnfree.bin` SHA-256
  `35a2a824dae3f1b59a4ff4c3cc1b14cf7a179040717e72c41c032dfe4540ed42`
  (3,932,160 bytes, same size as original `2bf344d6`, which is
  preserved in `payload/m1n1-adoption-orig.bin`).
- Kernel back to #33 `6c78e8b8` plain writeq (lo-hi NOT booted,
  NOT reverted in-tree — the booted file is the verified #33
  file, so lo-hi is not a variable).
- Boot: base `0x10004850000` (read twice), CTRR_D
  `[0x1000476c000, 0x10004850000)`, augmented DTB `119fb62d…`,
  reserve verified, producer arm return 1, C9_ADOPT_ARM index 402
  result 1, a=CC=`0x470000` (SHN bit 0x4000 CLEAR, vs 0x474000 in
  all previous runs — variant demonstrably applied, and the
  0x4000 CC delta is now identified as SHN_NORMAL).
- Result: logpages 1/2 CRC `2B6A2432`, 2/2 CRC `11C4AB69` per
  agent / `11C4AB68` as photographed (last-digit difference,
  lines match), NEW line "RTKIT: MESSAGE TO UNDISCOVERED
  ENDPOINT 0x02", ADOPT-PRE CC=00470000 (SHN NOT set), ADOPT-OK,
  TCB all zero (admin `0x0000010002E04000`, io
  `0x0000010002E10000`), then DEVICE NOT READY CSTS=0x2, SNAP2
  cc=00460001 csts=00000002, RESET -19, NO ADOPT-POST, panel NOT
  OBSERVED in sampled frames (300–580 s, cycling — do not treat
  as a panel verdict), no Oops to 580 s.
- Conclusion: SHN alone does not explain enable. Enable score
  with reserve after this test: 1/4; overall 2/10.

### 10. RTKit race investigation (offline)

Full review: RTKIT-RACE-INVESTIGATION-2026-10-28.md in this repo
(351 lines).

- CORRECTION — the undiscovered-endpoint line was NOT new in
  SHN-free: grep shows it in run 2 (0x02 then 0x01) and run 3
  (0x01, and 0x02 earlier) as well as SHN-free, all failures; not
  reported in run 4, run 6 (success), adopt+reserve (success),
  lo-hi (failure), or the repeat (failure); run 1 status unknown
  (no run-note file). Tally known-status: 3/7 failures, 0/2
  successes — neither necessary nor sufficient.
- RX path: `apple_rtkit_rx` (rtkit.c ~600–625) prints the warning
  then STILL allocates work and queues it on the ordered
  workqueue, dispatching by endpoint regardless of bitmap —
  message is NOT dropped; any "dropped therefore CFS" theory
  contradicts this code directly.
- Handlers by type: SYSLOG LOG (type 5) warns no buffer but still
  sends ACK; BUFFER_REQUEST (type 1) with adopted==false returns
  -EINVAL, prints failed buffer request (-22), clears buffer,
  sends NO reply (the one early-message path with a withheld
  reply); CRASHLOG CRASH would set crashed + reset — no run shows
  a crash line.
- Endpoint numbering correction: 0x02 = SYSLOG, 0x01 = CRASHLOG
  (rtkit.c 19–27) — reverse of loose earlier descriptions.
- Reception starts at probe (rtkit_init sets mbox->rx then
  mbox_start, recv IRQ enabled); endpoints marked only in
  adopt_running() (rtkit.c 886–906, set_bit 0x01+0x02, no STARTEP)
  from reset_work (apple.c 1177, adopted=true at 1179) — window
  is real, but early-queued work can execute after adopt_running,
  so early arrival does not imply early handling.
- No driver path gates enable on syslog/crashlog state (enable
  path reads only CC, CSTS, BOOT_STATUS, SART mask; CFS is
  firmware-set) — any causal link must be firmware-side,
  inference not verified code, and failure is immediate CFS not
  timeout.
- Why SHN-free showed it: timing coin-flip + photographed-window
  filtering, not a SHN mechanism (runs 2–3 showed it WITH SHN;
  SHN-free photos contain NO -22 line, leaning toward an ACKed
  LOG rather than a refused BUFFER_REQUEST — not proof of type).
- Aurora: rtkit.h @ d266c703 documents
  `apple_rtkit_init_adopted()` ("system endpoints marked
  available", no HELLO/EPMAP) and
  `init_adopted_with_buffers()` ("previous owner's system buffers
  installed BEFORE mailbox RX starts") plus hold_rx() /
  resume_rx(), and syslog_inherited / crashlog_inherited /
  oslog_inherited flags in rtkit-internal.h — BUT definitions of
  init_adopted / hold_rx and any assignment of inherited flags
  to true were NOT found in Aurora rtkit.c at d266c703 (only
  syslog_inherited=false inside syslog_rx_init), no separate
  adopted file in drivers/soc/apple at that commit — design
  intent documented, implementation NOT verified code, do not
  cite as such. Pro l1_ans_leave (1280–1350): no Linux-side
  pre-marking, expects full INIT/EPMAP which adoption skips;
  confirms post-handoff syslog/crashlog traffic is normal /
  continuous.
- Causality: LOW-MEDIUM overall, LOW for SHN-free — real race
  and correctness debt, best read as timing marker not prime
  suspect; promoting it would repeat the lo-hi/SHN pattern.
- Three layers, not one fix: (i) undiscovered warning = bitmap
  state probe→adopt window; (ii) syslog-no-buffer = LOG after
  adopt whose SYSLOG_INIT geometry Linux never saw; (iii)
  inherited-buffer validation = BUFFER_REQUEST handling, fixed
  post-adopt by run 4 SART-allow but still refused pre-adopt via
  adopted==false.

### 11. PRE-MARK TEST: NARROW THEORY REFUTED (Brett-photo-confirmed)

- Change — `apple_rtkit_init()` gains bool premark_inherited;
  when true, after bitmap_zero + set_bit(MGMT) and BEFORE
  `apple_mbox_start()`, set_bit(CRASHLOG) + set_bit(SYSLOG) +
  dev_info "pre-marked discovered before mbox_start (no
  STARTEP)"; other callers pass false; NVMe passes
  `anv->adoption_offered` (set from /chosen `j604,ans-live` +
  controller-state "disabled" before rtkit_init call);
  adopt_running() keeps existing set_bit calls; lo-hi reverted
  (4 writes back to plain writeq); no buffer-handling change.
  Diff: patches/linux-premark-2026-10-28.diff in this repo.
  NOTE on the recorded diff file: the run dir's
  `premark-diff.txt` also contains pre-existing EP_UNKNOWN7 /
  system7 hunks unrelated to pre-marking; the pre-mark change
  itself is the rtkit_init parameter + set_bit block + NVMe
  caller (plus the lo-hi revert hunk in the full-tree diff).
- Build gates passed (detached, EXIT=0, Image.gz `753bea58`,
  2,956,925 bytes, apple.o + rtkit.o rebuilt 22:09:53 after
  22:09:14 edits, 7 ADOPT strings + pre-mark string).
- Producer ORIGINAL SHN-carrying `2bf344d6` (not SHN-free).
- Boot: base `0x100055e0000` (read twice), CTRR_D
  `[0x100054fc000, 0x100055e0000)`, augmented DTB `5c02f7c2…`
  (5c02 prefix coincidence with lo-hi DTB, full hash differs),
  reserve verified, producer arm return 1, C9_ADOPT_ARM index 409
  result 1, a=CC=`0x474000` (SHN SET, as expected with original
  producer).
- Result: logpages 1/2 CRC `A96D2E5E`, 2/2 CRC `E20C75E3` (both
  exact-match in Brett's photos), pre-mark line present
  ("INHERITED ENDPOINTS 0x01/0x02 PRE-MARKED DISCOVERED BEFORE
  MBOX_START (NO STARTEP)" — implementation demonstrably took
  effect before RX), ADOPT-PRE CC=00474000, ADOPT-OK, TCB all
  zero (admin `0x0000010002E00000`, io `0x0000010002E0C000`),
  then DEVICE NOT READY CSTS=0x2, SNAP2 cc=00460001
  csts=00000002, RESET -19, NO ADOPT-POST, panel ADOPT FAIL 0/5
  RESET -19 BOOT F48913AC PHASE NO NAMESPACE ERROR NO NVME,
  undiscovered line ABSENT from both sampled logpages, -22
  ABSENT, syslog-no-buffer ABSENT (same window limit), no Oops
  to 420 s.
- Conclusion: narrow theory refuted — bitmap / warning /
  dispatch path does not cause CFS. This does NOT refute the
  broader early-buffer theory (pre-adopt BUFFER_REQUEST refusal
  via adopted==false unchanged by pre-marking); that follow-up
  is a separate decision, NOT combined.
- Enable score with reserve now 1/5 (first adopt+reserve
  success; repeat, lo-hi, SHN-free, pre-mark failures); overall
  2/11. One pre-mark success would in any case not have proved
  stability (base rate 1/4) — moot, since this run failed.

### 12. Standing state at end of Oct 28

- Enable flaky, 2/11 overall, 1/5 with reserve; reserve fixes
  Oops/PID1 (no Oops in 3/3 reserve boots that reached
  userspace/panel stage, plus lo-hi/SHN/pre-mark no-Oops to
  280/580/420 s).
- Remaining open: what Go init does after READS MATCH in ADOPT
  mode (interactive shell / disk-write path is a separate step),
  making the reserve durable (per-boot DTB route works /
  reversible; CTRR-patched m1n1 proxy is a later decision —
  never reuse a previous run's base, it shifts per proxy boot;
  augmented DTB must be passed to both producer and linux.py or
  the reserve is lost at the second prepare), AP-ON follow-up
  variant, adopted shutdown path, broader early-buffer
  (adopted-early) test as the next candidate decision,
  donor-branch staging (source-only, not booted yet),
  log-retrieval verification (ramoops marker check).
- C10 chainload overlap still open. X1 note correction still
  owed (explicit ask only).
- Fast-loop mode remains approved for boots; LabOS-default-boot
  and serial-console changes NOT approved; trivial static init
  and blind kernel bisect / 4K-pages-as-primary-fix are dead
  routes — do not revive. Print-and-halt workflows rejected by
  Brett.
- This commit is LOCAL ONLY on adoption-ram (not pushed by
  Muse — see GitHub auth note above). Brett pushes from his own
  terminal; push command is in the commit message body.

## Status as of late Oct 28, 2026 (evening)

- Branch adoption-ram, local commit in this update (see log);
  main untouched at 1cefd1b.
- Mac state at commit time: /dev/m1n1 ABSENT on sunki (Mac still
  in the pre-mark Linux boot at the time of this update; Brett
  had not yet rebooted to proxy when the update was written).
  Reboot to proxy is pending Brett's action, as usual.
- Next decisions for Brett: adopted-early buffer test vs
  donor-branch staging vs log-retrieval marker check — none
  started by this commit.
