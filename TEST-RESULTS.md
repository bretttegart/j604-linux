# J604 ANS review test results

> **Post-handoff review, Oct 7:** Original operator records below are preserved.
> See the [post-audit plan](POST-SHUT-AUDIT-PLAN-2026-10-07.md) for the next
> experiment and [the A/B follow-up](FOLLOWUP-2026-10-07.md) for the earlier
> corrections: the successful namespace capacity is **500,277,792,768 bytes**
> (`977105064 * 512`), not the displayed 4 TB. A/B have the same observed
> failure outcome; missing early B pages prevent claiming identical protocol
> traces. Client 0's sentinel does not establish a NAND role or absence of
> NAND access. The IOP-ACK timeout does not establish that it caused the
> firmware crash. TETHER-A2 is the current control; BASE-0 remains an
> unisolated failure. No additional hardware test was run for this review.
> [Next diagnostic test](POST-SHUT-AUDIT-PLAN-2026-10-07.md) exposes the
> unknown RTKit crashlog sections and Linux cold-reset chronology. Avoid an
> IOP OFF request for now: the Linux RTKit source documents OFF as
> non-restartable, while SLEEP is restartable.

Plan: [Muse runbook](MUSE-RUNBOOK.md). Evidence and hypotheses:
[2026-10-07 review](REVIEW-2026-10-07.md).

No new hardware tests were performed when this file was created. Update each
row with the observed result; a planned outcome is not a test result.

| Case | Purpose | Status | Evidence directory / key observation |
|---|---|---|---|
| BASE-0 | Frozen existing payload, saved tethered m1n1 | INCOMPLETE | ans-review-n6miVhGq/BASE-0/ — old init painted NVME-SNAP2 snapshot (CC2 00460001 / CSTS 00000002 STO 0); no nvme0n1 string seen; namespace/read unconfirmed; Brett photo 14:50:40 MDT shows full RTKit crashlog dump during this tethered boot (Csta/Cnvr unknown sections, Client 0 ring initialized s=41600) |
| TETHER-A | Common diagnostics and current frozen m1n1, direct Linux load | PASS | TETHER-A2 photos: ANSBR 3, namespace PRESENT (lbs 4096, 977105064 sectors, 4002222342144 B), GPT EFI PART OK, read x3 ALL MATCH sha256 7640546f91198e68.., FIRST CRASH NONE |
| CHAIN-A | Instrumented original cold path after SSD stage load | FAIL (cold crash reproduced with full trace) | CHAIN-A/run1 photo PXL_20261007_214944757: ANSBR 2 cold path; boot epmap completed; RTKDIAG boot iop ack ret=-62 (-ETIME); ANSCHK post ret=-62 cpu=00000010 bst=00000000 run=0 crashed=1; Client 0 ring uninitialized |
| CHAIN-B | Identical chain with T8132-only explicit IOP INIT | FAIL — identical to CHAIN-A | CHAIN-B/run1 photos (pager PAGE 1/69 + flood tail): ANSBR 2, CPU_CONTROL 00000010, BOOT_STATUS 00000000, namespace ABSENT, first crash [295] RTKit co-processor has crashed, final status -62; RTKDIAG boot iop ack ret=-62; Client 0 ring uninitialized |
| CHAIN-A2 | Return to A if B succeeds | CONDITIONAL, NOT RUN | |
| CONTROL-REPEAT | Exact TETHER-A recipe repeated (FOLLOWUP section 1) | PASS | bootid 7e0c4240-725c-46d0-8b00-e19bccb77ede; ANSBR 3; namespace PRESENT; GPT EFI PART OK; read x3 ALL MATCH sha256 7640546f91198e68..; FIRST CRASH NONE; 836 kmsg lines, 0 gaps |
| SHUT-AUDIT (run 1) | Audit stage1 -> unchanged stage2 A | FAIL (Linux side) | identical to CHAIN-A: boot iop ack ret=-62, ANSCHK crashed=1, Client 0 sentinel; bootid 38a5cd3c..; stage1 screen not photographed |
| SHUT-AUDIT (run 2) | Same audit stage1 rerun for SHAUD capture | FAIL (Linux side) | SHAUD fully captured: every shutdown transition OK (see section); Linux bootid 29231573.. |
| CRASHLOG-DIAG-A | Audit stage1-cd -> stage2-crashlog-diag-a (kernel C) | NO VERDICT (boot wedged) | Linux froze >4 min at post-helper-boot tail; never reached pager; power-cycled by operator |
| A-CONTROL2 | Audit stage1 -> unchanged stage2 A (repeat control) | FAIL as expected | bootid 1d0a2a64-ba58-4747-95a0-08f01b1d26ee; ANSBR 2; namespace ABSENT; FIRST CRASH [295]; FINAL RESET ERROR [837] -62; 2229 lines, 0 gaps; pager reached ~100 s after chainload |
| CRASHLOG-DIAG-A2 | Audit stage1-cd2 -> stage2-crashlog-diag-a2 (kernel C2) | NO VERDICT (boot wedged, same as C) | SHAUD clean again (S12 +774ms, HOLD); Linux froze at post-helper-boot tail >2 min; never reached pager |
| CRASHLOG-DIAG-A3 | Audit stage1-cd3 -> stage2-crashlog-diag-a3 (kernel C3) | boot completes to pager (ANS still FAIL as expected) | bootid b50aca37-aca1-494f-9894-20effdb53f06; crashlog unknown sections identified: 'Cnvr' 0x40 payload x2, 'Csta' 0x20 payload x4; boot iop ack ret=-62 as before |
| CRASHLOG-DIAG-A4 | C3 + restored unknown-section content dump | Pager reached; ANS still FAIL | Photos: PAGE 1/76, ANSBR 2, namespace absent, first crash [299], final -62 [1026], 2492 lines/0 gaps. Video: 77 pages/2498 lines, reset snapshots ret=0, PC=d24c8 ESR=be000000 (SError), Ccst task=12, CasC/Crtk also present. Six Cnvr/Csta tail payloads captured (256 bytes); not the full unknown-section inventory. Footer diagnostic offset 0x4bc0, size 0x4be0. See C4-VIDEO-REVIEW-2026-10-09.md. |
| CRASHLOG-DIAG-A5 | C4 + compact crashlog structure/version/footer diagnostics | Pager reached; ANS still FAIL | One send 13:04:03 MDT, C5-RUN-20261009T130403-0600. PAGE 1/79: ANSBR 2, namespace absent, first crash [325], final -62 [1061], 2581 lines/0 gaps. Ccst task 14 maps to power (C4 task 12 maps to Cmd); PC 19a4f0, ESR low32 be000000; CasC packed words repeat 49f008000; raw Cver RTKit_release-3514.0.15.release. Rejected 32-byte footer is CLHE, flags 0x0a misread as section length. Nikon capture retained; host exit 1 after handoff. See C5-SESSION-2026-10-09.md. |

| CRASHLOG-DIAG-A5-REPEAT | Unchanged C5 after fresh LabOS firmware identity capture | Pager reached; ANS still FAIL | One send 14:24:17 MDT. Boot ID 9f24e8f4-a15d-4c48-a068-62eac9c56bc7; ANSBR 2, no namespace, first crash [299], final -62 [1063], 2587 lines/0 gaps. Cver base c0c000 vs first C5 184000; all ten normalized frames identical. Task 14 power, ESR low32 be000000, FAR 49f008000; l2c_adr upper bits differ. See C5-REPEAT-SESSION-2026-10-09.md. |
| CHAIN-B2 / B3 | Repeat successful B on fresh boots | CONDITIONAL, NOT RUN | |

Post-C5 acquisition is complete: all 185 collected-file checksums pass;
Apple's 27.0.1 T8132 ANS container matches the signed SFR ANS digest.
Fresh LabOS's chosen manifest is byte-identical to SFR/current and its
live __TEXT matches the candidate except six startup metadata bytes.
[The repeat](C5-REPEAT-SESSION-2026-10-09.md) validates C5's runtime
mapping across two boots. Fault-address translation remains unresolved.
No firmware was flashed; the complete-26.6.2 restore history is preserved.
[Current plan](NEXT-TEST-AFTER-C5-2026-10-09.md): trace exception context and
address mapping offline, then one targeted diagnostic. No C6 built/sent.

## Per-run record template

### BASE-0 — 2026-10-07 ~14:50 MDT — Muse (operator), Brett (Mac-side)

```text
Case / local date-time / operator: BASE-0 / 2026-10-07 14:50 MDT / Muse via sunki, Brett rebooted Mac to LabOS proxy
Result: INCOMPLETE
Evidence directory: /home/btega/j604-boot/ans-review-n6miVhGq/BASE-0/ (chainload.log, linux.log, screen.mkv)
Exact boot command(s): chainload.py -n -r snapshot/m1n1-known-tethered.bin (timeout 90); then linux.py -b "idle=nop nokaslr loglevel=8 console=tty0 fbcon=nodefer" snapshot/Image.gz snapshot/t8132-j604-ramoops.dtb snapshot/initramfs.cpio.gz (timeout 210)
Starting state (fresh installed proxy, recovery steps): fresh boot into installed LabOS proxy (Brett); ANS state fresh from that boot

Source HEADs and saved dirty diffs: snapshot/{kernel-head.txt,kernel.patch,m1n1-head.txt,m1n1.patch,proxy-head.txt,proxy.patch} in ans-review-n6miVhGq
Kernel config / toolchain / build log: frozen snapshot/kernel.config; no build this case
Stage1 host SHA-256: n/a (no stage1; direct linux.py)
Stage2 host SHA-256: n/a
Stage2 ESP destination SHA-256 and verified path/PARTUUID: n/a (tethered)
Embedded m1n1 / kernel / DTB / initramfs SHA-256: m1n1 c87cf83bc134e8160efe3809076f0a784cfdaab2c1178a1bae8c679506474b86; Image.gz 579aa2273ece14458c0a5bcff9aebdc92494408ff59a063839275668c119226d; DTB d7091e7449a92d8ca62d6c4613cff8fe0ae86451d4e81af52c5eb56e1d84dc01; initramfs 780ed9f82ed3a019c3be45b2180f36d1a8ea30fafc6e94877f700109cbe869fd
Observed j604.test label / kernel version / boot ID: none (old init predates labels); kernel version string 7.1.9-g77cb8f24c238-dirty per review
OS firmware raw mBoot ID: unknown (not captured this case)
System firmware raw mBoot ID: unknown
Separately verified macOS build and LabOS identity, if available: macOS 26.6.2 (25G83) from prior sessions; not re-verified this case

Actual reset-work branch: unknown — old init did not classify ANSCHK (no BR paint)
CPU_CONTROL / BOOT_STATUS / CC / CSTS and sampling phase: NVME-SNAP2 probe snapshot CC=0x00460001 CSTS=0x00000002 (sampling phase = kernel probe print)
SART observations (phase, address/size/flags), if collected: none
Last successful handshake milestone: m1n1 proxy alive after chainload ("Proxy is alive again"); kernel decompress OK (host log)
First error or firmware assertion (exact redacted text): none observed
Final Linux error and timestamp: none observed
Namespace / logical block size / capacity: UNKNOWN — old init found no "nvme0n1" string in its kmsg scan, so no read test ran
Read offsets, sizes, checksum method and results: not run

Host exit status: chainload OK; linux.py 124 (timeout, expected: serial monitor detaches at handoff)
Mac outcome (shell/park/reboot/USB cycling/unknown): init painted verdict, then machine returned to installed LabOS proxy on its own by ~14:52 MDT (screen.mkv 170s+ shows "Running proxy...")
Complete log capture? Missing/truncated portions: host serial ends at kernel handoff (expected); on-screen kernel text during fast scroll is unreadable in webcam frames (known limitation)
Binary crashlog captured? Path/size/hash, or unavailable: unavailable (no crash observed)
Observation: Frozen tethered payload boots Linux and init runs, but the old init's classify fell through to the NVME-SNAP2 register paint instead of confirming the namespace and read result.
Interpretation / confidence: INCOMPLETE per runbook section 2 — the old init hides the measurement. This is not evidence of an enumeration regression; TETHER-A's common init provides the definitive namespace/read measurement.
One proposed next action and its reason: Proceed to kernel A + common init (runbook section 3), then TETHER-A — it measures the same tethered path with unambiguous output.
```

### CONTROL-REPEAT — 2026-10-07 16:13 MDT — exact TETHER-A rerun (FOLLOWUP-2026-10-07 section 1)

```text
Result: PASS — the current tethered control reproduces
Evidence: /home/btega/j604-boot/ans-review-n6miVhGq/CONTROL-REPEAT/ (chainload.log, linux.log, screen.mkv); Brett photos of pager pages 1, 2, 9-22/27
Components (unchanged from TETHER-A): snapshot/m1n1-current.bin 2b0142c4..; A/Image.gz a90386d6..; common DTB d7091e74..; common/initramfs.cpio.gz 04beffe6..
Fresh boot ID: 7e0c4240-725c-46d0-8b00-e19bccb77ede; j604.test=TETHER-A; kernel #27 (2026-10-07 15:03 MDT)
Summary (PAGE 1/27): BRANCH ANSBR 3; NAMESPACE PRESENT /dev/nvme0n1 lbs=4096 sectors=977105064 (capacity line shows the known 8x display bug; true 500,277,792,768 bytes); GPT EFI PART OK at LBA1 offset=4096 sha256(block)=7640546f91198e68..; READTEST x3 ALL MATCH (same hash as first TETHER-A); FIRST CRASH: NONE SEEN; KMSG 836 lines, 0 gaps
Healthy chronology captured (kmsg seq): [246] NVME-SNAP boot=de71ce55 csts=00000000 sart=005f cc=00474000; [248] ANSCHK cpu=00000010 bst=de71ce55 run=0; [260] ANSBR 3; [262] RTKDIAG wake send IOP INIT; [267] wake INIT send ret=0; [269] rx HELLO min=12 max=12 want=12; [274] rx EPMAP bitmap=0x51f base=0 last=0; [278] bitmap=0x3 base=1 last=1; [293-296] crashlog buffer size=8000 iova=0x00001000bcb000; [300] rx IOP_PWR_ACK new_state=0x20; [302] wake -> boot; [315] boot epmap ret=0 boot_result=0; [318] boot iop ack ret=0; [328] rx AP_PWR_ACK new_state=0x20; [333] boot AP ON ret=0
Sequence note: ANSCHK at [248] reads CPU_CONTROL RUN set (0x10) with BOOT_STATUS holding the NVME-SNAP boot value de71ce55 — consistent with branch 3 (previous stage left firmware running). Summary page shows CPU_CONTROL/BOOT_STATUS UNKNOWN (known parser artifact: last ANSCHK line without both fields).
Interpretation: TETHER-A2 control is reliable; per followup, proceed to SHUT-AUDIT. BASE-0 investigation stays deferred.
```

### SHUT-AUDIT — 2026-10-07 16:26 + 16:29 MDT — instrumented stage1 shutdown, stage2 A unchanged

```text
Result: shutdown provably clean end-to-end; Linux still crashes identically to CHAIN-A
Evidence: SHUT-AUDIT/stage1-shut-audit.bin 8d8978c0d0d8c6a76dcc521a82dc34be35ceb361b82309eb0f968c5e53820f14 (prints-only diff source.patch, 39 SHAUD formats, 20 s post-teardown hold); ESP stage2-ans-a.bin e0acf3db.. (loaded from LINUXESP, file size 7614162)
Runs: run 1 16:26 MDT (SHAUD screen missed; Linux bootid 38a5cd3c-04af-4b73-8a1a-0dec63df060e), run 2 16:29 MDT (SHAUD photographed by Brett; Linux bootid 29231573-fdb1-4b03-945b-107e4e50df1f). Linux side identical in both and to CHAIN-A: RTKDIAG boot iop ack ret=-62; ANSCHK post ret=-62 cpu=00000010 bst=00000000 run=0 crashed=1; ANS did not boot; Reset failure status: -62; crashlog sections 436e7672/43737461; Client 0 s=4294967295 (-1), Client 2 s=57600

SHAUD trace (run 2, verbatim values):
  bring-up: ANS on die 0; SARTv3 0x485c50000; rtkit booting version 12; rx iop_pwr_ack 0x20; rx ap_pwr_ack 0x20; nvme initialized at 0x4c5cc0000; stage2 read OK (7614162 bytes)
  S01 shutdown call=1 initialized=1 die=0
  S02 entry CC=0x00470001 CSTS=0x00000001 BOOT_STATUS=0xde71ce55 cpu_running=1
  S03 delete_sq ok=1 +23ms
  S04 delete_cq ok=1 +29ms
  S05 ctrl_shutdown ok=1 CSTS=0x00000009 SHST=2 +520ms
  S06 ctrl_disable ok=1 CSTS=0x00000000 RDY=0 +529ms
  sleep enter ap_cached=0x20 iop_cached=0x20 cpu_running=1 crashed=0
  switch ap_quiesced send=1; rx ap_pwr_ack state=0x10; ap wait ok ap=0x10
  switch iop_target send=1 target=0x01; rx iop_pwr_ack state=0x01; iop wait ok iop=0x01
  switch ok ap=0x10 iop=0x01; sleep switch_result=1
  asc_cpu_stop cpu_control before=0x00000010 after=0x00000000
  S08 sleep ret=0 cpu_running=0 BOOT_STATUS=0x00000000 +665ms
  pmgr_reset(ANS) found=1 ps_actual=15 active=1 ret=0 +701ms (device 0.ANS pulsed)
  pmgr_reset(ANS2) found=0 ret=-1 +716ms (expected alias miss, not a failure)
  S11a-e release rtkit/sart/asc/ioq/adminq; S12 complete +752ms; "nvme: shutdown done"; HOLD 20000ms

Run 2 PAGE 1/69 confirms: BRANCH ANSBR 2; CPU_CONTROL 00000010 BOOT_STATUS 00000000; NAMESPACE ABSENT (no /dev/nvme0n1 after 1m0s wait); FIRST CRASH [296] "RTKit: co-processor has crashed"; FINAL RESET ERROR [842] "Reset failure status: -62"; KMSG 2244 lines, 0 gaps. Same values as CHAIN-B PAGE 1.

Interpretation per FOLLOWUP-2026-10-07 decision table: this is the row "all shutdown operations and actual-device reset succeed, Linux still crashes." Also confirmed on screen: rtkit_sleep's outer return is 0 despite switch_result=1 (the Boolean-as-errno defect, instrumented not fixed) — harmless here because everything succeeded and the CPU was stopped anyway.
State handed to the kernel (measured): controller disabled (CC EN=0, RDY=0, SHST=DONE), AP QUIESCED (0x10), IOP SLEEP (0x01), CPU_CONTROL=0, BOOT_STATUS=0, 0.ANS reset pulse applied, mailbox/SART/queues freed.
Next per the table: capture pre/post Linux reset state and the first firmware assertion; compare the stage1 PMGR reset with the kernel's reset-controller sequence and firmware-memory/SART ownership; change ONE measured difference. Candidate measured difference already visible: the IOP is left in SLEEP (0x01), not OFF — nothing in either stage is proven to clear that internal state across the block reset.
```

### CRASHLOG-DIAG-A + A-CONTROL2 — 2026-10-07 16:51 / 16:57 MDT

```text
CRASHLOG-DIAG-A run (16:51 MDT, fired from fresh LabOS proxy):
  Components: C/stage1-shut-audit-cd.bin 3fbd00a98823938e1fb0fd780f656d10b28d44fb91405a5bd9c1916ac96d698c; ESP /stage2-crashlog-diag-a.bin 065399051d4565f41d54c67cfc38728131f9864abfb3eb32f8c75fde69e2675b (kernel C f9fc63c9883d5c9f99dfa530014556b5cda8a6d69e88b18648c1a14d766f6a1e; same DTB d7091e74..; same common initramfs 04beffe6..; label j604.test=CRASHLOG-DIAG-A)
  Observation: Linux booted (macsmc + rtkit-helper completed HELLO/EPMAP/ACK/AP ON per Brett photo 16:53), then the framebuffer tail stayed unchanged for >4 minutes — no pager, no further prints. A-run pacing reaches the pager ~100 s after chainload, so this is a genuine wedge, not the normal cold-fail silence. Power-cycled at ~16:56. No verdict on crashlog section content (never dumped to screen).
  Suspects (unproven): the new crashlog dump path at first ANS crash, or ANSRST snapshot placement in the branch-2 reset path. Patch reads bounded on paper; requires offline review / a split build to isolate.

A-CONTROL2 (16:57 MDT, per POST-SHUT-AUDIT-PLAN instruction to repeat the unchanged control when diagnostics change the result):
  Components: SHUT-AUDIT/stage1-shut-audit.bin 8d8978c0.. -> ESP /stage2-ans-a.bin e0acf3db.. (kernel A)
  Result: normal cold-fail pacing; PAGE 1/69 photographed: bootid 1d0a2a64-ba58-4747-95a0-08f01b1d26ee; ANSBR 2; CPU_CONTROL 00000010 BOOT_STATUS 00000000; NAMESPACE ABSENT; FIRST CRASH [295]; FINAL RESET ERROR [837] -62; KMSG 2229 lines, 0 gaps.
  Interpretation: machine and harness are healthy; the wedge is specific to the CRASHLOG-DIAG-A component set. Do not interpret the C boot as crashlog evidence.
```

### CRASHLOG-DIAG-A2 — 2026-10-07 17:33 MDT (kernel C2, split test)

```text
Components: C2/stage1-shut-audit-cd2.bin 55ec3e49..; ESP /stage2-crashlog-diag-a2.bin 80104802.. (kernel C2/Image.gz 867f2fa4.. = kernel C minus the unknown-section ASCII/hex content dump); same DTB/initramfs; label j604.test=CRASHLOG-DIAG-A2
SHAUD (photographed): identical clean shutdown (S02 CC=0x00470001 BOOT_STATUS=0xde71ce55; S05 SHST=2 +543ms; AP QUIESCED 0x10 ACK; IOP SLEEP 0x01 ACK; CPU_CONTROL 0x10->0; reset ANS ret=0, ANS2 -1 expected; S12 +774ms; HOLD 20000ms). Stage2 read 7614998 bytes.
Linux: booted macsmc + rtkit-helper fully; framebuffer tail then unchanged >2 minutes — pager never reached (same symptom as CRASHLOG-DIAG-A run 1).
Interpretation: the ASCII/hex content dump is EXONERATED (absent in C2, wedge persists). Shared remaining deltas vs kernel A: (1) ANSRST snapshots in apple.c branch 2, (2) rtkit.c first-crash marker, (3) crashlog bounds checks + unknown-section header line. Prime suspect recorded at the time: the ANSRST "post-assert" and "post-reinit" snapshots read CPU_CONTROL/BOOT_STATUS while the ps_ans block is asserted (device-disable + reset per the DT reset provider) — an MMIO read into a disabled block can stall the CPU instead of returning. C3 removes exactly those two mid-reset snapshots (keeps pre-assert, post-deassert, post-cpu-run) as the single-variable split.
```

### CRASHLOG-DIAG-A3 — 2026-10-07 17:45 MDT (kernel C3 = C2 minus two mid-reset ANSRST reads)

```text
Components: C3/stage1-shut-audit-cd3.bin 8cd6a5e2d93f6308597a298cd81a17ab0130c5aed4b031c9287364ac48b97f3c; ESP /stage2-crashlog-diag-a3.bin 99dfc1ad7775e686e9b318a0f7cd733597ffbdcffe77a676da26512a903868f9 (kernel C3/Image.gz c751cfb4d7ba575921d74026418785e5a3f344148c5f81249296829ea464f4bf); same DTB/initramfs; label j604.test=CRASHLOG-DIAG-A3
SHAUD: clean again (S12 +1019ms; stage2 read 7614499 bytes).
Linux outcome: boot completes to the init pager (no wedge). Cold-fail unchanged underneath: RTKDIAG boot iop ack ret=-62; ANSCHK post ret=-62 cpu=00000010 bst=00000000 run=0 crashed=1; ANS did not boot; Reset failure status: -62. Bootid b50aca37-aca1-494f-9894-20effdb53f06.
Wedge verdict (C/C2 vs C3 split): removing ONLY the ANSRST post-assert and post-reinit snapshots (register reads while the ps_ans block is asserted in reset) cured the freeze. The crashlog content dump is exonerated; the mid-reset MMIO reads are the wedge mechanism on this evidence.

Crashlog walk, new C-family output (verbatim from photos):
  RTKDIAG crashlog first crash notification, crashlog buffer size=8000
  RTKit: Unknown crashlog section: 436e7672
  RTKDIAG crashlog unknown section 'Cnvr' fourcc=436e7672 offset=0x46e0 payload_len=0x40
  RTKit: Unknown crashlog section: 436e7672
  RTKDIAG crashlog unknown section 'Cnvr' fourcc=436e7672 offset=0x4730 payload_len=0x40
  RTKit: Unknown crashlog section: 43737461
  RTKDIAG crashlog unknown section 'Csta' fourcc=43737461 offset=0x4780 payload_len=0x20
  RTKDIAG crashlog unknown section 'Csta' fourcc=43737461 offset=0x4b30 payload_len=0x20
  RTKDIAG crashlog unknown section 'Csta' fourcc=43737461 offset=0x4b60 payload_len=0x20
  RTKDIAG crashlog unknown section 'Csta' fourcc=43737461 offset=0x4b90 payload_len=0x20
  RTKDIAG crashlog malformed section size 0xa at offset 0x4bc0 (crashlog size 0x4bc0)
  RTKit: End of crashlog reached but no footer present
  Client table (id=6675420a): Client 0 wev 0x0 wsz 0 s 4294967295 e 4294967295 ps 4294967294 pe 4294967294; Client 1 s 4294967295; Client 2 s 57600 e 57600; Client 3 s 4294967295; Client 4 s 618 e 618; Client 5 s 98035 e 98040; Client 6 s 896 e 896. Regions 0-8 recorded (Region 0 s 0 e 64 sm 64; Region 1 s 64 e 768 sm 2063; Region 2 s 896 e 12928 lg 188; Region 3 s 12928 e 91328 lg 975; Region 4 s 91328 e 91840 sm 512; Region 5 s 93952 e 98048; Region 6 s 91840 e 92544 lg 11 sm 1408; Region 7 s 92544 e 93952 sm 1408; Region 8 s 768 e 896 sm 128). Ind_MC 270 Ind_C 64.
Notes: (1) payload CONTENTS of Cnvr/Csta are still uncaptured (hex/ASCII dump lives only in wedged kernel C; C4 = C3 + content dump is the safe follow-up now that the wedge cause is isolated). (2) 'size=8000' on the first-crash line vs 'crashlog size 0x4bc0' in the walk terminator are quoted exactly as printed — the walked size (0x4bc0 = 19392) is smaller than the buffer size; not interpreted here. (3) ANSRST pre-assert/post-deassert/post-cpu-run values are in the pager kmsg of this run; pager left running on the Mac at session end — photographable if the Mac stays powered, otherwise recoverable on any C3/C4 rerun.
```

### CHAIN-A — 2026-10-07 15:49 MDT — Muse chainload, Brett photos

```text
Result: FAIL — cold-path crash reproduced with instrumented kernel-side trace
Evidence directory: /home/btega/j604-boot/ans-review-n6miVhGq/CHAIN-A/run1/ (chainload.log, screen.mkv); Brett photo PXL_20261007_214944757
Boot: chainload.py -n -r CHAIN-A/stage1-ans-a.bin from fresh LabOS proxy; stage1 chainloaded /stage2-ans-a.bin from LINUXESP (PARTUUID 6891114B-7C56-4EC1-ABA9-4DC13B3B1DB4)
Components: stage1-ans-a 66df0a5833263395c6abb7ce3e8bb2f60fab14feb1fcfce94bea2fe9e04e99f2; stage2-ans-a e0acf3db6ad6b2eea4c8668a270d5fb76b13c2081a80a7050a5e19e20ae3746a; kernel A a90386d6..; common initramfs 04beffe6..; DTB d7091e74..
Observed j604.test: CHAIN-A (init start banner, bootid 204060f9-9440-4fca-84f0-24eb2b2a722)
Actual reset-work branch: 2 (cold; ANSCHK post cpu=00000010 = CPU RUN set)
Handbook mileposts (kernel A RTKDIAG): endpoint map completed; "RTKDIAG boot wait iop ack" then "RTKDIAG boot iop ack ret=-62" (-ETIME — IOP power ACK never arrived)
ANSCHK post: ret=-62 cpu=00000010 bst=00000000 run=0 crashed=1; final: "nvme nvme0: Reset failure status: -62"
Firmware crashlog (photo): unknown sections 436e7672 (Cnvr), 43737461 (Csta); Client 0 ring UNINITIALIZED (s=4294967295 e=4294967295); Client 2 s=57600; Client 5 s~98035 — firmware started, logged ~57 KB, crashed before NAND ring setup; "RTKit crashed: unable to recover without a reboot"
Namespace: ABSENT (expected on crash)
Observation: In branch 2 the kernel sets CPU RUN and calls apple_rtkit_boot(), which waits for epmap (arrives) and then for an IOP power-state ACK that is never provoked — no SET_IOP_PWR_STATE INIT is sent on this path. The firmware waits, then crashes; the kernel times out with -ETIME.
Interpretation: matches the runbook's explicit-INIT hypothesis. CHAIN-B (branch 2 → apple_rtkit_wake on t8132) sends INIT before the same waits.
One proposed next action: run CHAIN-B exactly as prepared (stage2-ans-b.bin 75b29279.. via ESP, fresh proxy, chainload stage1-ans-b.bin).
```

### CHAIN-B — 2026-10-07 15:54 MDT — Muse chainload, Brett photos

```text
Result: FAIL — identical to CHAIN-A (per runbook decision table)
Evidence directory: /home/btega/j604-boot/ans-review-n6miVhGq/CHAIN-B/run1/ (chainload.log, screen.mkv); Brett photos (pager PAGE 1/69 + crashlog flood tail)
Boot: fresh LabOS proxy; stage1-ans-b chainloaded /stage2-ans-b.bin from LINUXESP
Components: stage1-ans-b e47448f0a90d26fedde09d9d9e0af085d44a175301a8585658a1e7e3182b2f3fb; stage2-ans-b 75b292795c4adc257984db72fddecc67f6a9fbbe8c19c3750d365310ddf60a1a; kernel B 1f81ab6a.. (= A + T8132-only explicit-INIT in branch 2, proven by ab-delta.patch); common initramfs 04beffe6..; DTB d7091e74..
Observed j604.test: CHAIN-B; kernel #27 built 2026-10-07 15:35:06 MDT; bootid 2f31f9d0-5538-4c2b-0ed2-fac27ecf0ea7
Actual reset-work branch: ANSBR 2; summary CPU_CONTROL: 00000010 BOOT_STATUS: 00000000
Namespace: ABSENT (no /dev/nvme0n1 after 1m0s wait); GPT/read tests NOT RUN
FIRST CRASH: [295] nvme-apple 4c5cc0000.nvme: RTKit: co-processor has crashed; FINAL RESET ERROR: [842] Reset failure status: -62
KMSG: 2244 lines retained, 0 gap markers
Crashlog flood tail: unknown sections 436e7672 (Cnvr) x2, 43737461 (Csta); client table: Client 0 ring UNINITIALIZED (s=4294967295 e=4294967295); Client 2 s=57600; Client 4 s=610; Client 5 s=98035..98048; Client 6 s=896; region table identical to CHAIN-A; "RTKit crashed: unable to recover without a reboot"
Kernel mileposts (photo): "RTKDIAG boot iop ack ret=-62" then "ANSCHK post ret=-62 cpu=00000010 bst=00000000 run=0 crashed=1", "ANS did not boot", "Reset failure status: -62"
First divergence from CHAIN-A: none identified at summary/crashlog level — same branch, same registers, same error, same Client 0 state. The early RTKDIAG wake/epmap lines (whether the INIT send returned and whether any SET_IOP_PWR_STATE_ACK arrived) are in the 69-page pager and were not photographed this run.
Interpretation: the T8132-only explicit-INIT change does not change the outcome. The "missing INIT stimulus" hypothesis alone is refuted: with INIT sent via apple_rtkit_wake(), the IOP power ACK still never arrives and the firmware still crashes before initializing the NAND-facing ring (Client 0).
One proposed next action: per runbook decision table — shutdown ACK / reset-state audit: verify clean shutdown ACKs before this cold start (m1n1-side kboot nvme shutdown on the stage chain vs the kernel expectations) and capture the early RTKDIAG wake/epmap/ACK pages from a rerun to localize the first real divergence. Do not repeat the cold chain unchanged.
```



### TETHER-A — 2026-10-07 15:24 MDT — Muse, Mac already at LabOS proxy

```text
Result: INVALID COMPARISON
Evidence directory: /home/btega/j604-boot/ans-review-n6miVhGq/TETHER-A/ (chainload.log, linux.log, screen.mkv)
Exact boot command(s): chainload.py -n -r snapshot/m1n1-current.bin; linux.py -b "idle=nop nokaslr loglevel=8 console=tty0 fbcon=nodefer j604.test=TETHER-A" A/Image.gz common/t8132-j604-ramoops.dtb common/initramfs.cpio.gz
Components: m1n1-current 2b0142c4ce96a4d0; kernel A a90386d6378d0008e094746b92a2aaceaad6ffd3ec39c85f5662298e00cf344d; DTB d7091e7449a9; common initramfs 04beffe61833f3a34b8d4adcaa5e967a319ebf0f6142b880d22af26f1bc98fbd
Observed: "Proxy is alive again" after chainload; kernel+DTB+initramfs loaded; "Decompress OK"; FDT bootargs show j604.test=TETHER-A; serial monitor detaches at handoff (normal). Webcam: screen lit at ~8 s (mean luminance 57.8), dark by ~30 s (29.6), black at 60/120/200/300 s. No kernel text, no init summary, no paging ever rendered. /dev/m1n1 absent afterwards (Linux state, expected).
Interpretation: measurement harness failure, not a driver result (runbook section 6: missing diagnostics → repair measurement/provenance). Failure window is early: between m1n1 handoff and first fbcon output. Suspects in order: new init's /dev/tty0 handling (KDSETMODE path), kernel A early hang, m1n1-current handoff difference.
Next action: single-variable isolation — kernel A + frozen old initramfs + saved tethered m1n1 c87cf83b (identical to BASE-0 except the kernel). If it lights, the new init's display path is broken; if black, kernel A is broken.
```
Amendment 2026-10-07 ~15:45 MDT: the "black screen" was a measurement error on my side — the webcam frames mostly the desk monitor; the laptop display WAS running the pager (Brett confirmed 26 pages at 15:37, then rebooted to proxy before photos). Identical rerun (TETHER-A2, same artifacts) photographed by Brett (PXL_20261007_214349947, _214345343, _214337378):
- PAGE 1/26 summary: j604.test=TETHER-A; kernel 7.1.9-g77cb8f24c238-dirty #27 (clang 21.1.8, built 2026-10-07 15:03 MDT); BOOTID 070ea73f-e470-4e6d-b6b9-949ae5775eb2
- BRANCH: ANSBR 3 (tethered wake path, as designed)
- NAMESPACE: PRESENT /dev/nvme0n1 lbs=4096 sectors=977105064 capacity=4002222342144 bytes (3727.4 GiB)
- GPT: EFI PART OK at LBA1 offset=4096; READTEST: GPT header block read x3 (buffered) ALL MATCH sha256=7640546f91198e68..
- FIRST CRASH: NONE SEEN; KMSG: 827 lines, 0 gaps; PAGE 26 tail shows "nvme0n1: p1 p2 p3 p4 p5 p6" and clean init start
- Init measurement gap (non-blocking): summary CPU_CONTROL/BOOT_STATUS show UNKNOWN — the init's ANSCHK field parse missed the kernel A lines; branch + namespace + read evidence are complete without it.
Verdict: PASS per runbook section 6 (namespace + read/checksum test + complete diagnostics). Kernel A boots and enumerates tethered; no regression from the diagnostics or the m1n1-current handoff. Proceed to CHAIN-A.



Amendment 2026-10-07 ~15:05 MDT (operator photo): Brett's photo PXL_20261007_205040462 (taken 14:50:40 MDT, ~23 s after kernel load) shows a live RTKit crashlog dump during this BASE-0 tethered boot: firmware syslog flood (id=20202020), "Unknown crashlog section: 436e7672" (Cnvr) and "43737461" (Csta), client/region table (id=6675420a) with Client 0 ring INITIALIZED (s=41600 e=41600), and the tail "...crashed: unable to recover without a reboot" (partially garbled by fb double-print). Interpretation: the frozen payload (kernel 579aa227 + tethered m1n1 c87cf83b) crashes the 26.6.2 ANS firmware even when m1n1 pre-boots it — unlike the raw50-era tethered boots (kernel 5b94073c) that enumerated and read fine. The frozen kernel differs from the raw50 kernel by the Gravity EP7 rtkit port and ANSCHK prints; the m1n1 differs too (c87cf83b vs 2b0142c4). TETHER-A (kernel A from frozen source + m1n1-current 2b0142c4 + common init) isolates this with full diagnostics.


Copy this section for each run. Keep raw logs/videos/binaries outside Git;
link their paths and include short redacted excerpts as needed.

```text
Case / local date-time / operator:
Result: PASS / FAIL / INCOMPLETE / INVALID COMPARISON
Evidence directory:
Exact boot command(s):
Starting state (fresh installed proxy, recovery steps):

Source HEADs and saved dirty diffs:
Kernel config / toolchain / build log:
Stage1 host SHA-256:
Stage2 host SHA-256:
Stage2 ESP destination SHA-256 and verified path/PARTUUID:
Embedded m1n1 / kernel / DTB / initramfs SHA-256:
Observed j604.test label / kernel version / boot ID:
OS firmware raw mBoot ID:
System firmware raw mBoot ID:
Separately verified macOS build and LabOS identity, if available:

Actual reset-work branch:
CPU_CONTROL / BOOT_STATUS / CC / CSTS and sampling phase:
SART observations (phase, address/size/flags), if collected:
Last successful handshake milestone:
First error or firmware assertion (exact redacted text):
Final Linux error and timestamp:
Namespace / logical block size / capacity:
Read offsets, sizes, checksum method and results:

Host exit status:
Mac outcome (shell/park/reboot/USB cycling/unknown):
Complete log capture? Missing/truncated portions:
Binary crashlog captured? Path/size/hash, or unavailable:
Observation:
Interpretation / confidence:
One proposed next action and its reason:
```

#### Operator note 2026-10-07 ~16:15 MDT
Corrections in the header above accepted. Next: exact TETHER-A control repeat, then SHUT-AUDIT (instrumented stage1, stage2 A unchanged) per FOLLOWUP-2026-10-07. Separately, a display-only init v2 (block-letter webcam verdict carousel, test logic unchanged, initramfs 80365a9c..) was verified readable from the sunki webcam on its own tethered run (TETHER-V2, carousel showed NVME OK); init v3 repairs (capacity, ANSCHK field retention, full-read checks) will be separately named before use in any comparison.
