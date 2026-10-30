# Donor comparison — why adoption enable is flaky (offline review, no boot)

Date: 2026-10-28 (evening, after the adopt+reserve REPEAT failed).
Scope: NO hardware boot, NO Mac reboot, NO proxy use for booting, NO code
changes, NO repo push. Read-only review of the J604 tree on sunki plus the
public donor sources. This file is the deliverable; the parent agent's
summary carries the ranking and the one recommended test.

## 0. The fact to explain

Adoption enable outcome, all runs Oct 28, same kernel #33 lineage except
where noted, same producer (op 0xf06, Option A: queues deleted, controller
DISABLED, ANS running, no quiesce/sleep/PMGR reset):

- Runs 1–5, NO CTRR_D reserve: enable failed every time. ADOPT-OFFERED /
  PRE (cc=00474000, csts=00000000) / OK present, then DEVICE NOT READY,
  CSTS=0x2 (CFS set, RDY clear), SNAP2 cc=00460001 csts=00000002,
  RESET FAILURE -19, NO ADOPT-POST.
- Run 6, NO reserve: FIRST ADOPT-POST, cc=00460001 csts=00000001 (RDY=1),
  GPT parsing reached, then an init Oops blocked userspace.
- Non-adoption CTRR-reserve boot: PID 1 survived, panel C9 UNLABELED PASS
  5/5, no Oops to last photo.
- Adoption+reserve boot: ADOPT-POST reproduced (cc=00460001 csts=00000001),
  panel ADOPT PASS 5/5, no Oops to 180 s.
- REPEAT adoption+reserve boot (Brett's photos, LOGPAGE 1/2 CRC 80B537C9,
  2/2 CRC 68A5AF84): base 0x10005f74000, CTRR_D [0x10005e90000,
  0x10005f74000), augmented DTB memreserve verified, prepared-adopt.dtb
  preserves it first, arm return 1, C9_ADOPT_ARM index 409 result 1,
  ADOPT-OFFERED/PRE/OK, TCB dumps all zero (admin 0x0000010002DF8000,
  io 0x0000010002E04000) — then DEVICE NOT READY, CSTS=0x2, SNAP2
  cc=00460001 csts=00000002, RESET -19, NO ADOPT-POST, no Oops on either
  photographed page, no Go panel reached.

Score: enable 2/8 overall, 1/2 with reserve, 1/6 without reserve.
With n=2, reserve's effect on enable is indistinguishable from noise.
Reserve's effect on Oops is a separate, strong signal (no Oops in 3/3
reserve boots vs Oops in runs 1–4, 6 and the non-adoption bisect).
"Reserve fixes enable" is DISPROVEN as a complete explanation and is not
re-asserted anywhere below.

The discriminator that matters: SNAP2 CC is IDENTICAL (00460001) in
success and failure. The only differing enable register is CSTS:
RDY=1 (success) vs CFS=1 (failure). So the failure is not "CC was not
programmed" as read back — it is firmware actively reporting a fatal
status after EN is set. Any hypothesis must explain CFS, not just
slowness or a missing write.

## 1. Sources read, and what was NOT verified

Verified in source (read directly):

- J604 patch: `~/git/j604-linux/patches/linux-adoption-full-2026-10-28.diff`
  (1007 lines, base linux-asahi asahi 77cb8f24c; run-6 kernel 6c78e8b8).
- J604 live tree: `~/linux-asahi` branch `asahi` at 77cb8f24c,
  `drivers/nvme/host/apple.c` (reset_work, queue setup) and
  `drivers/soc/apple/rtkit.c` (adopt_running, rx paths), plus
  `drivers/nvme/host/core.c` (nvme_enable_ctrl / nvme_disable_ctrl).
- J604 adoption note: `~/git/j604-linux/ADOPTION-2026-10-28.md`;
  producer patch: `~/git/j604-linux/diagnostics/m1n1-adoption.patch`.
- Aurora linux @ d266c703: `drivers/nvme/host/apple.c` (writeq wrapper,
  can_adopt gate, inherited-buffer validation, handoff contract) and
  `drivers/soc/apple/rtkit.c` (inherited flags consumed in rx handlers).
  NOTE: the browser rendering of these files collapses newlines, so no
  Aurora line numbers are cited here — function names and file paths
  only. Aurora's reset/enable sequence itself could NOT be fully
  verified from the fetched view (the view truncates mid-file and
  contains no nvme_enable_ctrl / reset_work match), so no claim below
  rests on Aurora's enable ordering.
- Pro loader @ 7b1e2ebc: `src/standalone/level1-ans.c` (header comment,
  w64lh, l1_ans_leave, l1_ans_emergency, l1_ans_release/stop).

NOT verified in the fetched sources (do not treat as established):

- CORRECTION 2026-10-29 (see ADOPTION-RUNS-2026-10-29.md): the
  passage below as originally written claimed Aurora's adopted-state
  preparation was "not located". That claim was WRONG — it came from
  incomplete retrieval of a truncated browser view. Re-verified Oct
  29 against aurora-silicon/linux at full commit
  `d266c703c13f099068284d622d397292241a0224`: Aurora's adopted-init
  IS present — `apple_rtkit_mark_running()` (rtkit.c L1192-1217) is
  called from `__apple_rtkit_init()` (L1382-1383) when adopted, BEFORE
  `claim_rx()` / `mbox_start()`; `apple_rtkit_init_adopted()` is at
  L1415 and `apple_rtkit_init_adopted_with_buffers()` at L1458.
  Aurora's adopted path sends NO SET_AP_PWR_STATE (bookkeeping-only,
  like J604's P1). The original wording is preserved here for the
  record, struck through by this correction note; do not cite the
  "not located" claim.
  ORIGINAL (superseded): Aurora's claimed "prepares adopted state
  BEFORE mailbox reception starts": in the fetched Aurora rtkit.c,
  the inherited flags (`crashlog_inherited`, `syslog_inherited`,
  `oslog_inherited`) are CONSUMED in the rx handlers, but their
  setters / any pre-mailbox preparation function were not located
  in that file.
- The exact register sequence of m1n1's `c9_ctrl_shutdown()` (upstream
  m1n1 src/nvme.c was not fetched). See §2(b) for what IS established.
- Aurora's `apple_nvme_writeq()` call sites: the wrapper and its
  comment were verified, but the fetched view did not expose every
  call site, so "Aurora uses lo_hi for ASQ/ACQ as well as TCB bases"
  is stated as the wrapper's documented intent, not as a
  call-site-verified fact. Same caveat for Pro's `w64lh` call sites.

## 2. Astra's four differences, re-verified

### (a) RTKit reception order — real structural difference, weak CFS mechanism

J604 (live tree, drivers/soc/apple/rtkit.c):

- Mailbox reception starts at probe: `apple_rtkit_init()` registers
  `apple_rtkit_rx` as the mailbox callback and calls `apple_mbox_start()`.
  That is long before `apple_nvme_reset_work()` runs.
- `apple_rtkit_adopt_running()` (patch, rtkit.c) runs inside reset_work
  and only then sets two endpoint bits (`APPLE_RTKIT_EP_CRASHLOG` 0x01,
  `APPLE_RTKIT_EP_SYSLOG` 0x02) with NO STARTEP, completes the
  epmap/iop/ap wait objects, and sets iop/ap power state to ON as
  internal bookkeeping only. It sends zero management messages.
- Any firmware message arriving between probe and adopt_running is
  dispatched by `apple_rtkit_rx_work()` regardless of the endpoint
  bitmap (the bitmap only controls a warning line). Syslog LOG
  messages in that window hit `apple_rtkit_syslog_rx_log()`, warn
  "no syslog_msg_buffer", and still ACK (echo) the message
  (`goto done` -> `apple_rtkit_send_message`). So a syslog message
  cannot stall the firmware for lack of an ACK in J604.
- In the adopt+reserve success, repeated "SYSLOG MESSAGE BUT NO
  SYSLOG_MSG_BUFFER" lines appeared on logpages 2/3 and 3/3 and did
  NOT block enable. In the repeat failure photos, no
  undiscovered-endpoint or management (HELLO/EPMAP) lines appear on
  either photographed page — with the caveat that early probe lines
  may have scrolled off the 2-page display.

Aurora: rx handlers branch on `crashlog_inherited` /
`syslog_inherited` / `oslog_inherited` (e.g. an inherited session
"never saw SYSLOG_INIT, so the ring cannot be interpreted; the
records still have to be acknowledged"; an inherited crashlog buffer
is not re-read as a new crash). J604 has no equivalent inherited
flags: it treats every syslog LOG message the same way, and it never
records that the producer session already consumed SYSLOG_INIT.

Assessment: the race is real (a message can arrive before adopt
marks its endpoint), but no evidence ties it to CSTS CFS, and the
one observed instance (syslog spam in a SUCCESS) points the other
way. A management message (stray HELLO/EPMAP) arriving mid-enable
would be a stronger candidate, but none is evidenced in any
photographed page. Rank: LOW-MEDIUM for CFS. Missing evidence: a
full (not tail-only) kernel log for a failure run, or a
pre-adopt mailbox trace, showing a management message in the
probe-to-enable window.

### (b) Controller handoff / CC.SHN — Astra's attribution needs correction

Correction first: J604's Linux driver does NOT call `c9_ctrl_shutdown()`.
That is a PRODUCER-side (m1n1) helper. The sequence is in
`diagnostics/m1n1-adoption.patch`, `nvme_adopt_handoff()`:

- DELETE_SQ 1, DELETE_CQ 1 (via `c9_delete`), then
  `c9_ctrl_shutdown()` then `c9_ctrl_disable()`, then the arm gate:
  ASC CPU running, `rtkit_is_power_on()` (IOP ON and AP ON),
  BOOT_STATUS OK, CC.EN clear, CSTS.RDY clear. On success it
  snapshots and emits C9_ADOPT_ARM. `nvme_shutdown()` then
  early-returns when adopt-armed ("retain running ANS, buffers and
  SART mappings") with no sleep/stop/reset/free.

Pro loader, verified (`level1-ans.c`, `l1_ans_leave()` and its R44
comment):

- "Delete the IO queues, CC.EN = 0 (no CC.SHN: nothing was written)
  and wait RDY clear, bounded." No RTKit power message, no PMGR
  write, no reset, CPU_CONTROL untouched (RUN stays set), SART
  entries stay. Comment: "the firmware keeps its syslog/crashlog/
  ioreport/oslog buffer addresses until Linux's INIT gives it new
  ones."
- Pro's emergency path is different again (reset + RUN clear +
  SART removal), and is NOT the hand-back path.

What J604's `c9_ctrl_shutdown()` actually writes was NOT verified
in a fetched m1n1 source. Two established J604 facts bracket it:

- J604's own C9 notes record a shutdown step with SHST reaching
  complete in the C9 flow, i.e. a shutdown notification was part of
  the producer's vocabulary before adoption.
- ADOPT-PRE CC in every adoption run is 00474000. Decoding:
  EN bit 0 = 0; SHN bits 14–15 = (0x474000 >> 14) & 3 = 1, i.e.
  SHN_NORMAL is still set at handoff. Linux then clears it:
  `nvme_disable_ctrl(..., false)` clears SHN_MASK, and
  `nvme_enable_ctrl()` writes SHN_NONE, so at enable SHN = 0 in
  every run (SNAP2 CC 00460001 has SHN bits = 0).

Assessment: Pro deliberately avoids SHN and J604's producer (very
likely) sends one — that IS a real difference in handoff state.
But SHN happens on EVERY run including both successes, and SHN is
cleared before enable in every run, so SHN alone cannot be a
sufficient cause of CFS. It could only matter if ANS firmware keeps
a sticky shutdown-completed state that re-enable does not always
clear — a mechanism with no donor evidence fetched. Rank:
MEDIUM-LOW. Missing evidence: upstream m1n1 `c9_ctrl_shutdown()`
source (one fetch), and ideally a producer trace showing SHST at
arm time. The discriminating test for this hypothesis is a
SHN-free producer variant (EN=0 only, Pro-style leave) — a
producer change, strictly larger than the §4 test, so it is
second, not first.

### (c) Inherited buffers — verified difference, no CFS evidence in the repeat

Aurora (`drivers/nvme/host/apple.c`, `apple_nvme_sart_dma_setup`):

- For a preset IOVA, it requires `inherited_rtkit`, then validates
  page-by-page: no overflow, cache-line alignment, inside an
  inherited SART region (`apple_sart_is_inherited_region`), every
  page reserved, in the linear map, not highmem. Only then does it
  `memremap` the range, `dma_map_single_attrs` it, and REJECT it
  if the resulting DMA address != the firmware's identity IOVA
  ("Firmware keeps the old identity IOVA. A bounce/remapped
  address cannot replace it").
- On destroy it unmaps, unmemmaps, and only then removes the SART
  region. The `apple_nvme_rtkit_mapping` retains the device
  context for the retained mapping.

J604 (patch, `apple_nvme_sart_dma_setup` + destroy):

- For a preset IOVA in adopted mode only: SART-allow the preset
  range (`apple_sart_add_allowed_region`) and return 0 so the RTKit
  reply is sent. The reply path uses iova/size only; `bfr->buffer`
  stays NULL. Destroy guards the NULL (does not free). Non-adopted
  preset IOVA still returns -EINVAL.
- No range validation, no memremap, no identity-IOVA check, no
  CPU-visible pointer. Any later code path that dereferences
  `bfr->buffer` for an inherited buffer would fault — that is a
  latent correctness gap for later phases, not an observed one.

Buffers involved: syslog EP 0x02 and crashlog EP 0x01 (the 0x5000-byte
buffer request that returned -22 in run 1, fixed in run 4 by the
SART-allow change; after run 4 no -22 appears in any photo).
No evidence ANS gates NVMe RDY on syslog/crashlog buffer state:
syslog messages are ACKed without a buffer (see §2(a)), and the
repeat failure photos show NO buffer-request lines at all — the
log goes straight from TCB dumps to DEVICE NOT READY / CFS.
Also note for the record: producer sart-mask 0x5f vs consumer
ADOPT-PRE sart=01ff differ BY DEFINITION (producer snapshot mask
vs consumer protected-entries mask), not a slot-for-slot mismatch;
do not cite it as one.

Assessment: real, well-specified donor difference; as a CFS
explanation it is contradicted as sufficient by run 4 (buffer
serving demonstrably worked, enable still failed) and unevidenced
in the repeat. Rank: LOW for CFS; MEDIUM as a correctness debt
for any later read/write phase (Aurora's validation should be
ported when the donor branch is built, §5). Missing evidence: a
firmware buffer request in a failure run's full log.

### (d) Register access: writeq vs paired 32-bit writes — STRONGEST, and the ADOPTION note is wrong about it

Aurora (`drivers/nvme/host/apple.c`, `apple_nvme_writeq()`):

- Includes `<linux/io-64-nonatomic-lo-hi.h>`.
- Wrapper: if `hw->needs_ioq_registers`, `lo_hi_writeq(value, addr)`,
  else plain `writeq(value, addr)`.
- Comment, verbatim in substance: "Post-M4 ANS consumes the queue
  and NVMMU TCB base addresses as paired 32-bit registers. Match
  the access sequence used by Apple firmware, m1n1, and U-Boot;
  older ANS generations retain their native 64-bit access."

Pro loader (`level1-ans.c`):

- `w64lh()`: "io-64-nonatomic-lo-hi: two 32-bit stores" — low word
  first, then high word (`w32(x, lo); w32(x+4, hi)`).

J604 (patch + live tree `drivers/nvme/host/apple.c`):

- ZERO occurrences of `lo_hi_writeq` in the patch or the live tree.
- Pre-enable address writes, all plain `writeq` (live-tree lines):
  ASQ at :1271, ACQ at :1272, ASQ_TCB_BASE at :1276,
  IOSQ_TCB_BASE at :1278. Post-enable: IOQ_CQES at :1418,
  IOQ_CMDS at :1420 (also plain writeq; these cannot affect
  enable, which precedes them).
- The J604 `t8132_hw` entry sets `needs_ioq_register = true` —
  the very condition under which Aurora switches to lo_hi — yet
  the J604 code uses plain writeq throughout.
- `ADOPTION-2026-10-28.md` claims paired lo-hi access is "already
  handled by the October C9 tree's IOQ register writes, reused
  unchanged." That claim is CONTRADICTED by the patch itself:
  the IOQ writes are plain writeq too. Correct the note.

Why readback does not refute this (Astra's correction, applied):
run 5's readback showed `readq()` returning exactly the intended
ASQ_TCB / IOSQ_TCB / ASQ / ACQ values. A readback reads the
register file; it does not prove what ANS's internal consumer
latched. If ANS latches an address on the HIGH-word write (the
lo_hi sequence's second store), a single 64-bit transaction may
be delivered by the interconnect as one beat, as hi-then-lo, or
split with a gap — and the latched value, or whether the write
is accepted at all by a 32-bit-only ANS window, can vary with
bus state, address alignment, and window. That is a genuinely
intermittent mechanism, unlike the deterministic order/state
differences in (a)–(c). It also fits the one hard fact that
nothing else fits: CC (a 32-bit writel) is identical in success
and failure, while the 64-bit-written addresses are the only
enable inputs whose delivery mechanism differs from the donor's.

Counter-evidence, stated plainly: two successes used plain
writeq, so writeq is NOT deterministically broken. If it were,
run 6 and adopt+reserve could not have succeeded. The hypothesis
is therefore "writeq delivery to the ANS windows is
intermittently wrong", not "writeq never works". Confidence:
MEDIUM (highest of the set, not high). Missing evidence:
a direct observation of a mis-latched address — which the
current instrumentation cannot provide, because the only
readback reads the same register file. The lo_hi test in §4 is
the observation.

## 3. Timing / race hypotheses beyond Astra's four

H5 — Enable timeout too short for a slow ANS. WEAK. `nvme_enable_ctrl()`
(live core.c) writes CC without EN, re-reads CAP, writes CC|EN, then
`nvme_wait_ready(CSTS_RDY, RDY, (CAP.TO+1)/2, "initialisation")` —
a CAP-derived timeout in seconds, not a short fixed deadline. The
failure signature is CFS set, not a bare RDY-clear timeout. Missing
observation: CAP.TO itself is never printed in any run log (the
reset_work CAP reads are not logged); a future diagnostic print
of CAP would close this cheaply, but it is not a test by itself.

H6 — No retry after CFS. VERIFIED structural fact, not a cause.
In `apple_nvme_reset_work()`, an `nvme_enable_ctrl()` failure goes
to `out` and the probe fails with -19 ("RESET FAILURE STATUS: -19"
in the log); there is no second enable attempt in the same boot.
This AMPLIFIES any transient CFS into a binary boot outcome, but
it does not create CFS. A retry-on-CFS variant would discriminate
transient vs sticky CFS — keep it as a later diagnostic, not the
first test, because it changes failure handling rather than the
suspected cause and would muddy attribution if combined with §4.

H7 — Per-boot DMA address / SART collision. WEAK. Queue DMA
addresses vary per boot (repeat admin TCB 0x0000010002DF8000 vs
adopt+reserve ASQ_TCB 0x00000100038BC000 in Brett's photo; m1n1
base and retained-range addresses also shift). But Linux coherent
allocations avoid reserved/retained ranges, the SART protected
mask is constant (01ff at ADOPT-PRE in every run), and no overlap
is evidenced. No mechanism links a particular address to CFS.

H8 — AP power ON never sent by Linux. WEAK for flakiness, live as
a follow-up. The contract's labelled variant is "adopt + AP-ON
only". Against it: the producer arm gate REQUIRES IOP ON and AP ON
(`rtkit_is_power_on()`) and returned 1 in the repeat, so the
firmware's view of AP power is ON from the producer session;
Linux's internal bookkeeping (adopt_running sets ap_power_state
= ON) matches that view. If AP power were OFF, the arm gate
would have refused, not produced a flaky enable.

H9 — Sticky firmware state after producer shutdown (SHN). See
§2(b). MEDIUM-LOW. Discriminated by the SHN-free producer variant,
second in line after §4.

H10 — Queue programming order (AQA/ASQ/ACQ before TCB bases;
LINEAR_SQ_EN and NUM_TCBS before the disable). LOW. The order is
identical in success and failure runs (live tree reset_work:
LINEAR_SQ_EN, NUM_TCBS, disable_ctrl, AQA, ASQ, ACQ, TCB bases,
readback, enable), and no donor ordering difference was verified
in the fetched Aurora view (see §1). A different order would be
a deterministic change, not an explanation for flakiness, unless
ANS samples asynchronously — for which there is no evidence.

H11 — Diagnostic prints changing timing/layout. WEAK now. The
run-5 readback and run-6 TCB dump are read-only and were present
in BOTH a success (run 6, adopt+reserve) and the repeat failure,
so they are not the variable that separates those runs. Do not
remove them for the §4 test; removing them would add a second
variable.

## 4. Ranking

| Rank | Hypothesis | Confidence | Missing evidence / refutation condition |
|---|---|---|---|
| 1 | (d) Plain writeq to 32-bit-only post-M4 ANS address registers is intermittently mis-delivered/latched | MEDIUM | A mis-latched address cannot be observed with current instrumentation (readback reads the register file). Refuted as SOLE cause by a repeat failure under lo_hi (§5). Supported by ADOPT-POST under lo_hi, but needs a second consecutive success before "stable" is claimed. |
| 2 | (b) Producer SHN leaves sticky firmware shutdown state that re-enable does not always clear | MEDIUM-LOW | Upstream m1n1 c9_ctrl_shutdown source; SHST at arm time. Refuted as sole cause by the two successes that also went through SHN. Discriminated by the SHN-free producer variant, second. |
| 3 | (a) RTKit message arriving before adopt_running marks its endpoint | LOW-MEDIUM | Full (not tail-only) log of a failure run showing a management message in the probe-to-enable window, or a mailbox trace. Syslog spam is evidenced in a SUCCESS, which cuts against it. |
| 4 | H6 no-retry amplifying a transient CFS (mechanism, not cause) | — (structural fact) | A retry variant would show whether a second enable attempt succeeds after a first CFS — diagnostic value only, after §5. |
| 5 | (c) Inherited-buffer handling (NULL CPU pointer, no validation) | LOW for CFS; MEDIUM as later-phase debt | A buffer request in a failure run's full log. Port Aurora validation in the donor branch regardless (§5). |
| 6 | H5 timeout, H7 DMA/SART collision, H8 AP-ON, H10 queue order | LOW each | CAP print (H5); AP-ON variant is the contract's labelled follow-up, not the next test. |

Nothing above is labelled "eliminated" except in the narrow senses
already established: CTRR_D reserve does not by itself explain
enable (repeat failure with reserve correctly applied); buffer
serving as implemented in run 4 does not by itself explain enable
(enable still failed after the -22 was fixed); readback matching
does not prove programming correct (§2(d)); a non-adoption Oops
does not prove independence from shared changes (the CTRR_D
defect itself was a shared DTB/producer change).

## 5. The ONE recommended next hardware test

Change ONE variable only: the pre-enable 64-bit address writes.

- In `drivers/nvme/host/apple.c`, `apple_nvme_reset_work()`:
  replace plain `writeq` with `lo_hi_writeq` (include
  `<linux/io-64-nonatomic-lo-hi.h>`, as Aurora does) for exactly
  four writes: ASQ, ACQ, ASQ_TCB_BASE, IOSQ_TCB_BASE.
- Change NOTHING else: same kernel tree otherwise, same initramfs
  (1057580b…), same producer (op 0xf06, Option A, SHN behaviour
  unchanged), same per-boot CTRR_D reserve DTB technique (new
  base, new DTB — the base shift is inherent to the technique,
  not a test variable), same cmdline with `j604.test=ADOPT`,
  same RAM-only reads-only boot, same readback/TCB-dump prints
  (read-only, present in both success and failure runs).
- Do NOT also change the IOQ post-enable writes in this test:
  they occur after enable and cannot affect it; changing them
  would add a variable. They are a follow-up if the pre-enable
  change succeeds (port Aurora's wrapper for all six writes).
- Brett physically: photograph the screen (panel/logpages with
  CRCs), then reboot to proxy — same as before. No other action.

Support criterion: ADOPT-POST with cc=00460001 csts=00000001
(RDY=1) AND panel ADOPT PASS (5/5, NAMESPACE YES, ERROR NONE).
Refutation criterion (as SOLE cause): DEVICE NOT READY,
CSTS=0x2, SNAP2 cc=00460001 csts=00000002, RESET -19, NO
ADOPT-POST — i.e. the exact repeat signature, now under lo_hi.

Interpretation discipline: ONE lo_hi success does NOT prove
stability (base rate with reserve is 1/2; one success is
consistent with chance). If it succeeds, repeat once more
UNCHANGED before claiming anything stronger than "supported".
If it fails, lo_hi is refuted as the sole cause (it may still
contribute, but the next test must be the SHN-free producer
variant, §2(b), not a combined lo_hi+SHN change — combining
them would destroy attribution). The top two hypotheses ARE
separable by one test each, in this order, so no pair is needed
up front.

## 6. Donor-integration branch: start now in parallel, do not boot it yet

Start a SEPARATE source-only branch now, in parallel with the
§5 test, because it costs no Mac time and stages the next step
whichever way §5 lands:

- Port, as a reviewable diff against the J604 tree (not a
  wholesale Aurora import): Aurora's `apple_nvme_writeq()` wrapper
  (all six address writes, once §5 justifies it); Aurora's
  inherited-buffer validation (reserved-page + SART-region +
  identity-IOVA checks, memremap + dma_map, retained mapping
  context) replacing the NULL-buffer SART-allow; Aurora's
  `can_adopt` CFS gate (refuse adoption if CSTS & CFS at
  adopt-check time — note this gate would NOT have changed any
  run so far, since ADOPT-PRE csts was 0 in all of them; it is a
  safety improvement, not a fix); and the RTKit inherited flags
  (crashlog/syslog/oslog) so an inherited session is
  distinguished from a fresh handshake in the rx paths.
- Keep J604 addresses, DT property names (`j604,ans-live`),
  Option A contract, and the T8132 NVMMU window (0x485cc0000)
  explicit and separate from any T6040 addresses.
- Do NOT boot this branch before the §5 result. If lo_hi alone
  fixes enable, the branch can be trimmed to the wrapper +
  validation and the SHN/AP-ON variants stay unbuilt. If lo_hi
  fails, the branch is already staged for the SHN-free producer
  variant and the AP-ON follow-up. Booting a large donor rewrite
  before §5 would confound attribution in exactly the way Astra
  warned against.

## 7. Log retrieval (largest testing-time multiplier)

Status: configured but NOT verified end-to-end.

- Kernel: CONFIG_PSTORE=y, PSTORE_CONSOLE=y, PSTORE_RAM=y,
  PSTORE_COMPRESS=y (live tree .config). DTB (repeat run's
  augmented.dts): reserved-memory node `ramoops@10300000000`,
  reg 1 MiB, record-size 0x20000, console-size 0x80000,
  pmsg-size 0x20000, max-reason 2. The region is reserved, so
  Linux will not allocate over it, and the load addresses seen
  in boots (kernel/FDT/initramfs around 0x1000xxxxxxx) do not
  overlap it.
- What is UNVERIFIED: whether the region's contents survive the
  actual return-to-proxy path used here (Brett's manual reboot,
  which re-enters iBoot/proxy — as opposed to a watchdog reset
  that stays inside the proxy's RAM context), and whether any
  tool on the sunki side can read that physical range back
  through the proxy. A subsequent Linux boot reading
  /sys/fs/pstore would also work ONLY if RAM survived AND the
  Go init had a shell to read it — it currently does not.
- Cheapest verifiable check (one dedicated experiment, no new
  infrastructure): boot a kernel that prints a unique marker
  string to console, return to proxy by the usual path, then
  attempt a proxy-side physical read of 0x10300000000 and grep
  for the marker. Marker present = ramoops survives this path
  and is worth building the read-back tooling around. Marker
  absent = ramoops does not survive this path; stop relying on
  it and do not spend further boots assuming it.
- USB EEM (Air project, J713): NOT assumed. For J604 it needs a
  USB gadget/EEM path in the RAM kernel, the Mac's USB-C port in
  device mode, and host-side capture on sunki — none built,
  none verified. It is larger work than the ramoops check and
  should only start if the ramoops check fails or if a live
  (non-post-mortem) log channel becomes the binding constraint.
- Until either channel is verified, every verdict stays
  photo/webcam-bound with the known limits: tail-only logpages,
  scrolling loss of early probe lines, and transcription risk
  (the 17-digit VA error and the run-3 VA correction are the
  standing examples). The §5 test's support/refutation criteria
  were chosen to be readable from a single photographed page
  (ADOPT-POST line, SNAP2 line, panel) for exactly this reason.
