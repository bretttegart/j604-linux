# RTKit endpoint race — offline investigation (no boot)

Date: 2026-10-28 evening, after the SHN-free test failed.
Scope: NO hardware boot, NO Mac reboot, NO proxy use for booting, NO code
changes, NO repo push. Read-only review of the J604 tree on sunki plus the
public donor sources (Aurora linux @ d266c703, Pro m4-loader @ 7b1e2ebc).

## 0. Headline correction first

The SHN-free agent's claim that "MESSAGE TO UNDISCOVERED ENDPOINT 0x02" was
a line "not seen in previous runs" is WRONG as a run-record claim. It was
new to that agent's frame set, not to the project. Grep of the Oct 28 run
notes shows the line in:

- Run 2 (retry) RUN-NOTE: "RTKit: Message to undiscovered endpoint 0x02,
  then 0x01" — failure.
- Run 3 (flagflip) RUN-NOTE: "Message to undiscovered endpoint 0x01 (and
  0x02 earlier in the log)" — failure.
- SHN-free RUN-NOTE + Brett's photos (LOGPAGE 1/2 CRC 2B6A2432) — failure.

It is NOT reported in: run 4 (notes explicitly list "no undiscovered
warnings" as a criterion and report none in photos), run 6 (success),
adopt+reserve (success), lo-hi (failure), adopt+reserve repeat (failure).
Run 1 has no RUN-NOTE.md (cam files only), so its status is UNKNOWN, not
absent. Tally on known-status runs: undiscovered in 3/7 failures, 0/2
successes. It is neither necessary nor sufficient for failure in the
observed record. Absence from a photo is also not proof of absence from a
boot: the logpage display shows only a window, and most run notes are
photo/frame-based.

## 1. The J604 code, with exact locations

All J604 line numbers are ~/linux-asahi, branch asahi + October C9/adoption
working tree (the live tree still carries the lo-hi edit un-reverted; the
booted kernels were file-verified, so do not confuse live-tree text with
booted-kernel behaviour).

### 1a. When reception starts vs when endpoints are marked

- drivers/nvme/host/apple.c, apple_nvme_probe path (~line 1810-1885):
  the /chosen offer is read first (ADOPT-OFFERED, controller-state
  "disabled"), then devm_apple_rtkit_init() at line 1885.
- drivers/soc/apple/rtkit.c, apple_rtkit_init (~lines 700-740): bitmap_zero
  on endpoints, set_bit(APPLE_RTKIT_EP_MGMT = 0) ONLY, then
  rtk->mbox->rx = apple_rtkit_rx, then apple_mbox_start(rtk->mbox).
- drivers/soc/apple/mailbox.c, apple_mbox_start (line 243): enables the
  recv-not-empty IRQ. Reception is therefore LIVE from probe, before any
  adopt marking.
- drivers/nvme/host/apple.c, apple_nvme_reset_work (line 1085, run
  asynchronously via apple_nvme_async_probe): adoption gate, ANSCHK,
  ADOPT-PRE print (line 1171), then apple_rtkit_adopt_running() (line
  1177), then anv->adopted = true (line 1179).
- drivers/soc/apple/rtkit.c, apple_rtkit_adopt_running (lines 886-906):
  sets iop/ap power states ON (bookkeeping only), completes the epmap /
  power completions, then set_bit(APPLE_RTKIT_EP_CRASHLOG = 1) and
  set_bit(APPLE_RTKIT_EP_SYSLOG = 2) — WITHOUT apple_rtkit_start_ep, i.e.
  no STARTEP (contract C1) — and prints "inherited endpoints 0x01/0x02
  marked discovered (no STARTEP)".

The race window is therefore real and precisely bounded: from mbox_start
inside probe to adopt_running() inside reset_work. In between, probe does
queue allocation, IRQ request, nvme_init_ctrl, and async scheduling, so
the window is not microseconds — it spans the whole tail of probe plus
workqueue scheduling. Any ANS message to 0x01/0x02 inside it hits the
undiscovered path.

### 1b. What the rx path does with an undiscovered-endpoint message

drivers/soc/apple/rtkit.c, apple_rtkit_rx (~lines 600-625):

    if (!test_bit(ep, rtk->endpoints))
        dev_warn(rtk->dev, "RTKit: Message to undiscovered endpoint 0x%02x\n", ep);
    // app-endpoint early-recv check (system endpoints skip this)
    work = kzalloc(...); work->ep = ep; work->msg = msg.msg0;
    queue_work(rtk->wq, &work->work);   // ordered workqueue

apple_rtkit_rx_work (~lines 555-600) then dispatches by endpoint number
regardless of the bitmap: EP_CRASHLOG (1) -> crashlog_rx, EP_SYSLOG (2)
-> syslog_rx, etc. THE MESSAGE IS NOT DROPPED. The undiscovered line is a
warning attached to a normally-dispatched message. Any theory in which
"the message was dropped, therefore CFS" contradicts this code directly.

What the handlers then do depends on message type (the log line carries
only the endpoint, never the type — so the type of SHN-free's 0x02
message is NOT directly evidenced):

- SYSLOG LOG (type 5), syslog_rx_log (~lines 462-510): syslog_msg_buffer
  is NULL in adoption mode because SYSLOG_INIT was consumed by the
  producer session, so it warns "received syslog message but no
  syslog_msg_buffer" and goes to `done:`, which STILL sends the ACK reply
  (apple_rtkit_send_message, EP_SYSLOG, same msg). LOG messages are
  ACKed even early. No state consequence.
- SYSLOG BUFFER_REQUEST (type 1), via apple_rtkit_common_rx_get_buffer
  (~lines 266-339) -> shmem_setup = apple_nvme_sart_dma_setup
  (drivers/nvme/host/apple.c, ~lines 262-295): a preset IOVA with
  anv->adopted == false returns -EINVAL. The get_buffer error path
  (~lines 330-339) prints "failed buffer request for 0x%zx bytes (-22)",
  clears the buffer (size = 0, iova = 0), and sends NO reply. This is the
  ONE early-message path with a withheld reply.
- CRASHLOG: crashlog_rx (~lines 370-410) only acts on type CRASH (1);
  other types warn and return with no state change. A CRASH message with
  an empty buffer goes through the same get_buffer/-EINVAL path as
  above; a CRASH message with a buffer sets rtk->crashed = true and calls
  ops->crashed -> nvme_reset_ctrl. No run shows a crash line, so no
  early message in any run was a CRASH that reached that path.

A second ordering subtlety: rx_work runs on an ordered workqueue while
adopt_running runs on reset_work. A buffer-request work item QUEUED early
can EXECUTE after adopt_running (adopted == true), in which case the
run-4 SART-allow path succeeds and the reply is sent. Early arrival does
not imply early handling. The race is doubly timing-dependent.

### 1c. What endpoint 0x02 is, and whether it can gate enable

Endpoint numbers, drivers/soc/apple/rtkit.c lines 19-27: MGMT 0,
CRASHLOG 1, SYSLOG 2, DEBUG 3, IOREPORT 4, UNKNOWN7 7, OSLOG 8,
TRACEKIT 0xa. So 0x02 = SYSLOG, 0x01 = CRASHLOG. (Run-4's "syslog/crashlog
endpoints" shorthand is correct.)

Syslog message types in this tree: BUFFER_REQUEST 1, LOG 5, INIT 8
(SYSLOG_INIT carries entry count and message size; the producer consumed
it, so Linux never learns the ring geometry — hence every later LOG
warns and is ACKed unparsed).

Does anything in the driver gate NVMe enable on syslog/crashlog state?
NO, in code. The enable path in reset_work (lines ~1210-1390: boot-status
poll, NVMMU setup, nvme_disable_ctrl, AQA/ASQ/ACQ/TCB writes, readbacks,
TCB dumps, nvme_enable_ctrl, ADOPT-POST at line 1385) reads only CC,
CSTS, BOOT_STATUS and SART mask. It never consults the endpoints bitmap,
the syslog/crashlog buffer structs, or any RTKit completion except the
adopt/boot ones already completed. CFS (CSTS bit 1) is set by firmware,
not by Linux. So a code-level gate from "syslog/crashlog mishandled" to
"CFS at enable" DOES NOT EXIST in this driver. Any causal link must be
firmware-side (e.g. ANS waiting on a log-buffer reply before it will
report RDY) — that is inference, not verified code, and no run evidences
ANS waiting on anything: the failure signature is immediate CFS, not a
timeout (enable waits a CAP-derived timeout, not a short fixed deadline,
and the failure is CFS, not bare slowness).

### 1d. Is there an existing pre-discovery mechanism?

NO, in the J604 tree. The /chosen offer (j604,ans-live = 1,
j604,ans-live-controller-state = "disabled", j604,ans-live-boot-status =
0xde71ce55, j604,ans-live-sart-mask = 0x5f, verified in SHN-free's
prepared-adopt.dts) is read only to set adoption_offered (apple.c
~1821); it is never used to pre-mark endpoints or pre-install buffers.
apple_rtkit_init takes no adopted/inherited parameter, and the J604
rtkit.h (line 127) exports only apple_rtkit_adopt_running(). A
pre-marking mechanism would need to be built (see section 5 for the exact
form that preserves C1).

## 2. Aurora: the adopted-init API exists in the header, its implementation was NOT located

Aurora linux @ d266c703, include/linux/soc/apple/rtkit.h (verified by
fetch):

- apple_rtkit_init_adopted(): "Initialize an instance for a co-processor
  that the bootloader left running and that cannot be reset. No
  HELLO/EPMAP handshake takes place: the system endpoints are marked
  available and syslog/OSLog records are acknowledged without being
  parsed. The caller must verify the device-specific running/ready
  indicators before using the instance."
- apple_rtkit_init_adopted_with_buffers(): "As above, with the previous
  owner's system buffers installed BEFORE mailbox RX starts. The caller
  validates and maps their retained storage."
- apple_rtkit_hold_rx() / resume_rx(): "Stop taking interrupts for
  messages from the co-processor, which then stay queued in the mailbox
  until apple_rtkit_resume_rx()."
- struct apple_rtkit_inherited_buffer { endpoint, shmem } and the
  rtkit-internal.h fields syslog_inherited / crashlog_inherited /
  oslog_inherited, commented "Session inherited from the bootloader:
  INIT geometry never observed." Aurora's syslog_rx_log ACKs-without-
  parsing when syslog_inherited is set, and its crashlog_rx only looks
  for an earlier-crash log in an inherited session.

BUT: the definitions of init_adopted / init_adopted_with_buffers /
hold_rx / resume_rx, and any assignment of the *_inherited flags to
true, were NOT found in Aurora's rtkit.c at d266c703 (find for
"init_adopted" and "hold_rx" in the fetched file returns nothing; the
only syslog_inherited assignment found is "= false" inside
syslog_rx_init), nor is there a separate rtkit-adopted file in
drivers/soc/apple at that commit (directory listing verified). The
Aurora T8132 file t8132-platform-handoff.c is PMGR policy only, not
RTKit adoption. So: Aurora's DESIGN INTENT is documented (adopted state
+ buffers before RX), but the donor report's earlier "not located" stands
for the implementation at this commit — do not cite an Aurora adopted-
init implementation as verified code. The correct statement is: Aurora
designed for this exact problem (pre-RX adopted state), J604 has not
implemented that design, and the J604 gap is the probe-to-adopt window
in section 1a.

## 3. Pro loader: no Linux-side pre-marking, but confirmation that early traffic is expected

jgoyvaerts/m4-loader @ 7b1e2ebc, src/standalone/level1-ans.c,
l1_ans_leave() (lines 1280-1350): delete IO queues, CC.EN = 0 (no
CC.SHN), bounded RDY-clear wait, no RTKit power message, no PMGR write,
CPU_CONTROL untouched, SART entries stay. Its comment states the
firmware "keeps its syslog/crashlog/ioreport/oslog buffer addresses
until Linux's INIT gives it new ones". The Pro loader therefore does NOT
pre-mark anything for Linux — it is a loader-to-m1n1 handoff, and it
expects Linux to run a full INIT/EPMAP handshake (which adoption
deliberately skips). Its relevance to J604 is narrower but real: it
confirms ANS syslog/crashlog traffic after handoff is NORMAL and
continuous (the J604 producer itself drains syslog via nvme_poll_syslog
during its own CC waits, C9-PREP-ADOPT/m1n1-local/src/nvme.c lines
180-257), so a message landing in Linux's probe-to-adopt window is a
timing coin flip, not an anomaly. Nothing in l1_ans_leave changes Linux
message timing except that it leaves ANS running — which the J604
producer also does.

## 4. Why SHN-free showed the line (and why that explanation is weak as a SHN mechanism)

Candidates, tested against the code and the corrected run record:

(a) SHN-wait removal shortens handoff, so Linux probe starts earlier
relative to ANS's next periodic syslog message, widening the chance a
message lands in the probe-to-adopt window. PLAUSIBLE as a timing shift,
but NOT a SHN-specific mechanism: run 2 and run 3 showed the same line
WITH SHN present, so SHN removal is not necessary for it. At most it
nudged the odds in one run.

(b) ANS sends a message at a fixed point after handoff regardless of
Linux readiness. CONSISTENT with continuous syslog traffic (producer
polls it during waits; Pro keeps the buffers live), but it predicts the
line in MOST runs, not 3/7 — unless most such messages fall outside the
window or outside the photographed logpage window.

(c) The message was present in more runs but only visible when the
logpage window includes it. STRONGEST for explaining absences: run
notes are photo/frame-based, the logpage display is a scrolling window,
and the undiscovered line sits early in the log (before ADOPT-PRE),
while most verdict photos capture the LATER pages (enable failure /
panel). Run 4's "no undiscovered warnings" is a photo claim, not a
boot-log claim. Absence from a photo must not be treated as absence
from the boot.

Most defensible combined explanation: (a) + (c) — a periodic-traffic
coin flip per run, filtered by a narrow photographed window, with SHN
removal at most nudging the timing. The SHN-free line itself proves
only one thing: in that run, an ANS message to ep 0x02 arrived between
Linux mbox_start and adopt_running. Nothing more.

One further observation on SHN-free's specific message: its photographed
pages contain NO "failed buffer request (-22)" line, while runs 1-3
photos do. If SHN-free's early 0x02 message had been a BUFFER_REQUEST
refused pre-adopt, the -22 line should appear somewhere in the log
(it is printed unconditionally on that path). Its absence is consistent
with the early message being a LOG (type 5): warned as undiscovered,
then ACKed at `done:` with no state consequence. That is not proof of
type (the -22 line could sit outside the photographed window), but it
leans against the buffer-request reading for this run.

## 5. Causality assessment: LOW-MEDIUM overall, LOW for SHN-free specifically

For a causal role:
- The pre-adopt buffer-request refusal is a real withheld-reply path,
  and Aurora engineered pre-RX adopted state precisely to avoid
  early-message mishandling — the donor authors clearly consider this
  class of problem worth designing around.
- The undiscovered line appears in 0/2 successes and 3/7 known-status
  failures, so it does not anti-correlate with success.

Against a causal role (stronger):
- rx does NOT drop the message; only the warning is new, dispatch
  continues (section 1b). The narrow "warning path" theory contradicts
  the code.
- SHN-free's early message most likely was a LOG (no -22 in its pages),
  which is ACKed regardless of the bitmap.
- The line is absent in 4 known-status failures (run 4, lo-hi, repeat,
  plus successes excluded) — so it is not necessary for the failure
  signature, which is byte-identical with and without it (CSTS 0x2,
  SNAP2 cc 00460001 csts 00000002, RESET -19).
- No driver code path links syslog/crashlog state to CFS; run 4 proved
  post-adopt buffer-serving working while enable still failed; successes
  (run 6, adopt+reserve) show syslog-no-buffer lines coexisting with
  ADOPT-POST.
- The ordered-workqueue subtlety (section 1b) means even a genuinely
  early buffer request may be handled post-adopt and succeed.

Verdict: the race is REAL (the window exists, the warning proves
traffic inside it, and pre-adopt buffer refusal is a genuine withheld
reply), but as the cause of CFS it is LOW-MEDIUM in general and LOW for
the SHN-free run. It is best read as a timing marker and a correctness
debt, not as the prime suspect. Promoting it would repeat the lo-hi /
SHN pattern: a plausible mechanism, refuted as sole cause by the next
test, at the cost of another boot cycle.

## 6. The ONE recommended next test: pre-mark inherited endpoints inside rtkit_init, before mbox_start

Change (one variable only, no STARTEP, C1 intact):
- In drivers/soc/apple/rtkit.c, give apple_rtkit_init() an adopted
  pre-marking path: when the NVMe probe has an adoption offer (the
  /chosen j604,ans-live properties it already reads), set
  set_bit(APPLE_RTKIT_EP_CRASHLOG) and set_bit(APPLE_RTKIT_EP_SYSLOG)
  on rtk->endpoints BEFORE apple_mbox_start() is called inside init.
  The cleanest form is a parameter/flag on rtkit_init (or a tiny
  pre-mark helper called from probe before init's mbox_start — but NOT
  a set_bit in probe after init returns, because mbox_start already ran
  inside init and the window, though shrunk to microseconds, would
  remain by construction).
- adopt_running() keeps its existing set_bit calls (idempotent) and its
  power-state/completion bookkeeping; nothing else in reset_work,
  producer, kernel, initramfs, cmdline, or reserve-DTB technique
  changes. Kernel: #33 lineage, plain writeq (the lo-hi edit stays out
  of the booted file, as in the SHN-free test). Producer: the ORIGINAL
  SHN-carrying producer (2bf344d6), not the SHN-free variant — SHN is
  not the variable here, and reverting to the repeat baseline keeps
  attribution clean (repeat baseline = #33 + original producer +
  reserve, failed with the race window present).
- What this test does and does not change, stated plainly: it silences
  the undiscovered warning and guarantees dispatch bitmap state from
  the first received message. It does NOT change early buffer-request
  handling, because that refusal is gated on anv->adopted (apple.c
  sart_dma_setup), not on the endpoints bitmap — a pre-adopt buffer
  request would still be refused with -22 until adopt_running sets
  adopted. So this test discriminates the NARROW theory (bitmap/
  warning/dispatch path causes CFS), not the broader early-buffer theory.
  If it fails, the narrow theory is refuted and the follow-up (NOT
  combined into this test) is an adopted-early variant that also makes
  buffer handling adopt-aware before reset_work — a separate decision,
  because adopted=true early also touches the shutdown-skip and
  remove paths.

Support criteria: ADOPT-POST cc=00460001 csts=00000001 (RDY=1) +
panel ADOPT PASS 5/5, AND the undiscovered-endpoint line absent from
all photographed/sampled pages (if the line still appears, the marking
did not take effect before RX — an implementation failure, not a
theory result).
Refute criteria (narrow theory): the exact repeat signature — DEVICE
NOT READY, CSTS=0x2, NVME-SNAP2 cc=00460001 csts=00000002, RESET
FAILURE -19, no ADOPT-POST — with the undiscovered line ABSENT (line
gone, failure persists = race-as-warning-path refuted). If the line is
present despite the change, the test is inconclusive on the theory and
the implementation must be fixed first.
Discipline, as before: one success does not prove stability (base rate
with reserve is 1/4); a second unchanged repeat is required before any
stronger claim.

## 7. Interaction with syslog-no-buffer and inherited-buffer validation (short)

Three distinct layers of the same inherited-session incompleteness, not
one fix: (i) the undiscovered warning = bitmap state during the
probe-to-adopt window (this test's target); (ii) syslog-no-buffer =
LOG messages after adopt whose SYSLOG_INIT geometry Linux never saw
(needs Aurora-style inherited-flag ACK-without-parse, or a re-INIT —
not changed by bitmap pre-marking); (iii) inherited-buffer validation =
BUFFER_REQUEST handling, fixed post-adopt by run 4's SART-allow but
still refused pre-adopt via adopted==false (needs the adopted-early
follow-up, or Aurora's init_adopted_with_buffers design, not the bitmap
test). Bitmap pre-marking touches (i) only. Do not let a success or
failure of test 6 be read as a verdict on (ii) or (iii).
