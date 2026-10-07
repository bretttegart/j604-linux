# SHUT-AUDIT result — control repeat + stage1 shutdown audit (2026-10-07, Muse)

Follows FOLLOWUP-2026-10-07. Full ledger in TEST-RESULTS.md.

## 1. Control repeat (your section 1)

Exact TETHER-A recipe repeated once — PASS. Fresh bootid 7e0c4240-725c-46d0-8b00-e19bccb77ede, ANSBR 3, namespace present, GPT OK, three reads ALL MATCH (sha256 7640546f91198e68.., same as first run), no crash, 836 kmsg lines 0 gaps. Healthy chronology captured (NVME-SNAP boot=de71ce55, ANSCHK cpu=00000010 bst=de71ce55, wake INIT ret=0, HELLO v12, EPMAP, IOP_PWR_ACK 0x20, AP ON ret=0). Two more tethered passes also observed incidentally today (TETHER-V2 with a display-only init variant; original TETHER-A x2). No reproducibility concern on this side.

## 2. SHUT-AUDIT (your section 2)

Stage1-only instrumentation (`8d8978c0..`, prints + return captures, 39 SHAUD formats, 20 s post-teardown hold, source.patch in the run dir), ESP stage2 A untouched (`e0acf3db..`, loaded 7614162 bytes). Audit build did not change the Linux outcome (no timing-sensitivity flip): Linux side identical to CHAIN-A in two runs (bootids 38a5cd3c.., 29231573..).

SHAUD (all values from the filmed run):

- S02 entry: CC=0x00470001 CSTS=0x00000001 BOOT_STATUS=0xde71ce55 cpu_running=1
- S03 delete_sq ok=1 +23ms; S04 delete_cq ok=1 +29ms
- S05 ctrl_shutdown ok=1 CSTS=0x00000009 SHST=2 +520ms
- S06 ctrl_disable ok=1 CSTS=0 +529ms (RDY=0)
- AP QUIESCED: send=1, rx ap_pwr_ack 0x10, wait ok
- IOP SLEEP 0x01: send=1, rx iop_pwr_ack 0x01, wait ok; switch_result=1
- CPU stop: CPU_CONTROL 0x00000010 -> 0x00000000; S08 BOOT_STATUS=0x00000000 +665ms
- pmgr_reset(ANS): found=1, ps_actual=15 active=1, ret=0 +701ms (0.ANS pulsed); pmgr_reset(ANS2): found=0 ret=-1 (alias miss, expected)
- releases rtkit/sart/asc/ioq/adminq; S12 complete +752ms; "nvme: shutdown done"

Your `rtkit_sleep()` defect is confirmed on screen: switch_result=1 while the outer return prints 0 — harmless in this run (all steps succeeded; CPU stopped regardless), now proven rather than inferred.

## 3. Decision-table outcome

This is your row "all shutdown operations and actual-device reset succeed, Linux still crashes." The state measured at handoff: controller disabled and handshaked (SHST DONE, RDY 0), AP QUIESCED 0x10, IOP **SLEEP 0x01**, CPU_CONTROL 0, BOOT_STATUS 0, 0.ANS reset pulsed, buffers/mappings freed. No failed transition exists on the m1n1 side to repair.

Measured candidate differences for the next single change (your pick):

1. **IOP is left in SLEEP (0x01), never OFF.** Nothing in m1n1's pulse or (from source) the kernel's ps_ans assert/deassert is shown to clear the firmware's internal power state. Variant: stage1 requests IOP OFF (0x00) instead of SLEEP, everything else identical.
2. **Kernel reset-controller sequence vs stage1 pulse.** Kernel A asserts ps_ans (apple.c), writes RUN, boots without INIT and waits for an ACK the firmware never sends post-EPMAP. Comparing that assert/deassert timing/ordering against m1n1's 10us DEV_DISABLE+RESET pulse is a source task I can do host-side next.
3. First firmware assertion still uncaptured (crashlog yields Cnvr/Csta + client table only; assertion text not yet seen). If you want it, say how you'd like it fished out.

BASE-0 remains deferred per your call (control passes, so no reason to open it).

## Harness note (separate track)

A display-only init v2 (block-letter verdict carousel readable from the sunki webcam) was verified on its own tethered run; init v3 repairs (capacity = sectors x 512, ANSCHK field-wise retention, full-read checks, kmsg first/last sequence) will be separately named before use in any comparison.

— Muse, 2026-10-07 ~16:35 MDT


## Addendum — CRASHLOG-DIAG results (2026-10-07 evening, Muse)

Per POST-SHUT-AUDIT-PLAN-2026-10-07. Full detail in TEST-RESULTS.md.

1. CRASHLOG-DIAG-A (kernel C) wedged the boot (~90 s in; never reached the pager). The unchanged audit A control (A-CONTROL2) paged normally, isolating the regression to the C diagnostics.
2. Split test C2 (content dump removed): wedge persisted — the ASCII/hex dump is innocent.
3. Split test C3 (only the ANSRST post-assert and post-reinit register snapshots removed): boot completes to the pager with the usual cold-fail underneath. On this evidence, reading CPU_CONTROL/BOOT_STATUS while ps_ans is asserted (device-disable + reset) stalls the CPU. The surviving ANSRST points (pre-assert, post-deassert, post-cpu-run), the first-crash marker, and the bounds checks are safe.
4. Crashlog unknown sections are now identified by header: 'Cnvr' (0x436e7672), 0x40-byte payloads at 0x46e0 and 0x4730; 'Csta' (0x43737461), 0x20-byte payloads at 0x4780, 0x4b30, 0x4b60, 0x4b90. Walk ends at a malformed 0xa-size stub at 0x4bc0; no footer. Payload bytes still unseen.
5. Proposed next single step: C4 = C3 + the unknown-section content dump restored (safe now that the wedge cause is isolated; sections are small — 64 B and 32 B — so dumps are tiny). One boot yields the actual Cnvr/Csta bytes, the first real candidate for a firmware assertion/state record. Anchors per your decision tree: readable assertion -> one corresponding kernel fix; structured binary -> decode offline before any hardware change.
