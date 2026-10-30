# Live-session adoption runs, 2026-10-29 (Mac16,1 / T8132 / J604)

RAM-only adoption tests. Same contract as Oct 28
(adoption-handoff-contract-2026-10-28.md in the workspace copy):
default handoff RUNNING, not quiesced; Option A only for first runs
(controller DISABLED, queues deleted, ANS running; Linux creates fresh
queues). Forbidden before first I/O: INIT, HELLO, HELLO_REPLY, EPMAP
renegotiation, STARTEP for inherited endpoints, AP/IOP power
renegotiation (except the single AP-ON message permitted by Amendment
A1, §6A, and later the single instrumented Tier B message permitted by
Amendment A2, §6B — both now lapsed for enable purposes), SLEEP, PMGR
reset, SART/buffer reallocation.

Payload baseline, unchanged all Oct 29 unless a section says otherwise:
disabled producer `2bf344d672ad0e835b1758f68a6b7c35d9c4accd20c50222c981ec393a17f4ef`,
adoption initramfs `1057580bef01f17a2705a7bf8e1f746098090437970922cb43d904aaea435f5b`,
orig DTB `d7091e7449a92d8ca62d6c4613cff8fe0ae86451d4e81af52c5eb56e1d84dc01`,
kernel #33 `6c78e8b8f494c4e48e1dd1b88e9153017610db41bc6f13ef84a38cb206ddf029`.
Boot method every run: linux.py under pty, cmdline EXACTLY
`idle=nop nokaslr loglevel=8 console=tty0 fbcon=nodefer j604.test=ADOPT`
(fbcon only, NO serial console — not approved), RAM-only, reads only,
one proxy process at a time. Webcam (Logitech C920 on sunki,
/dev/video0) is corroboration only; **Brett's phone photos supersede it
in every run**. Host linux-boot.log contains no kernel console lines
(console is framebuffer-only after kboot_boot) — standing pattern.

Standing scorekeeping, applied all day: the clean tally counts enable
outcomes (ADOPT-POST vs RESET -19). **ADOPT-POST and panel PASS are
separate records everywhere below** — a POST with no panel photo is
POST-only, never upgraded to a panel PASS. Diagnostic tallies
(retry-diag, AP-ON, A2) are separate and never enter the clean tally.

FAST-LOOP MODE (approved Oct 28) continued Oct 29. NOT approved:
LabOS as default boot, serial-console cmdline change. Loop automation
HELD Oct 29 (Brett's explicit choice): no serial change, no
watchdog/panic investigation, no host-side loop script.

## Corrections to earlier notes, made in this commit

(a) RTKit correction. The Oct 28 notes claimed Aurora's adopted-init
implementation was "not located" (DONOR-COMPARISON-2026-10-28.md, "NOT
verified" section; RTKIT-RACE-INVESTIGATION-2026-10-28.md §2). That
claim was WRONG — it came from incomplete retrieval of a truncated
browser view. Re-verified Oct 29 against the Aurora fork at full
commit `d266c703c13f099068284d622d397292241a0224`
(aurora-silicon/linux): Aurora's adopted-init IS present.
`apple_rtkit_mark_running()` (rtkit.c L1192–1217) is called from
`__apple_rtkit_init()` (L1382–1383) when adopted, BEFORE `claim_rx()` /
`mbox_start()`; `apple_rtkit_init_adopted()` is at L1415 and
`apple_rtkit_init_adopted_with_buffers()` at L1458;
`apple_rtkit_adopt_running()` (L1637–1645) calls mark_running and
returns 0 — and sends NO management message, in particular NO
SET_AP_PWR_STATE. Aurora's adopted path is bookkeeping-only, like
J604's P1 (below). Aurora's NORMAL boot path ends with
`set_ap_power_state(ON)` (L1628); the `early_ap_power` variant sends
it before the IOP power ACK wait (L1604–1613). Aurora's adopted
consumer path (apple.c L1604–1632): adopt_running, disable only if
CC.EN set, `goto rtkit_ready`, no AP message. The two Oct 28 passages
are corrected in this commit; the Oct 29 donor-integration report
carries the corrected provenance (see §7).

(b) Single-variable wording. Oct 28's lo-hi and SHN-free sections
already read "REFUTED as sole cause" and are left as-is. The pre-mark
section headed "NARROW THEORY REFUTED" is softened in this commit to
"refuted as a sole cause": pre-mark failed identically alone; a
combined effect with other pieces was never tested, so no broader
elimination is claimed.

(c) X1 note correction. C9-X1-SESSION-2026-10-12.md overstated page 7
as byte-exact and page 17's tail as CRC-confirmed. The verification
agent's final report retracted BOTH: despite exhaustive search
(spacing variants, CRC-affine single/pair substitution solving,
zero-run combinatorics), NO page's transcription reproduced its header
CRC. The corrected verification section (staged at
`m4-salvage/c9-x1-2026-10-12/verification-section-corrected.md`) is
applied in this commit. The X1 conclusions are unaffected — the
load-bearing values (FAR 0x49F020000, PC 0xDA24E8, ESR 0xBE000000,
CMBX slots 125/126/127) were each read independently from the frames
and cross-confirmed across pages; only byte-exact archival
transcription remains unproven.

## 1. Reserve-repro boot (~10:27) — reproduction technically UNCONFIRMED

Run dir `run-2026-10-29-reserve-repro/`. Non-adoption boot, no ADOPT
cell. Base read twice: `0x10005920000`. CTRR_D
`[0x1000583c000, 0x10005920000)`. Augmented DTB
`89f7d38d4893d0ba96dcfbb41b3270841f96804a761c2b375841d68255af41de`
(one memreserve line only, dtc round-trip). Kernel #33. Logpages 1/2
CRC `72E01351`, 2/2 CRC `CA8D04E2` (Brett photos matched webcam
exactly). No Oops on any sampled frame to 235 s.

**Panel PASS was NOT captured.** The panel paints only until
verdict+10 s; both the webcam first sample and Brett's photos missed
the window. Reproduction therefore remains technically UNCONFIRMED.
The sustained PASS in §2 does NOT retroactively confirm it.

## 2. Sustained-read boot (10:36–10:52) — SUSTAIN PASS, 1520/1520, n=1

Build dir `run-2026-10-29-sustained-build/`, boot dir
`run-2026-10-29-sustained-boot/`. New initramfs SHA
`d2e8b6c8e966ba79dbd44657b66e0bf3093fe2958b786382c54d810f057abba4`
(1,038,954 bytes); cell `j604.test=SUSTAIN` (panel paints
continuously, final verdict stays up indefinitely); expected map
fixed to the probe-reads values (the repo tree's `c9_status.go`
expected map did NOT match probe-reads for 4 of 5 LBAs; the booted
initramfs `1057580b…` DOES contain all five probe hashes — the repo
tree was never updated; any initramfs built from the repo tree as-is
would fail 4/5). Detached build EXIT=0, NO kernel rebuild. Boot
approved by Brett 10:44. Base `0x10004ddc000`. CTRR_D
`[0x10004cf8000, 0x10004ddc000)`; CTRR_C
`[0x10006390000, 0x1000639c000)`. Augmented DTB
`169a668a0322bf290206029136b31308f99e136236feb618b121e7f4e203c05a`.
Cmdline exactly as baseline except `j604.test=SUSTAIN`.

Panel verbatim (Brett-photo-confirmed): SUSTAIN / PASS; ITER 272 OK
1520 TOT 1520; SIZE 4096 CONC 8 WRAPS 23; IOQ DEPTH 64; DIRECT MATCH 5
OF 5; NAMESPACE YES; BOOT `D7E536B5`; PHASE SUSTAIN PASS; ERROR NONE;
MISMATCH NONE. All three phases clean, 1520/1520 reads, Oops none.

Caveats: n=1; reads establish nothing about self-contained booting,
reset/suspend, or writes. Brett rebooted to proxy 10:52 (verified
ttyACM1 10:53–10:54).

## 3. Enabled handoff (Astra step 2) — designed, built, FAILED same signature

Design doc (618 lines):
`~/j604-boot/adoption-build/enabled-handoff-design-2026-10-29.md`.
Key finding: J604's consumer already does adopt-then-disable in
sequence; the design needs a mode-split gate, a contract change, and
one audit — no new disable call site. Queues/SART recommendation:
delete and recreate, do not reuse. Prep (a) FDT-parser fix
root-caused (parse_fdt treated FDT_BEGIN_NODE names as strings-block
offsets; node names are inline strings); prep (b) automated CTRR
reservations — still pending (not built); prep (c) ramoops
verification — still pending (not built).

Brett's three decisions (Oct 29, 11:04): (1) gate-failure policy
**refuse-and-stop** with diagnostic dump, no auto-retry as disabled;
(2) producer variant **in-place flag** (not separate binary) —
reboots reset the chainloaded producer state, so runtime
contamination is not persistent, provided the original producer
binary + source are preserved as a verified backup first and the flag
defaults OFF; (3) scope **minimal** — mode gate + contract + disable
audit, same IOQA, same SART-allow, NO full Aurora adopted-init port.

Minimal build (Oct 29, ~11:05–11:15), build note
`run-2026-10-29-enabled-build/BUILD-NOTE.md` (210 lines). Backup
first (`backup/m1n1-adoption-orig.bin` SHA `2bf344d6…`; source
tarball; pre-edit consumer files; Oct 28 prepared DTB). Work tree
`m1n1-enabled/` is a copy — original tree never edited. Arm-op
decision: reuses **0xf06 with mode parameter args[0]**: 0 = disabled
(unchanged), 1 = enabled, other = refuse; proxy client pads args to
zeros, so existing scripts stay disabled by default. Producer: new
`nvme_adopt_handoff_enabled()` refuse-and-stop gate (NVMe init, ASC
running, RTKit on, BOOT_STATUS OK, CC.EN set, CSTS RDY set, CFS
clear); on pass returns WITHOUT Delete SQ/CQ, shutdown, disable, IOQ
zeroing, SART freeing, sleep, PMGR reset; `nvme_shutdown()`
enabled-armed branch re-checks then panics if the retained controller
stopped before handoff. Consumer (apple.c only, 57 diff lines):
`adoption_mode` enum (NONE/DISABLED/ENABLED), gate prints
`ADOPT-PRE-ENABLED` / `ADOPT-PRE-ENABLED-FAILED`, `ADOPT-DISABLE`
before/after prints around the existing unconditional disable.
Shutdown-block audit resolved: reset_work block
`if (is_running && !adopted)` **cannot be proven inert** for enabled
mode, so skipped when `adoption_offered` (condition
`… && !adopted && !adoption_offered`); an earlier global-replace
error also touched shutdown()/suspend() and was reverted — first
kernel build `d1726c56…` is DISCARDED. FDT-parser fix REGRESSION PASS
vs dtc on the Oct 28 DTB. Payloads: producer
`35945d411fe46a6dbb7e869aa933350d4767a2666390eda56ed73e857d55968c`
(3,932,160 bytes), kernel
`65d166c8d0ac83f39a71a31b47f0686143e6498103f43b48dd0275b2ebb6ae3d`
(2,957,379 bytes). Note: the build's host script still calls 0xf06
with no argument (= disabled) and the C9 sequence — a future boot
script must call `p.request(0xf06, 1)`; the design's simplified
producer sequence is NOT implemented.

Enabled boot attempt 1 (Oct 29, 11:17–11:21): NOT COMPLETED — agent
stopped before the producer arm (further tool calls disabled for that
turn after a safety refusal; not a boot failure). Pre-boot verified:
all payload hashes matched; base `0x10004f58000` read twice; CTRR_D
`[0x10004e74000, 0x10004f58000)`; CTRR_C
`[0x100059c8000, 0x100059d4000)`; augmented DTB
`aa869d4cb06bb7c94f165a578b61ad731a7659caf7cd2192642a328b3e7c399e`;
chainload succeeded; enabled producer script prepared at
`run-2026-10-29-enabled-boot/run-adopt-producer-enabled.py` (one
init, one 5-LBA read set, NO shutdown/second init/second read set,
arm `p.request(0xf06, 1)`). Mac left at chainloaded enabled producer
proxy.

Enabled boot re-dispatch (Oct 29, 11:27–11:33) — FAILED, same RESET
-19 signature, Brett-photo-confirmed. Proxy premise held (base still
`0x10004f58000`, chainloaded producer intact, no silent redo).
Producer script ran clean: all 5 readback hashes matched, arm
`C9_ADOPT_ENABLED_ARM` index 210, result 1, `a=0x470001, b=1,
c=0xde71ce55` — no REFUSED dump. Prepared DTB verified (fixed parser
+ dtc): CTRR_D first, `"enabled"`, `0xde71ce55`, `0x5f`. Linux boot
11:30, cmdline exactly as specified. Brett photo 1 (mid-sequence):
NVME-SNAP `cc=00470001 csts=00000001`; ADOPT-OFFERED
`controller-state=enabled`; **ADOPT-PRE-ENABLED passed**
(`cc=00470001 csts=00000001`); ADOPT-OK `ret=0 adopted=1`;
**ADOPT-DISABLE `ret=0 cc-after=00000000 csts-after=00000000`**
(ordered disable clean); pre-mark line still present in this kernel
(consumer tree carried the premark modification — NOT reverted).
Brett photo 2 (final panel): ADOPT / WAIT / DIRECT MATCH 0 OF 5 /
NAMESPACE NO / ANS BR NA / ANS CRASH NO / RESET -19 / BOOT
`2127BB7D` / PHASE WAIT NAMESPACE / ERROR NONE. NO ADOPT-POST. Oops
none. Conclusion: **disable timing alone is NOT the cause (not a
sole cause).** SNAP2 values for this boot not in photographed frames,
not claimed. Mac verified back at proxy 11:33 (ttyACM1); Brett
confirmed "Rebooted" 11:33. Run dir
`run-2026-10-29-enabled-boot/` (RUN-NOTE.md complete).

## 4. IOQA snapshot boot — ADOPT-POST, then Oops (a success snapshot AND a new reserve finding)

Approved by Brett 11:33 ("Next: IOQA timing audit + pre-enable
snapshot"). Run dir `run-2026-10-29-ioqa-snapshot/`. Phase 1 audit
(source-backed, cause unproven): Aurora writes IOQA 0x1210 **before
enable** (depth|depth<<16, depth = max_queue_depth, minus 1 if
needs_ioq_registers); J604 skips pre-enable write on t8132
(`if (!needs_ioq_register)`), writes **after Create SQ** as
`(63)|(63<<16)` = `0x003f003f`; IOQ regs 0x1200/0x1208 after Create
SQ — matches; CAP read twice, never printed (snapshot fixes that);
timeout from core `NVME_CAP_TIMEOUT`.

Snapshot boot (disabled mode, prints-only kernel `f6a2f786…`,
disabled producer `2bf344d6`, initramfs `1057580b`, augmented DTB
`8af4c1b9…`, base `0x100040e4000`): Brett photo — ADOPT-OFFERED
disabled; ADOPT-PRE `cc=00470000 csts=00000000`; ADOPT-OK;
**NVME-SNAP-PREENABLE `cap=0000020101001040 cap_to=240 cc=00000000
csts=00000000 bst=de71ce55 sart=01ff ioqa1210=003f003f
aqa=00010001`**; **ADOPT-POST `cc=00460001 csts=00000001`** — third
enable success at that point. Then Oops in/around /init after "Run
/init as init process": "Unable to handle kernel write to read-only
memory at virtual address ffff8000040c0000" → phys
`0x100040c0000`. **Panel NOT OBSERVED (init dead), NOT a pass, NOT
a read success.** Honest gap: asq/acq/IOQ-reg/TCB-base digits from
that photo were uncertain and were NOT transcribed.

Rules IN: pre-enable 0x1210 already reads `0x003f003f` — Aurora's
exact value, inherited — so a missing pre-enable IOQA write is NOT
the missing step; moving the write before enable would be a value
no-op at that point. Timeout is not the mechanism (cap_to=240 ≈ 120
s; failures are immediate CFS). Leaves open: discriminating
comparison (failure snapshot vs success snapshot) — unmet at that
time, met later by §6.

## 5. Reserve re-examination (offline only, no boot)

Approved by Brett 11:54. Report (548 lines):
`~/j604-boot/adoption-build/reserve-reexamination-2026-10-29.md`.

**16 KiB gap is REAL in the snapshot DTB but does NOT explain the
snapshot Oops:** snapshot recorded reserve `0x10003ffc000 +
0xE4000` (verified identically in augmented.dts, dtc round-trip,
prepared-adopt.dts, both payload copies — not a
transcription/dtc artifact); recorded end `0x100040e0000`, gap
`[0x100040e0000, 0x100040e4000)` just below base
`0x100040e4000`; fault page phys `0x100040c0000` lies INSIDE the
recorded reserve, `0x20000` below the gap start. H5 (gap caused it)
RULED OUT.

**Snapshot boot is the ONLY reserve boot whose window ≠
[base−0xE4000, base)** — all 9 others match exactly; snapshot window
shifted DOWN by exactly `0x4000`, same size. Leading explanation
(hypothesis, not proven): snapshot DTB built 11:38, BEFORE chainload
11:41, and its run dir has NO query-base logs; hand computation from
base `0x100040e0000` (pre-chainload enrolled base) gives exactly
`0x10003ffc000`.

**Corrected tally:** only **3** reserve boots genuinely reached
userspace clean (Oct 28 non-adopt reserve PASS, adopt+reserve #1
PASS, Oct 29 sustained PASS) vs 1 Oops (snapshot) — other "no Oops"
reserve boots died at enable (vacuous).

**Memreserve path checks out on paper, two unproven ifs:**
kboot_prepare_dt (m1n1-upstream/src/kboot.c L2810+) preserves
/memreserve/ via fdt_open_into, only appends (DTB, m1n1 image,
CTRR_C if sysregs locked — NO CTRR_D in stock kboot, so the manual
line is Linux's only CTRR_D knowledge); linux.py L127 aborts loudly
if prepare fails; kernel `early_init_fdt_scan_reserved_mem`
(drivers/of/fdt.c L497–520) memblock_reserves every entry. Unproven
for the snapshot boot: whether the final DTB Linux received carried
the reserve (linux.py's prepared DTB was never saved — a
verification gap) and whether the faulting page was a buddy page.

**Ranked Oops hypotheses:** H1 (most plausible) non-buddy mapping
(ioremap/fixmap, DMA/CMA carveout, early mapping — reserve prevents
allocation, not hardware enforcement on a page mapped by another
route); H2 (plausible, unproven) reserve never reached Linux's
memblock list; H3 (low) linear-map derivation wrong for this boot;
H4 (low, unfalsifiable now) different mechanism coincidentally
in-window. **No ESR/CPU/PID/pc/call trace exists for the snapshot
Oops — do NOT copy Oct 28's ESR 0x9600004f onto it.**

**CTRR_D caveat at the time:** `[base−0xE4000, base)` was an
inference (patch comment + 912 KiB); live CTRR_D_LWR/UPR never
dumped; inversion `[base−0xE8000, base−0x4000)` unexcluded (fault
page inside both windows). Also: the snapshot note's CTRR_C
`[0x100059c8000, 0x100059d4000)` belongs to the ENABLED boot, not
the snapshot boot (snapshot top_of_kdata `0x10004bc8000`).

**Proposed fix (primary):** self-verifying reserve script —
chainload FIRST, base twice after chainload, live CTRR_D sysreg
readback asserting the formula window, DTB assertions incl. linux.py
prepared-DTB read-back, plus `memblock=debug` on the verification
boot. Alternatives listed, not primary: (A) widen reserve to
[base−0xE8000, base); (B) CTRR-patched m1n1 as proxy (proxy change
Brett hasn't approved); (C) reserved-memory node; (D) re-run
snapshot unchanged.

## 6. Reserve verification boot — gates all passed, enable FAILED, memblock NOT captured

Approved by Brett 12:01 ("Yes, run the self-verifying reserve
verification boot"). Run dir `run-2026-10-29-reserve-verify/`.
Brett rebooted to proxy; agent proceeded.

**Gates all passed:** chainload first (disabled producer
`2bf344d6`, raw mode `chainload.py -r` — a first non-raw attempt
failed at MachO parse before loading anything, harmless); base read
twice after chainload: **`0x10004834000`**; top_of_kdata
(chainloaded) `0x10005318000`. **FIRST live CTRR_D sysreg dump on
J604:** `CTRR_D_LWR_EL1 = 0x10004750000`, `CTRR_D_UPR_EL1 =
0x10004833000` → `[0x10004750000, 0x10004834000)`, size `0xE4000` —
**EXACTLY [base−0xE4000, base); formula CONFIRMED, inversion
EXCLUDED.** CTRR_C sysregs: LWR `0x100052a4000`, UPR
`0x100052af000`; sysreg-derived CTRR_C `[0x100052a4000,
0x100052b0000)` (0xC000) but stock kboot reserves CTRR_C as
`0x100052a4000 / 0xB000` (UPR−LWR, no +4K page) — one-page
kboot-vs-patch difference, recorded not interpreted; **CTRR_C is NOT
at [top_of_kdata−0xC000, top_of_kdata) — do not use the
top_of_kdata formula for CTRR_C.** Augmented DTB `9cec9df9…`:
exactly one memreserve line `/memreserve/ 0x0000010004750000
0x00000000000e4000`, `start+size == base`, both inputs. Producer arm
0xf06 result 1, both C9 read sets 5/5, prepared DTB verified (fixed
parser + dtc). **Gate 5 PASSED — linux.py prepared-DTB read-back**
(separate proxy session replicating linux.py's DTB path; saved
`linux-prepared-readback.dtb` `40abb437…`): first reservation =
CTRR_D `0x10004750000 / 0xE4000`, matching; only difference vs
producer DTB is an added 5th reservation for the initrd — expected.
Kernel `f6a2f786…` (snapshot prints-only lineage). Cmdline exactly
as baseline plus `memblock=debug` (the ONLY change, diagnostic only).

**Boot FAILED, classic signature (Brett photos, logpages 1/3–3/3):**
LOGPAGE 1/3 CRC `8E922DA4` — SNAP `BOOT=DE71CE55 CSTS=00000000
SART=01FF CC=00474000`, OFFERED DISABLED, PRE `CC=00474000
CSTS=00000000`, OK `RET=0 ADOPTED=1`, RB dumps (NUM_TCBS
`0000003F`, intended 63, AQA `00010001`, ASQ
`0x0000010003878000`, ACQ `0x0000010003874000`, TCB ADMIN BASE
`0x000001000387C000`). Note ADOPT-PRE `cc=00474000` (SHN bit SET)
matches Oct 28 disabled runs, unlike snapshot boot's `00470000` —
print-point/tree difference, not interpreted. LOGPAGE 2/3 CRC
`677539C9` — **SNAP-PREENABLE `CAP=0000020F0010040 CAP_TO=240
CC=00000000 CSTS=00000000 BST=DE71CE55 SART=01FF IOQA1210=003F003F
AQA=00010001 ASQ=0000010003878000 ACQ=0000010003874000
IOQ_CQES1208=0000010007990000 IOQ_CMDS1200=000001000798C000
IOQ_TCB=0000010003888000 MAXDEPTH=64 NEEDS_IOQ=1`**, then "DEVICE
NOT READY: ABORTING INITIALISATION. CSTS=0x2". (CAP differs from
snapshot boot's `0000020101001040` — recorded verbatim, not
interpreted. This failure snapshot + the snapshot boot's success
snapshot now AGREE on ioqa/cap_to/cc/csts — none of those fields
explains the difference.) LOGPAGE 3/3 CRC `F22FE387` — SNAP2
`CC=00460001 CSTS=00000002`, "RESET FAILURE STATUS: -19". **NO
ADOPT-POST.** Panel (webcam): intermediate ADOPT/WAIT/0 OF 5/RESET
-19/BOOT `0FF00DF3`, final ADOPT/**FAIL**/0 OF 5/NAMESPACE NO/RESET
-19/BOOT `0FF00DF3`/PHASE NO NAMESPACE/**ERROR NO NVME**. Oops none
(died at enable).

**Criterion (A) memblock_reserve dump: NOT CAPTURED** (host log has
no console lines; webcam early-boot frames illegible). **H2 is
neither proven nor disproven by this boot — do not cite it as
memblock evidence either way.** What stands: DTB delivery to Linux
is verified (gate 5); whether Linux's memblock list contains the
reserve remains unobserved (would need a readable memblock dump or
serial console — NOT approved).

**Score after this boot: 3/14 overall; with reserve 2/8**
(adopt+reserve #1 S, repeat F, lo-hi F, SHN-free F, pre-mark F,
enabled F, snapshot S, reserve-verify F). Interpretation: reserve
verified end-to-end and enable failure unchanged — **the enable
failure is independent of reserve correctness for this boot.** Next
discriminating step for H1/H2 is NOT another reserve tweak.

## 7. Donor integration, SOURCE-ONLY (complete)

Approved by Brett 12:26 ("Next: donor integration, source-only").
Report (451 lines):
`~/j604-boot/adoption-build/donor-integration-2026-10-29.md` (also
`run-2026-10-29-donor-integration/REPORT.md`). Patches:
`~/j604-boot/adoption-build/run-2026-10-29-donor-integration/patches/`
(P1 328 lines, P2 39, P3 131, P4+P6 58, COMBINED 513).

**Where it lives:** integration tree
`~/linux-asahi-donor-integration`, branch
`donor-integration-2026-10-29`, baseline `1e9e42dd5` (exact copy of
live tree working state), commits `ef7df001a` P1, `b287de1f7` P2,
`e35f82b99` P3, `ba3a0e71b` P4+P6, HEAD
`ba3a0e71b05e2ce2283fffbb2df6f843d4895221`. **Live tree
`~/linux-asahi` branch `asahi` at `77cb8f24c` verified untouched**
(same 16 pre-existing modified/untracked entries, nothing pushed).

**Provenance limitation (stated plainly, partially lifted later —
see §10):** fresh GitHub fetch of the Aurora fork NOT achieved at
this stage (commit hash truncated `d266c703`, full hash nowhere on
sunki, guessed full hash 404 not retried, web search conflates
aurora-silicon with ublue Aurora). Aurora line numbers carried
forward from Oct 28 verification; **every J604 line verified fresh.**
The AP-ON design (§10) later DID verify Aurora at full commit
`d266c703c13f099068284d622d397292241a0224`; the RTKit correction
at the top of this file rests on that verification, not on this
stage's carried numbers.

**Pieces:** **P1** Aurora adopted-init ordering — new
`apple_rtkit_mark_running()` (power ON, completions, system endpoint
bits CRASHLOG/SYSLOG/DEBUG/IOREPORT/UNKNOWN7/OSLOG/TRACEKIT, three
new inherited flags) called from `apple_rtkit_init(...,
premark=true)` BEFORE `mbox->rx` assignment and `mbox_start()`;
`adopt_running()` calls it idempotently; `reinit()` clears flags;
new exported `apple_rtkit_init_adopted()` /
`devm_apple_rtkit_init_adopted()`; NVMe probe uses adopted path only
when an offer is present (macsmc/dcp/sio unchanged). Rx:
`common_rx_get_buffer()` clears flag on fresh (zero-IOVA) buffer,
keeps on preset; `crashlog_rx()` warn-and-returns for a non-CPU-
visible inherited buffer — closes a real latent NULL-memcpy fault
in the old shadow-copy path (deliberate trade:
genuine-crash-while-inherited is now warn-and-ignore);
`syslog_rx_init()` after adoption = fresh ring start, clears flag;
inherited syslog LOGs still ACKed with dev_dbg. Risk LOW-MEDIUM.
**P2** adopted-early buffer acceptance — preset IOVA accepted when
`adopted || adoption_offered` (apple.c:327 area), identical handling
to post-adopt, plus `ADOPT-EARLY-BUFFER` dev_info line that fires
ONLY if a request actually arrives pre-adopt (the discriminating
evidence). Risk LOW. **P3** strict-buffer validation variant,
**DEFAULT OFF** — `apple_sart_is_protected_region()`,
`apple_nvme_validate_inherited_buffer()` (nonzero size, 4 KiB
alignment, protected containment), module parameter
`adopt_strict_buffers` (default off; reject line
`ADOPT-STRICT-BUFFER reject`). Deliberately NOT ported:
linear-map/reserved-page checks (J604 never CPU-maps an inherited
buffer) and memremap/dma_map/identity-IOVA (J604 SART allow-list IS
the identity mapping — vacuous). Risk if enabled MEDIUM-HIGH: NOT
proven producer buffers sit inside protected SART entries — must
stay OFF for the first integrated boot. **P4** lo-hi writes on
exactly the four pre-enable writes (ASQ, ACQ, ASQ_TCB_BASE,
IOSQ_TCB_BASE; apple.c:1390–1397) — **already refuted alone Oct 28,
never credit it from an integrated success without a P4-only
re-test.** **P5** IOQA snapshot retention, NO change
(NVME-SNAP-PREENABLE immediately before `nvme_enable_ctrl()`,
apple.c:1504; IOQA write NOT moved — proven value no-op). **P6**
print-only CFS-at-gate diagnostic (apple.c:1258): if `CSTS & CFS`
at the adoption branch, print `ADOPT-PRE-CFS-WARN` and PROCEED
(deliberately not a refuse gate).

**Conflicts/uncertainties:** Aurora's "RX not yet armed" assumption
verified for the NVMe probe order only (`mbox_get` doesn't arm RX,
`mbox_start` does, mark_running runs before it). **P1 subsumes
pre-mark: the old "pre-marked discovered" line will NOT appear in an
integrated boot; the new line is "RTKit: adopted-init mark_running
before mbox_start."** Enabled-mode gate unchanged; the reset_work
shutdown block is still saved by its `!adoption_offered` clause,
NOT by the new power state (P1 sets power ON at probe, so
`is_running()` is true at reset_work entry) — **that clause must
never be removed.** P3 containment unproven.

**Left out, with reasons:** Aurora `with_buffers()` (not portable —
producer publishes no buffer IOVAs/sizes in /chosen, only
ans-live/controller-state/boot-status/sart-mask; P1+P2 are the
portable subset); Aurora `can_adopt` CFS refuse gate (replaced by P6
print-only); Pro `l1_ans_leave()` as a new producer change (already
embodied twice — Oct 28 SHN-free, Oct 29 enabled retain path;
re-applying breaks comparability with the 2/8 reserve baseline);
T6040 addresses; post-enable IOQ lo-hi; retry-on-CFS; AP-ON variant;
queue reuse; Air no-PMGR-reset; IOQA write move.

**Compile check:** targeted build in integration tree only
(`ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- make
drivers/soc/apple/rtkit.o drivers/soc/apple/sart.o
drivers/nvme/host/apple.o`) EXIT 0, no errors/warnings for touched
files, new strings verified in objects. Honest correction: first
targeted build ran WITHOUT ARCH=arm64 and rewrote the copy's
`.config` to x86; restored from live tree's arm64 `.config` before
the successful build (live tree `.config` never touched, verified by
md5; x86 objects discarded). No full Image.gz at that stage.

## 8. Integrated boot attempts — build PASSED, boot2 POST, repeat FAILED

**Attempt 1, approved 12:46** (disabled mode, strict off). Run dir
`run-2026-10-29-donor-integration-boot/`. **Build PASSED:** HEAD
verified `ba3a0e71b…`; detached build (`make olddefconfig` first,
ARCH=arm64) donefile EXIT=0; **integrated Image.gz SHA-256
`61d7d3b5f06b1cdf15b97f4a33ade9c37ddf9d1f7fcd3e6fa0c5549a25d06fe3`
(2,957,993 bytes)**, CONFIG_ARM64=y, vmlinux strings verified
(mark_running, ADOPT-EARLY-BUFFER, ADOPT-PRE-CFS-WARN,
NVME-SNAP-PREENABLE). Gates passed (base `0x10004924000`; CTRR_D
`[0x10004840000, 0x10004924000)`; augmented DTB `89ee9fe4…`).
**Producer FAILED:** attempt 1 `nvme-first-init` FAILED —
`m1n1.proxy.UartTimeout` on the `nvme_init` reply (INIT_BEGIN in
trace, reply lost); retry correctly refused on contaminated producer
state. Producer-state failure, NOT a Linux boot failure, NOT an
enable verdict. Mac left at chainloaded disabled producer proxy with
NVMe touched. **Producer-attempt discipline learned:** one producer
attempt per proxy session; if `nvme_init` UartTimeout recurs, do NOT
retry in the same session — stop, record phase/error/INIT_BEGIN,
NEEDS BRETT reboot + re-dispatch.

**Boot2 (re-dispatch, approved 12:57), run dir
`run-2026-10-29-donor-integration-boot2/`:** kernel reused (Image.gz
`61d7d3b5…` re-verified); chainload `-r` exit 0; **base twice
`0x100045ec000`**; CTRR_D LWR `0x10004508000` / UPR
`0x100045eb000` → exactly `[base−0xE4000, base)`; **augmented DTB
`f34df06139d74ca9ee5be48b7982d2ef1b12208394f8e597c2914dd310e31877`**;
producer single attempt SUCCEEDED (PRODUCER_ARMED,
`C9_ADOPT_ARM` index 406, result 1, `a=0x474000, b=0,
c=0xde71ce55, d=0`; `/chosen` disabled). Prepared DTB verified.
The re-dispatch agent then STOPPED before linux.py (its session was
cut short) — NOT a boot failure.

**linux.py-only continuation (Brett approved via options widget
13:05, "Yes, run linux.py now from the armed proxy state"):** armed
state verified live (base still `0x100045ec000`); **linux.py
prepared-DTB read-back PASSED** (saved
`linux-prepared-readback.dtb` SHA
`743a2716991ee0c8e4a92bc67f89cebb6f99909a3d55b34017002932a6f98523`,
37,307 bytes; first reservation CTRR_D `0x10004508000 / 0xE4000`,
matching). Linux boot 13:06 from
`~/bootloader/proxyclient/tools/linux.py` (note:
`~/m1n1-upstream/proxyclient` path does not exist), cmdline exactly
as baseline, strict off. **Result: ADOPT-POST present** — LOGPAGE 1/3
CRC `182C2A7F` (SNAP `CC=00474000 CSTS=00000000`, OFFERED DISABLED,
**mark_running PRESENT twice**, ANSCHK **RUN=1 (new — P1 sets power
ON at probe, vs RUN=0 in prior runs)**, ADOPT-PRE, ADOPT-OK `RET=0
ADOPTED=1`, RB ASQ `0x000001000388C000` ACQ
`0x0000010003888000`); LOGPAGE 2/3 CRC `C9720899`
(SNAP-PREENABLE `CAP=0000020F0010040 CAP_TO=240 IOQA1210=003F003F
ASQ_TCB=00000100038C0000 IOQ_TCB=00000100038CC000
IOQ_CQES1208=0000010007748000 IOQ_CMDS1200=0000010007744000
MAXDEPTH=64 NEEDS_IOQ=1`); LOGPAGE 3/3 CRC `290643E2`
(**ADOPT-POST `CC=00460001 CSTS=00000001`**, RDY=1 CFS clear). NO
DEVICE NOT READY / SNAP2 CFS / RESET -19. **ADOPT-EARLY-BUFFER
(P2): NOT in sampled frames** (early-buffer theory untested by this
boot, not refuted). **ADOPT-PRE-CFS-WARN (P6): correctly silent**
(CFS 0 at PRE). ADOPT-DISABLE values NOT captured (print fell
between sampled logpage regions; not claimed). **Panel NOT OBSERVED
in webcam samples** (sampling miss, not a FAIL; no failure
signature, no Oops in frames). **Brett's photos Oct 29 13:27
confirmed the POST exactly** (same CRCs) but still no panel photo —
**panel PASS remains UNCONFIRMED**. Score after boot2: **4/15
overall, 3/9 with reserve**. Brett chose (13:27) reboot to proxy,
repeat boot next.

**Repeat boot (Brett "Booted and ready" 13:31), run dir
`run-2026-10-29-donor-integration-repeat/`:** kernel reused
`61d7d3b5…`; chainload first; **base twice `0x1000596c000`**;
CTRR_D LWR `0x10005888000` / UPR `0x1000596b000` → exactly
`[base−0xE4000, base)`; top_of_kdata (chainloaded)
`0x100050d0000`; augmented DTB `df014b4b…` (35,390 bytes, one line
`0x0000010005888000 / 0xE4000`); producer ARMED (`C9_ADOPT_ARM`
index 418, result 1, both read sets 5/5); prepared DTB verified
(CTRR_C `0x100063dc000 / 0xb000`); read-back PASSED (`7f266ff8…`,
first reservation matching). **FAILED, classic signature,
Brett-photo-confirmed:** LOGPAGE 1/3 CRC `8DCA7BBE` (mark_running
twice, RUN=1, ADOPT-OK, RB ASQ_TCB `0x0000010003990000` IOSQ_TCB
`0x000001000399C000` ASQ `0x000001000398C000` ACQ
`0x0000010003988000`); LOGPAGE 2/3 CRC `7A1C9302`
(SNAP-PREENABLE same CAP/IOQA values, then **DEVICE NOT READY
CSTS=0x2**, SNAP2 `CC=00460001 CSTS=00000002`); LOGPAGE 3/3 CRC
`B29EF6A3` (**RESET FAILURE STATUS: -19**); **panel (Brett photo):
ADOPT / WAIT / 0 OF 5 / NAMESPACE NO / RESET -19 / BOOT `B3ECC721`
/ PHASE WAIT NAMESPACE / ERROR NONE** (intermediate WAIT, recorded
as panel state at photograph time; verdict doesn't depend on
WAIT-vs-FAIL). NO ADOPT-POST anywhere. P2 not present (untested), P6
correctly silent. Oops none (died at enable). Webcam: 16 frames
checked (60–410 s, 10 s spacing 300–410 s); no final FAIL panel
captured — sampling miss, not a PASS. **Verdict: integrated tree
1/2 on enable — whole-as-defined does NOT cure CFS, first POST was
flakiness, no single piece credited; bisect P1/P2/P4-only is NOT next
(repeat-hold precondition unmet). Tally: 4/16 overall, 3/10 with
reserve** (with-reserve S: adopt+reserve #1, snapshot, boot2; F:
repeat, lo-hi, SHN-free, pre-mark, enabled, reserve-verify,
donor-repeat). Mac rebooted to proxy Oct 29 13:44. **Mid-sequence-
photo lesson (Oct 29): downstream driver-init lines after
PREENABLE in a photo are other drivers, NOT NVMe success — do not
claim POST from them.**

## 9. Next-step design (offline) — Rank 1 retry diagnostic chosen

Brett said "Please continue" 14:06. Design report (499 lines):
`~/j604-boot/adoption-build/next-step-design-2026-10-29.md`.
Integration tree verified untouched.

**Correction carried forward:** enabled-controller handoff is NOT a
candidate again (already booted, RESET -19). Queue reuse ranked
separately.

**Aurora re-verification in this design: NOT achieved** (same
fork-fetch limitation); refs carried forward from Oct 28, labelled;
chosen step does not depend on them. (Superseded in part by the
AP-ON design, which DID verify Aurora — see §10.)

**Key fresh finding — the 120-second black box:**
`nvme_enable_ctrl()` (core.c L2711+) writes CC EN, then
`nvme_wait_ready(..., (CAP.TO+1)/2, "initialisation")` with CAP.TO=240
→ **120 s wait budget**; returns "Device not ready" only on timeout
(or CSTS == ~0). Failing boots show only PREENABLE (csts=0) and
SNAP2 (csts=0x2) endpoints, nothing between; after failure
reset_work goes straight to `out` (RESET -19) with no second attempt
and no post-failure snapshot. Sticky-vs-transient unanswerable from
prior evidence.

**Ranked candidates:** (1) **Instrumented retry-on-CFS
diagnostic** — observes the 120 s wait AND re-tests the controller
in-session; separates transient / write-triggered / sticky CFS in
one boot. (2) AP-ON follow-up variant — needs contract amendment
first (contract forbids AP power renegotiation before first I/O).
(3) Queue reuse — highest cost (producer + contract change),
weakened by fresh-queue successes. (4) Pre-enable IOQA write —
nearly refuted as necessary (POSTs without it). Not ranked: strict
mode (can only reject more), P1/P2/P4 bisect (precondition unmet),
second enabled boot (refuted alone).

**Design (branch `donor-integration-retry-diag` off `ba3a0e71b`, two
files):** core.c `nvme_wait_ready` print-only (`NVME-WAIT-READY
t=%us csts=%08x` at t=0, every 10 s, on exit; enable wait only — op
`"initialisation"`); apple.c post-failure snapshot print-only
read-only after SNAP2 (line name `NVME-SNAP2-FAIL`: CC, CSTS,
BOOT_STATUS, CPU_CONTROL, SART mask, RTKit crashed/running, ASQ/ACQ
+ TCB-base readbacks, NUM_TCBS, TCB_STAT, IOQ regs, CAP re-read);
**one gated retry** (only if CFS set AND RTKit not crashed AND
BOOT_STATUS OK AND CPU RUN; else `ADOPT-RETRY-SKIP reason=...`
refuse-and-stop to `out`): `ADOPT-RETRY-ATTEMPT n=1` →
`nvme_disable_ctrl(false)` → **no settle delay** → second
`nvme_enable_ctrl()` → `NVME-SNAP3`; success prints
`ADOPT-POST-RETRY` (+ existing ADOPT-POST); failure prints
`ADOPT-RETRY-FAILED` → `out`. Count hardcoded 1, no loop, no module
parameter. Comparability: producer/initramfs unchanged; retry-POST
scored in a SEPARATE diagnostic tally (never 4/16 clean tally, never
bisect repeat-hold, never credits a piece); retry fires only on an
already-failed boot, so it cannot turn a success into a failure.
Clean POST with no retry needed would score 5/17 clean but NOT a
bisect repeat-hold (tree changed).

Brett approved (options widget, 14:21): **"Build and boot the retry
diagnostic once."**

## 10. Retry-diag attempt 1: built, gates passed, then STALLED (linux.py never ran)

Run dir `run-2026-10-29-retry-diag/`. **Build PASSED:** branch
`donor-integration-retry-diag` off `ba3a0e71b`, two files only;
detached build exit 0; **Image.gz SHA
`19ff6eb6ec73a59d1d12ec517cea15e21a80973d9ae08cfb41ad6c26411ed77e`
(2,958,898 bytes)**, strings verified; live tree untouched.

**Gates all passed:** `/dev/m1n1 -> ttyACM0`; chainload raw exit 0;
**base twice `0x1000541c000`**; CTRR_D sysregs
`[0x10005338000, 0x1000541c000)` exactly `[base−0xE4000, base)`;
augmented DTB `47672a21…` (35,390 bytes, one line); producer ARMED
(`C9_ADOPT_ARM` index 427, result 1, both read sets 5/5, `/chosen`
disabled/`0xde71ce55`/`0x5f`); prepared DTB verified (m1n1 image
`0x1000541c000 / 0x3c0000`, CTRR_C `0x10005e8c000 / 0xb000`);
read-back PASSED (`a1ff29bf…`, first reservation CTRR_D
`0x10005338000 / 933888`). Strict off.

**Then the agent stopped** (a tool call in its session was removed
by a safety classifier; agent instructed not to continue/
reconstruct that step). **Observer agent (observe-only)
established: linux.py NEVER RAN** — no `linux.py`/`script -qec`
process, **no `linux-boot.log` in the run dir at all**; only process
alive was the webcam ffmpeg recorder (PID 111080, holding
/dev/video0). `/dev/m1n1` mtime 14:24; `host-result.json` still
PRODUCER_ARMED (base `0x1000541c000`). Brett's photo 14:36 + two
webcam frames: screen **identical, frozen at the chainloaded
producer's FDT-prepared display** ("FDT prepared at
`0x100084d0000`", m1n1 logo) — NOT a boot in progress. **Verdict:
STALLED, not failed; no wait series / SNAP2-FAIL / retry outcome /
panel exists; tally unchanged (4/16); no piece credited or
refuted.** Record appended to that run dir's RUN-NOTE.md with
`frame-fdt-560s.jpg` / `frame-fdt-latest.jpg`.

**Standing lesson from two interrupted runs (enabled attempt 1,
retry attempt 1):** when a run agent stops mid-sequence, do NOT
assume the boot state — verify Mac/proxy state independently
(process list, linux-boot.log existence, screen) before acting; do
NOT re-dispatch the same step through the stopped agent.

Brett chose (options widget, 15:15): **"Reboot to proxy and
re-dispatch the retry boot fresh."** New run dir for the
re-dispatch; kernel `19ff6eb6…` reused (re-verify hash, no rebuild).

## 11. Retry-diag2 boot: FAILED, CFS sticky (the diagnostic's answer)

Run dir `run-2026-10-29-retry-diag2/` — RUN-NOTE 195 lines,
`cam-boot.mkv` (242 MB), follow-up `cam-panel.mkv` (49 MB), frames
60–590 s + panel sweep at 10 s spacing. Kernel reused (no rebuild).
Gates redone fresh (new base/DTB — values in run note; augmented
DTB `32e0fba1…`, read-back first reservation CTRR_D
`0x10004e9c000 / 933888`). **New guard added this run and kept for
all future runs: verify linux.py actually started (process alive +
`linux-boot.log` created) within 60 s of invocation, or stop and
report — no silent loop.**

**Brett-photo-confirmed logpages (CRCs match webcam exactly):**
- **1/4 CRC `A933CCF9`:** SNAP `BOOT=DE71CE55 CSTS=00000000
  SART=01FF CC=00474000`; OFFERED DISABLED; mark_running twice;
  ANSCHK RUN=1; ADOPT-PRE `CC=00474000 CSTS=00000000`; inherited
  endpoints marked; ADOPT-OK `RET=0 ADOPTED=1`; RB (NUM_TCBS
  `0000003F`, ASQ_TCB `0x0000010003884000`, IOSQ_TCB
  `0x0000010003890000`, intended 63, AQA `00010001`, ASQ
  `0x0000010003880000`, ACQ `0x000001000387C000`, TCB_STAT
  `00000000`, LIN_SQ_CTRL `00000001`).
- **2/4 CRC `0AC9CF6A`:** TCB dumps; SNAP-PREENABLE
  `CAP=0000020F0010040 CAP_TO=240 CC=00000000 CSTS=00000000
  BST=DE71CE55 SART=01FF IOQA1210=003F003F AQA=00010001
  ASQ=0000010003880000 ACQ=000001000387C000
  IOQ_CQES1208=0000010008074000 IOQ_CMDS1200=0000010008070000
  ASQ_TCB=0000010003884000 IOQ_TCB=0000010003890000 MAXDEPTH=64
  NEEDS_IOQ=1`; then **WAIT-READY `T=0S CSTS=00000000`**, syslog-
  no-buffer line.
- **3/4 CRC `11196130`:** WAIT-READY **`T=10S`–`T=120S` ALL
  `CSTS=00000002`** (no flicker, no intermediate values); DONE
  `T=120S CSTS=00000002 RET=-19`; DEVICE NOT READY `CSTS=0x2`;
  SNAP2 `CC=00460001 CSTS=00000002`; **SNAP2-FAIL: no field moved
  vs PREENABLE** (BST `DE71CE55`, CPU `00000010`, SART `01FF`,
  RTK_CRASHED=0, RTK_RUNNING=1, same ASQ/ACQ/TCB/IOQ values,
  NUM_TCBS `0000003F`, TCB_STAT `00000000`, CAP
  `0000020F0010040`); **ADOPT-RETRY-ATTEMPT `N=1`**;
  **ADOPT-RETRY-DISABLE `RET=0 CC=00460000 CSTS=00000002` —
  disable returned 0 but CSTS stayed 0x2 (CFS persists through
  disable)**; second wait `T=0S CSTS=00000002`, `T=10S
  CSTS=00000002`.
- **4/4 CRC `09BC72B1`:** second wait `T=20S`–`T=120S` ALL
  `CSTS=00000002`; DONE `T=120S RET=-19`; DEVICE NOT READY;
  **SNAP3 `CC=00460001 CSTS=00000002`**; **ADOPT-RETRY-FAILED**;
  **RESET FAILURE STATUS: -19**. **NO ADOPT-POST, NO
  ADOPT-POST-RETRY anywhere.**

**Correction vs webcam (Brett supersedes):** agent's webcam
frame-450 misread second-wait `T=0S` as CSTS=0; Brett's logpage 3/4
shows `T=0S CSTS=00000002` — **retry starts ALREADY FAULTED** (vs
first attempt T=0 CSTS=0). Strengthens the sticky branch.

**Panel:** follow-up recording (`cam-panel.mkv`, from 15:30)
sampled 10 s spacing × 90 s — logpages cycling, **no panel frame in
that window** (panel slot falls outside it). Panel verdict = webcam
panel from main recording (t=300): **ADOPT / WAIT / 0 OF 5 /
NAMESPACE NO / ANS BR NA / ANS CRASH NO / RESET -19 / BOOT
`A7CE3F2D` / PHASE WAIT NAMESPACE / ERROR NONE** (intermediate
WAIT, not final FAIL; verdict doesn't depend on WAIT-vs-FAIL). No
final FAIL panel captured in either recording. Oops none (died at
enable, never reached /init reads).

**ADOPT-EARLY-BUFFER and ADOPT-PRE-CFS-WARN: confirmed ABSENT
across all four photographed logpages** (not just webcam samples).
Early-buffer theory remains untested, not refuted; P6 correctly
silent (CFS 0 at PRE).

**Interpretation (design matrix): STICKY branch** — CFS arrives
within the first 10 s after the enable write (T=0 was 0, T=10 already
2), then frozen; retry fails identically and starts already
faulted; disable does not clear CFS; SNAP2-FAIL unmoved. NOT a
first-write race (retry did NOT post), NOT time-dependent firmware
competition (no flicker/late arrival), NOT partial-progress-then-
fault (no intermediate CSTS), NOT a new retry signature.
**Transient branch CLOSED; do NOT repeat the diagnostic. Next: Rank
2 AP-ON, then Rank 3 queue reuse.** Clean tally stays **4/16**;
retry tally: POST 0/1, failed 1/1 (evidence only). Brett rebooted to
proxy Oct 29 15:35 ("Done!").

## 12. AP-ON (Rank 2) design + Amendment A1

Brett said "Let's do it" 15:37. Design report (554 lines):
`~/j604-boot/adoption-build/apon-design-2026-10-29.md` (on sunki).
Offline only; live tree untouched.

**Precise action:** exactly ONE real RTKit mailbox message,
`SET_AP_PWR_STATE` state ON (type `0xb`), via already-exported
`apple_rtkit_set_ap_power_on()` (J604 rtkit.c L936–943 →
`set_ap_power_state()` L913–935); ACK waited on under the function's
own 1 s bound and verified (return 0 only if ACK arrives AND
ACK-updated `ap_power_state` == ON = `0x20`). **Kernel only**,
apple.c reset_work. **No producer change** (baseline `2bf344d6…`
preserved for comparability).

**Slot A (primary):** immediately AFTER `ADOPT-OK` (apple.c
L1276–1279) and BEFORE the unconditional `nvme_disable_ctrl()` block
(which clears the producer's SHN state `00474000`). **Slot B
(reserved):** same message immediately before `nvme_enable_ctrl()`
after SNAP-PREENABLE — unlocked ONLY by the matrix row-5 signal
(VERIFY shows AP state reverted during disable/queue programming).
A Slot A identical failure does NOT trigger Slot B.

**Prints (dev_err):** `ADOPT-AP-ON-BEFORE` (iop/ap here are Linux
*bookkeeping* values, explicitly not firmware state),
`ADOPT-AP-ON` (ret, ap_after = ACK-updated value; printed even on
refusal), `ADOPT-AP-ON-REFUSED reason=...` (one of `ap_on_failed`,
`ack_state_mismatch`, `rtk_crashed`, `boot_status_changed`,
`cpu_stopped`, `cfs_after_message`), `ADOPT-AP-ON-VERIFY`
(immediately before enable, after SNAP-PREENABLE — observational,
NOT a second gate: if it shows reversion/CFS, boot still proceeds to
enable so the reversion is recorded as evidence).

**Gate (refuse-and-stop):** proceed to disable/queue/enable ONLY if
ret==0 AND ap_after==ON AND !is_crashed AND BOOT_STATUS==OK
(`0xde71ce55`) AND CPU RUN set AND !(CSTS & CFS); otherwise `goto
out` exactly as today. NEVER fall through to enable on refusal,
NEVER wake/boot/PMGR path, NEVER IOP fallback, ONE message attempt
per boot, no re-send.

**Must NOT do:** no INIT/HELLO/EPMAP/STARTEP/SLEEP/PMGR reset/SART
change/queue-address change/IOQA move/CC-CSTS write other than the
message; no change to adoption gate, ADOPT-PRE/OK prints, PREENABLE
snapshot, lo-hi writes, `out` path, or the reset_work shutdown guard
(`is_running && !adopted && !adoption_offered`). **Risk stated
plainly:** the message could in principle stall/crash ANS if
firmware treats a second SET_AP_PWR_STATE as a transition;
mitigations structural (1 s bound, gate, RAM-only, one attempt); a
crash from the message IS a result (matrix row 4).

**Why distinct from P1:** P1 `apple_rtkit_mark_running()` (rtkit.c
L759–777; called from `apple_rtkit_init(..., premark_inherited=true)`
before `mbox->rx`/`mbox_start()`, and idempotently from
`apple_rtkit_adopt_running()` L1002–1020) sets `iop_power_state`/
`ap_power_state` = ON as **Linux-side variables only, sends NO
mailbox message**. ANSCHK RUN=1 is Linux's bookkeeping conclusion
(`is_running()`, rtkit.c L89–99), not a firmware ACK. AP-ON adds the
missing half: a real message with a verified ACK. **Hypothesis
pair:** H-AP1 (firmware gates enable on SET_AP_PWR_STATE ON from the
*current session owner* — producer negotiated with its session;
Linux never re-presented it → CFS within 10 s of CC.EN;
discriminator: ACKed AP-ON → POST) vs H-AP0 (bookkeeping suffices /
handshake carries over; discriminator: ACKed AP-ON → identical
RESET -19). Plausibility asymmetry: J604's disabled mode ALWAYS
disables + recreates queues (touches controller more than Aurora's
adopted consumer, which disables only if CC.EN set). **IOP
excluded:** SET_IOP_PWR_STATE is ANS-side (static in J604, not
exported, shutdown/sleep paths only); IOP variant is NOT automatic
after an AP-ON failure — needs its own design + amendment. **Genpd
disambiguation:** contract H7 domains (`ps_ans`,
`ps_apcie_sys_st`, `apple_nvme_attach_genpd()` apple.c L1848–1880)
are Linux genpd for ANS hardware blocks — AP-ON does not touch them
or the DTB; H7 unchanged.

**Aurora re-verification — ACHIEVED in this design:** GitHub API
resolved truncated `d266c703` to full commit
**`d266c703c13f099068284d622d397292241a0224`**
(aurora-silicon/linux, 2026-10-28); rtkit.c + apple.c fetched and
read. Verified: `apple_rtkit_mark_running()` rtkit.c L1192–1217;
`__apple_rtkit_init()` calls it L1382–1383 when adopted, BEFORE
`claim_rx()`/`mbox_start()` (Oct 28 "L1381–1389" was the call site,
confirmed); `apple_rtkit_init_adopted()` L1415;
`apple_rtkit_init_adopted_with_buffers()` L1458;
`apple_rtkit_adopt_running()` L1637–1645 calls mark_running, returns
0 — **sends NO management message, in particular NO
SET_AP_PWR_STATE** (Aurora's adopted path is bookkeeping-only, like
J604's P1); Aurora NORMAL boot path `apple_rtkit_boot_common()` ends
with `set_ap_power_state(ON)` (L1628), `early_ap_power` variant
sends it before the IOP power ACK wait (L1604–1613); Aurora apple.c
adopted path (L1604–1632): adopt_running, disable only if CC.EN
set, `goto rtkit_ready`, no AP message. Wait difference recorded,
not fixed: Aurora's `set_ap_power_state()` waits via
`apple_rtkit_wait()` (polls mailbox when `sync_syslog_ack` set);
J604's uses plain `wait_for_completion_interruptible_timeout(...,
1000 ms)` — a candidate explanation if AP-ON times out (matrix row
3). **Correction to the next-step design's Rank 2 framing:** AP-ON
does NOT port Aurora's adopted path; it tests a NEW hypothesis —
J604 firmware requires the normal boot path's final step even for an
adopted session. The design depends on J604 code read fresh, not on
Aurora line numbers.

**Branch / diff discipline:** new branch
**`donor-integration-apon` off clean integration HEAD `ba3a0e71b`**
— NOT off retry-diag (retry-diag checkout carries an uncommitted
101-line diff with RETRY LOGIC that changes the failure path; an
AP-ON result via retry would be uninterpretable). **Carried
(print-only, path-neutral, each marked `/* J604 DIAGNOSTIC —
print-only, remove for any clean tree */`):** core.c wait-series
prints, apple.c SNAP2-FAIL print block. **Excluded (must NOT
appear):** retry attempt/disable/enable, SNAP3, ADOPT-POST-RETRY,
ADOPT-RETRY-FAILED, ADOPT-RETRY-SKIP, any settle delay, any module
parameter. **Builder MUST diff vs `ba3a0e71b` and verify the diff
contains ONLY (i) apple.c AP-ON block + VERIFY print, (ii) core.c
wait-series prints, (iii) apple.c SNAP2-FAIL print block — any other
file/hunk stops the build from proceeding to boot.**

**Scoring (fixed in advance):** clean tally 4/16 NEVER moves on an
AP-ON outcome, even POST + panel PASS. **AP-ON tally (separate,
new):** POST / identical-failure per boot; **REFUSED is NOT scored
as an enable failure** (no enable attempted); panel PASS vs
POST-only recorded separately. An AP-ON POST does NOT count as a
P1/P2/P4 bisect repeat-hold. A single AP-ON POST triggers ONE
unchanged repeat; 2/2 makes AP-ON the leading mechanism → next is an
ATTRIBUTION design (AP-ON-only on a minimal tree), NOT clean-tally
entry, NOT single-piece credit; repeat fails → AP-ON joins the flaky
set (1/2 own tally), no default AP-ON+queue-reuse combination. **If
AP-ON fails identically, the AP-ON tree is RETIRED** (as retry-diag
was); Rank 3 queue reuse is then designed on the INTEGRATED tree,
not the AP-ON tree.

**Interpretation matrix (design §8, fixed):** row 1 ACK OK + gate
passes + VERIFY still ON + POST → H-AP1 supported → repeat AP-ON
unchanged once. Row 2 ACK OK + gate passes + VERIFY still ON +
IDENTICAL failure → H-AP0, AP-ON refuted as sole cause → tree
retired, amendment lapses, next Rank 3 queue reuse on integrated
tree, do NOT repeat AP-ON. Row 3 REFUSED `ap_on_failed` (no ACK
within 1 s) → NO enable verdict, NOT scored, do NOT proceed/
re-send/go to queue reuse on this evidence → next: message-path
investigation. Row 4 REFUSED `rtk_crashed`/`boot_status_changed`/
`cpu_stopped`/`cfs_after_message` → message disturbed the session
→ NOT scored, do NOT repeat the message, audit message path before
ANY further power experiment; AP-ON as enable candidate suspended.
Row 5 ACK OK + gate passes but VERIFY shows ap reverted or CFS
already set before enable → handshake doesn't survive disable/queue
programming; next: Slot B (ONLY unlocked by this row) or
disable-interaction investigation. Row 6 ACK OK + wait series
CHANGES shape vs diag2 but still fails → design isolating what
changed; do NOT combine changes by default. Row 7 ACK OK + POST but
panel NOT OBSERVED → AP-ON tally 1/1, panel open; repeat's panel
capture is the priority. Row 8 EARLY-BUFFER or PRE-CFS-WARN fires
for the first time → record separately, do NOT conflate with the
AP-ON verdict.

**Boot plan (design §7):** mode DISABLED; producer `2bf344d6…` +
initramfs `1057580b…` re-verified, unchanged; kernel REBUILT from
the AP-ON branch; strict OFF; reserve gates identical to
boot2/repeat/diag2 (chainload first raw mode; base twice after
chainload, never a previous base; live CTRR_D sysreg assert
`[base−0xE4000, base)` — mismatch = major finding, sysreg window
used and stated; fresh augmented DTB one line, dtc round-trip,
start+size == base, non-overlap, both inputs; arm result 1; prepared
DTB verified with fixed parser; read-back first-entry; any gate
failure stops before linux.py; UartTimeout guard; linux.py-started
60 s guard); cmdline EXACTLY as baseline.

**Amendment A1 — APPROVED and RECORDED Oct 29 (Brett, options
widget 15:48):** Brett tapped **"Approve Amendment A1, build and
boot AP-ON Slot A once."** Muse appended §6A to the contract file
in the same turn, with the §6 C1 consequential edit (first sentence
read "…AP/IOP power renegotiation (EXCEPT the single AP-ON message
permitted by Amendment A1, §6A), SLEEP, PMGR reset, and any SART or
buffer reallocation"), and two §7 checklist items. No other
contract section changed; §3 H7 untouched. **Amendment A1 (§6A)
substance:** ONE experiment, DISABLED mode (Option A) only,
integrated tree + AP-ON block per `apon-design-2026-10-29.md` §4;
the ONLY exception to §6 C1. PERMITTED (only this): consumer in
reset_work, immediately after ADOPT-OK and before the unconditional
disable, may send exactly ONE `SET_AP_PWR_STATE` ON
(`apple_rtkit_set_ap_power_on()`), wait for ACK under the function's
own 1 s bound, print BEFORE / AP-ON / VERIFY snapshots; may proceed
to disable/queue/enable ONLY if the gate passes (ACK received, ACK
state ON, RTKit not crashed, BOOT_STATUS OK, CPU RUN set, CFS clear
after the message); otherwise refuses and stops via the existing
`out` path. REMAINS FORBIDDEN (unchanged): INIT, HELLO, HELLO_REPLY,
EPMAP renegotiation, STARTEP for any inherited endpoint,
SET_IOP_PWR_STATE in any form, any second SET_AP_PWR_STATE in the
same boot, SLEEP, PMGR reset, SART or buffer reallocation, queue
reuse, IOQA write reordering, enabled mode, any producer-side power
message; producer obligations (§4 P1–P5) unchanged — producer sends
NO power message under this amendment. REVERSIBILITY/EXPIRY:
experiment-scoped exception, not a standing permission — if the
AP-ON boot fails identically (ACK OK, same RESET -19), the amendment
LAPSES on that boot's completion; if it POSTs, the amendment
remains in force ONLY for the AP-ON repeat boot and no other
purpose; if REFUSED at the handshake gate, it lapses for enable
purposes and the next step is message-path investigation (matrix
rows 3/4), not another power experiment under this amendment. RUN
HEADER: any run under this amendment MUST record "contract
2026-10-28 + Amendment A1 (AP-ON, Slot A, one message)" alongside
mode (DISABLED), producer hash, kernel hash, DTB hash.

## 13. AP-ON build + boot: REFUSED, §8 ROW 4 (complete)

Dispatched Oct 29 ~15:49 (agent, completed 16:14). Run dir
`~/j604-boot/adoption-build/run-2026-10-29-apon/` (RUN-NOTE 96
lines, build log, diff audit, reserve assertions, prepared-DTB
read-back, linux-boot.log, cam-boot.mkv 45,264,565 bytes 97.6 s,
frames; webcam frames also at `~/workspace/m4-frames-apon/`).

**Build passed, diff audit passed:** branch
`donor-integration-apon` off clean HEAD `ba3a0e71b` (retry-diag's
uncommitted 101-line retry diff preserved to
`retry-diag-working-diff-preserved.txt` and discarded first). Diff
vs `ba3a0e71b`: 4 files, 140 insertions, 2 deletions — ONLY (i)
apple.c AP-ON block + VERIFY, (ii) core.c wait-series prints, (iii)
apple.c SNAP2-FAIL print-only block; forbidden strings absent (no
ADOPT-RETRY/SNAP3/POST-RETRY/SET_IOP/settle delay/module
parameter). One documented deviation: a small exported read-only
accessor `apple_rtkit_power_states()` (rtkit.c + rtkit.h, 15 lines)
because iop/ap bookkeeping lives in rtkit's internal struct.
**Image.gz SHA-256
`0b07cc7fd34a67136d147eb6e5e774f38e6b38f60af7f7e51611fcd53501baf8`
(2,959,218 bytes)**, CONFIG_ARM64=y, strings verified. Live tree
untouched.

**Gates all passed:** `/dev/m1n1 -> ttyACM0`; `/root/.ssh` empty on
first contact, restored from `/home/hatch/.ssh`. Chainload first
raw mode; **base twice `0x10004658000`**; live CTRR_D sysregs LWR
`0x10004574000` / UPR `0x10004657000` → exactly
`[base−0xE4000, base)`; augmented DTB **`3c4dd4d4…`** (35,390
bytes, one line, start+size == base, both inputs); producer ARMED
(`C9_ADOPT_ARM` index 421, result 1, `a=0x474000, b=0,
c=0xde71ce55, d=0`, both read sets 5/5); prepared-adopt.dtb verified
(prepared FDT `0x1000770c000 / 0x20a3e`, m1n1 image
`0x10004658000 / 0x3c0000`, CTRR_C `0x100050c8000 / 0xb000`);
linux.py prepared-DTB read-back PASSED (`1e13f329…`, first
reservation CTRR_D `0x10004574000 / 933888`). Strict OFF. linux.py
started 15:59:12 under pty, started-guard PASSED (process alive +
linux-boot.log), bootargs exactly as specified.

**Brett's FDT photos (~15:57) reconciled:** the two frames ("FDT
prepared at `0x1000770c000`") were **this run's producer
FDT-prepared display** left on screen before linux.py took over —
NOT a stall (retry-diag stall address was `0x100084d0000`) and NOT a
linux.py handoff stage; proof: at check time linux.py had not
started and `0x1000770c000` is this run's own prepared DT address.

**Panel — Brett-photo-confirmed, OUT-PATH panel (not an
enable-failure panel):** intermediate WAIT (ADOPT / WAIT / 0 OF 5 /
NAMESPACE NO / ANS BR NA / ANS CRASH NO / RESET -19 / BOOT
**`419EEC80`** / PHASE WAIT NAMESPACE / ERROR NONE); webcam
frame-60 = final FAIL panel (same BOOT id; ADOPT / FAIL / PHASE NO
NAMESPACE / ERROR NO NVME). It follows the refused gate's `out`
path — must NOT be misread as row 2 evidence; no enable was
attempted.

**Logpage — Brett-photo-confirmed, SINGLE page, CRC `EF084F39`**
(webcam frames 70/80/90 identical): SNAP `BOOT=DE71CE55
CSTS=00000000 SART=01FF CC=00474000`; OFFERED DISABLED; mark_running
twice; ANSCHK `CPU=00000010 BST=DE71CE55 RUN=1`; ADOPT-PRE
`CC=00474000 CSTS=00000000`; inherited endpoints marked; ADOPT-OK
`RET=0 ADOPTED=1`; **ADOPT-AP-ON-BEFORE `IOP=32 AP=32 BST=DE71CE55
CPU=00000010 CC=00474000 CSTS=00000000 SART=01FF`**;
**ADOPT-AP-ON `RET=-62 AP_AFTER=32 IOP=32 BST=DE71CE55
CPU=00000010 CC=00474000 CSTS=00000002 SART=01FF`**;
**ADOPT-AP-ON-REFUSED `REASON=CFS_AFTER_MESSAGE RET=-62
AP_AFTER=32 BST=DE71CE55 CPU=00000010 CC=00474000 CSTS=00000002
RTK_CRASHED=0`**; `RESET FAILURE STATUS: -19`. **Absent and
therefore nonexistent for this boot:** no SNAP-PREENABLE, no
VERIFY, no WAIT series, no DEVICE NOT READY, no SNAP2/SNAP2-FAIL,
no ADOPT-POST, no RB/TCB dumps, no disable values. EARLY-BUFFER
absent (theory untested); PRE-CFS-WARN correctly silent (CFS 0 at
PRE). Oops NONE.

**Interpretation — §8 ROW 4, explicitly NOT row 2:** ACK never
arrived (ret=-62, timeout-class, no ACK within 1 s); gate REFUSED;
**CSTS 0 at BEFORE → 2 at AP-ON/REFUSED — CFS set in the window of
the single AP message (or its 1 s ACK wait), before any disable or
enable** (CC still `00474000` throughout); ap_after 32 is
bookkeeping ON preset by mark_running, NOT ACK-updated; BST OK, CPU
RUN, RTK_CRASHED=0 — disturbance is a CFS fault, not crash/status/
CPU stop. Gate priority correctly yields `cfs_after_message` over
`ap_on_failed`; the -62 recorded alongside. Fast panel (~1 min
after linux.py start) confirms no 120 s wait (enable never
attempted). **Consequences (fixed in advance):** NOT scored as an
enable failure; do NOT repeat the message; do NOT go to queue reuse
on this evidence; next step is a **message-path audit** before ANY
further power-messaging experiment; **AP-ON as an enable candidate
SUSPENDED pending that audit (tree suspended, not retired); NOT a
queue-reuse trigger.** Late-ACK/polling-wait sub-question stays open
inside the audit but cannot be probed by re-sending under lapsed A1.
**Amendment A1 LAPSED for enable purposes on this refused boot.**
Tallies: clean unchanged **4/16**; **AP-ON tally REFUSED 1/1, not
scored** (POST 0/0, identical-failure 0/0). Brett re-photographed
the same logpage 16:17 and confirmed "Back at the proxy."

## 14. Message-path audit design (complete, offline)

Brett said "Let's do it" 16:18. Deliverable:
`~/j604-boot/adoption-build/message-path-audit-design-2026-10-29.md`
(1,035 lines, 58,338 bytes, md5
`c5fec2e794a7b5e44e5f72a726352f88`; identical local copy at
`~/workspace/message-path-audit-design-2026-10-29.md`). All code
claims re-read fresh, incl. Aurora rtkit.c at full commit
`d266c703c13f099068284d622d397292241a0224`.

**Phase 1 static findings:** ret=-62 pinned (send returned 0, 1 s
wait expired, completion never signalled — not send
failure/interruption/state mismatch; state check never reached).
Send succeeded in FIFO-write sense (stuck FIFO would be -110, not
-62) → "never transmitted" refuted except "written but ignored,"
which collapses into transition-fault. Message word `(0xb << 52) |
0x20` byte-identical to producer's own boot-time ON →
encoding-malformed refuted. ACK handler unconditional
(`complete_all()` on any type-0xb EP_MGMT message) →
handler-conditional-drop refuted; but handler log is `dev_dbg`,
invisible in framebuffer logpages, so a post-deadline ACK leaves no
trace in the AP-ON boot. Two live RX gaps survive: GFP_ATOMIC
work-allocation failure in `apple_rtkit_rx` drops silently (no
print, no counter); no J604 precedent of any Linux-sent AP ACK ever
being received (normal boot path never runs for ANS on J604;
producer never ACK-waits its AP ON). Aurora's polling wait rescues
only queued-without-interrupt messages and only when
`sync_syslog_ack` is set; J604 has no such field/DT property and
the window is still 1000 ms → porting it verbatim changes nothing
on J604.

**Ranked candidates + discriminators:** 1. **(a) Firmware
transition-fault (leading)** — steady-state second ON on a live
session faults NVMe and withholds ACK; discriminator: sub-second
CSTS sampling around the FIFO write (CFS within ms of write =
send-triggered). 2. **(e) Incipient/coincidental CFS** —
variable-latency fault happened to expire in the ~1 s window;
discriminator: message-free boot with dense CSTS snapshots. 3. **(c)
Late/queued ACK (partial only)** — explains ret=-62, never CSTS
0→2; discriminator: post-refusal +0/+1/+5 s window with one RX-side
mailbox poll (sends nothing). 4. **(b) ACK-handler/RX defect
(narrowed)** — handler-drop refuted; live sub-cases silent
alloc-failure and wrong-endpoint arrival; discriminator: dev_err
alloc-failure print + per-endpoint RX counters + workqueue depth.
5. **(d) Never transmitted** — refuted in FIFO sense; residual
check composed-word print + FIFO readback. 6. **(f)
Wait-implementation defect** — sub-case of (c); discriminator: same
post-refusal poll. 7. **(g) Gate-priority masking** — not a
mechanism; reporting rule: future gates print ACK-received? and
CFS-set? as SEPARATE booleans, never a single reason string alone.

**Phased plan:** Phase 1 done (report §1 + 9-item reviewer
checklist). **Phase 2 Tier A — message-free CSTS-watch boot (NO new
amendment needed):** integrated tree `ba3a0e71b` + prints only (CSTS
snapshots at existing print points only — no inserted delay loop,
no timing variable — plus RX counters, workqueue depth, FIFO
readbacks, alloc-failure print); scored in the clean tally as an
integrated-tree boot. **Phase 2 Tier B — single-message
instrumented boot (needs new Amendment A2, skeleton in §6):** only
if Tier A shows no spontaneous pre-enable CFS; same Slot A message,
1 s bound unchanged, prints P0 (composed word), P1 (CSTS
before/after send + every 100 ms through the wait, send_ret/wait_ret
separated), P2 (ACK handler promoted to dev_err), P3/P4/P5
(alloc-failure, counters, FIFO readback), P6 (post-refusal +0/+1/+5
s sampling with one RX-side poll, no send); gate unchanged
refuse-and-stop; scored on a separate A2 tally. **Phase 3 (sketched
only, each variant needs its own narrow amendment):** 3a late-ACK
wait variant, 3b handler-fix + retest, 3c encoding-fix + retest,
3d/3e transition-fault leading or no-finding → message line CLOSED,
next queue reuse on integrated tree or a non-RTKit CFS mechanism.
Nothing in Phase 3 authorised by the design.

**Audit does NOT do (binding §4):** no AP-ON repeat, no queue reuse,
no IOQA move, no strict mode, no enabled mode, no IOP message, no
producer change, no clean-tally change, no AP-ON tally change, no
commit/push/enrolled-proxy change, no santra/Borg contact.

Brett approved (options widget, Oct 29 16:36): **"Yes, run Tier A
and draft Amendment A2 for Tier B after Tier A results."**

## 15. Tier A CSTS-watch boot: POST, clean tally 5/17

Dispatched 16:36. Run dir
`~/j604-boot/adoption-build/run-2026-10-29-tier-a-csts-watch/`
(RUN-NOTE 183 lines, build log, diff, reserve assertions,
prepared-DTB read-back, linux-launch.log, cam-boot.mkv 254,223,401
bytes, frames; webcam frames also at `~/workspace/m4-frames-tier-a/`).

**Build passed, diff audit passed:** branch
`donor-integration-tier-a` off clean HEAD `ba3a0e71b` (the apon
checkout's uncommitted 221-line AP-ON working diff preserved to
`apon-working-diff-preserved.txt` first, then discarded; AP-ON tree
suspended, not modified). Diff vs `ba3a0e71b`: 6 files, 159
insertions, 1 deletion — ONLY Tier A prints (apple.c CSTS-watch/
RX-count/FIFO helpers + 6 call sites, rtkit.c RX counters +
alloc-failure print + accessors, rtkit-internal.h, rtkit.h,
mailbox.c/h read-only A2I accessor). No message send, no register
write, no delay loop. **Image.gz SHA-256
`07ee767ac6ed09b423da1c3685bb858cfbf07e2ad6509f6e56fa71e6c22be3fa`
(2,959,065 bytes)**. Live tree untouched.

**Gates all passed:** `/dev/m1n1 -> ttyACM0` (Brett at proxy from
16:17); `/root/.ssh` restored again. Chainload first raw mode;
**base twice `0x1000560c000`**; top_of_kdata (chainloaded)
`0x10006088000`; live CTRR_D sysregs LWR `0x10005528000` / UPR
`0x1000560b000` → exactly `[base−0xE4000, base)`; CTRR_C sysregs
LWR `0x1000607c000` / UPR `0x10006087000` (recorded, not used).
Augmented DTB **`e4e90197…`** (35,390 bytes; exactly one line
`0x0000010005528000 / 0xE4000`; one dtc attempt failed first —
memreserve prepended BEFORE `/dts-v1/`; fixed by inserting AFTER
`/dts-v1/`; no gate skipped). Producer ARMED single attempt
(`C9_ADOPT_ARM` index 388, result 1, `a=0x474000, b=0,
c=0xde71ce55, d=0`, both read sets 5/5). Prepared-adopt.dtb
`a45a2635…` verified; linux.py read-back PASSED (`0ceb15c0…`).
Strict OFF.

**Egress incident (mid-run, recovered, no gate skipped):** direct
sunki-lan SSH failed persistently at linux.py launch (kex reset by
198.19.0.1:3128); first launch command never ran (no
linux-boot.log). Standing SOCKS workaround used for the rest of the
run; tunnel killed afterwards with safe ps/awk pattern; orphaned
linux.py ssh session terminated.

**linux.py started-guard PASSED:** started 16:45:09 under pty,
bootargs exactly as specified; webcam from 16:43.

**Logpages — Brett-photo-confirmed:** **1/4 CRC `FB1486BE`**
(SNAP `BOOT=DE71CE55 CSTS=00000000 SART=01FF CC=00474000`;
OFFERED DISABLED; MARK_RUNNING; ANSCHK RUN=1; ADOPT-PRE
`CSTS=00000000`; CSTS-WATCH ADOPT-PRE `CSTS=00000000`; RX-COUNT
ADOPT-PRE all zero `ALLOCFAIL=0`; ADOPT-OK `RET=0`; CSTS-WATCH
ADOPT-OK `CSTS=00000000`; RX-COUNT ADOPT-OK all zero; FIFO ADOPT-OK
`CTRL=00028801`). **2/4 CRC `4358AE32`** (CSTS-WATCH AFTER-DISABLE
/ AFTER-ADMINQ / AFTER-TCB all `CSTS=00000000 CC=00000000
BST=DE71CE55 CPU=00000010`; RX-COUNTs all zero; RB
`NUM_TCBS=0000003F ASQ_TCB=0x00000100038C0000
IOSQ_TCB=0x00000100038CC000 TCB_STAT=00000000
LIN_SQ_CTRL=00000001`; intended 63; `AQA=00010001
ASQ=0x00000100038C0000 ACQ=0x0000010003880000`). **3/4 CRC
`CD630CC6`** (TCB dumps all zero; SNAP-PREENABLE
`CAP=00000020F0010040 CAP_TO=240 CC=00000000 CSTS=00000000
BST=DE71CE55 SART=01FF IOQA1210=003F003F AQA=00010001
ASQ_TCB=0x00000100038C0000 IOQ_CQES1208=0x0000010008700000
IOQ_CMDS1200=0x00000100086FC000 IOQ_TCB=0x00000100038CC000
MAXDEPTH=64 NEEDS_IOQ=1`; CSTS-WATCH PREENABLE `CSTS=00000000`;
RX-COUNT PREENABLE all zero). **4/4 CRC `116E9732`** (FIFO
PREENABLE `CTRL=00028801 FULL=0 EMPTY=1`; repeated "RECEIVED SYSLOG
MESSAGE BUT NO SYSLOG_MSG_BUFFER" lines; **ADOPT-POST
`CPU=00000010 BST=DE71CE55 SART=01FF CC=00460001
CSTS=00000001`**). Webcam frame-240 = logpage 2/4 exactly;
frame-300 = logpage 4/4 exactly. EARLY-BUFFER absent (untested);
PRE-CFS-WARN correctly silent. Oops NONE.

**Panel: NOT OBSERVED (lost after initial load — Brett reported it
cannot be fetched; NOT a webcam sampling miss, NOT a FAIL). Panel
PASS NOT claimed.** Brett rebooted to proxy (16:48; `/dev/m1n1`
re-enumerated ttyACM1).

**Interpretation (within n=1):** CSTS `00000000` at EVERY pre-enable
snapshot (ADOPT-PRE, ADOPT-OK, AFTER-DISABLE, AFTER-ADMINQ,
AFTER-TCB, PREENABLE) with NO message sent — no spontaneous
pre-enable CFS. Candidate (e) **WEAKENED** (not refuted — n=1);
candidate (a) send-triggered **STRENGTHENED**. RX counters all
zero, ALLOCFAIL=0 baselines (b)/(c2) at zero; FIFO readbacks show
mailbox not stuck message-free. Tier A does NOT answer the late-ACK
question (no message → no ACK) — Tier B only.

**Scoring (decided explicitly, boot2 precedent applied):** the
clean tally counts enable outcomes (POST vs RESET -19); panel is a
separate read-verification record. **Tier A POST counts. Clean
tally now 5/17** (integrated tree alone 2/3: boot2 POST, repeat
RESET -19, Tier A POST). Panel PASS for Tier A remains OPEN. NOT a
bisect repeat-hold; credits no single piece. AP-ON tally REFUSED 1/1
stands; retry-diag tally POST 0/1, failed 1/1 stands. Memory updated
Oct 29.

## 16. Amendment A2 drafted, SIGNED, §6B appended

Draft (offline, completed 16:53):
`~/j604-boot/adoption-build/amendment-a2-draft-2026-10-29.md` (269
lines, 13,583 bytes, md5 `0e3879e5f28524ed30ea209aa5263e42`;
identical local copy `~/workspace/amendment-a2-draft-2026-10-29.md`).
Contract NOT edited during drafting (verified 0 mentions of A2).

**A2 substance (modelled on A1, but a NEW amendment — does NOT
revive lapsed A1):** ONE experiment, DISABLED mode only. Tier B
tree = integrated `ba3a0e71b` + Tier A prints + AP-ON block EXACTLY
as built for the AP-ON boot (re-applied from
`run-2026-10-29-apon/apon-branch.diff`, 221 lines, incl. read-only
`apple_rtkit_power_states()` accessor — the `donor-integration-apon`
branch no longer carries the block as a committed diff) + Tier B
prints P0–P6. Diff audit vs `ba3a0e71b` must show ONLY those three
components. ONLY message permitted: single Slot A `SET_AP_PWR_STATE`
ON, 1 s bound UNCHANGED, immediately after ADOPT-OK, before the
unconditional disable. **Prints (all dev_err):** P0
`ADOPT-MSG-WORD msg=%016llx ep=%u` (expected `(0xb << 52) |
0x20`); P1 `ADOPT-MSG-CSTS t=%ums csts=%08x cc=%08x` — CSTS before
FIFO write, after `management_send()` returns, then every 100 ms
through the 1 s wait (10 samples; a READ loop during an existing
wait, not a new delay), `send_ret`/`wait_ret` printed separately —
THE discriminator (CFS within ms of write = send-triggered;
near/after deadline = timeout/watchdog); P2 ACK handler log promoted
dev_dbg→dev_err, print-only — `ADOPT-ACK-RX msg=%016llx state=%u`;
P3 alloc-failure dev_err + counter; P4 per-endpoint RX counters +
workqueue depth at send and refusal; P5 A2I FIFO readback after send
returns; P6 post-refusal +0/+1/+5 s samples with ONE
`apple_mbox_poll()` drain before +5 s (RX-side only, sends
nothing) — `ADOPT-POST-REFUSAL t=+%us ap=%u done=%d csts=%08x
cc=%08x bst=%08x cpu=%08x crashed=%d`. Plus Tier A prints and
VERIFY only if gate passes. **Gate:** refuse-and-stop unchanged
(ret==0 AND ap_after==0x20 AND !crashed AND BST OK AND CPU RUN AND
!CFS, else REFUSED + `goto out`, never enable/re-send/fall
through); plus (g) reporting rule — ACK-received? and CFS-set? as
SEPARATE booleans, never a single reason string alone (AP-ON
priority order `cfs_after_message` retained, both booleans visible
alongside). **Remains forbidden:** INIT, HELLO, HELLO_REPLY, EPMAP
renegotiation, STARTEP, SET_IOP_PWR_STATE any form, any second
SET_AP_PWR_STATE, SLEEP, PMGR reset, SART/buffer reallocation,
queue reuse, IOQA write reordering, enabled mode, any producer-side
power message, any wait-bound change, any retry/disable/enable after
a refusal. Producer `2bf344d6…`, initramfs `1057580b…`, strict OFF.
**Expiry:** gate passes + POST → in force ONLY for the ONE
unchanged Tier B repeat (repeat POSTs 2/2 → AP-ON leading →
ATTRIBUTION design, not clean-tally entry; repeat fails → A2 flaky
1/2, do NOT combine with queue reuse by default). Gate passes +
identical enable failure → lapses; AP-ON retired; next Rank 3 queue
reuse on INTEGRATED tree; do NOT repeat Tier B. Gate REFUSED →
lapses for enable purposes; next step determined by WHICH print
discriminates (P1 send-triggered + P6 empty + P0 correct + P3/P4
clean → message line CLOSED, queue reuse or non-RTKit CFS
investigation; P1 at/after deadline + P6 empty + no Linux defect →
transition-fault by elimination, same consequence; P3 fires or P4
mis-route/dispatch loss → fix defect, then single-message retest
under a NEW amendment; P0 differs → corrected encoding under NEW
amendment; P6 post-deadline ACK + CFS NOT send-triggered → late ACK
proven, CFS half unexplained). Late ACK without send-triggered CFS
→ wait-variant needs its OWN new amendment (Aurora caveat: polling
rescues queued messages only; extended window is a separate
behaviour change); a late ACK alone NEVER reopens AP-ON until the
CFS half is resolved. **Scoring:** SEPARATE A2 tally (A2-REFUSED /
A2-POST / A2-identical-failure; panel PASS vs POST-only separate);
clean tally stays **5/17** regardless of Tier B outcome, even POST
+ panel PASS; AP-ON REFUSED 1/1 stands; Tier B POST is NOT a bisect
repeat-hold and does NOT reopen AP-ON generally without an
attribution design; EARLY-BUFFER/PRE-CFS-WARN first firing gets its
OWN follow-up design. **Run header:** "contract 2026-10-28 +
Amendment A2 (Tier B, Slot A, one instrumented message)" +
mode/producer/kernel/DTB hashes.

**Signature (Brett, options widget, Oct 29 16:53): "Approve A2 and
build/boot Tier B once"** (option (a) — the only option that
dispatches Tier B). Muse then, in the same turn: appended the draft
verbatim as **§6B** of the contract with approval record "Approved
by Brett Oct 29, 2026 (option (a): approve the A2 text AND build/
boot Tier B once)" and §6B header sanity-checked (section at line
179; contract 28,300 bytes after append); updated §6 C1 (line 101)
— exception is now the single Tier B message permitted by §6B, §6A/
A1 noted as lapsed for enable purposes; added the two §7 Tier B
checklist items. No other contract section changed; §3 H7 untouched.

## 17. Tier B boot: A2-REFUSED, send-triggered — message line CLOSED

Dispatched 16:54, ONE boot, run dir
`~/j604-boot/adoption-build/run-2026-10-29-tier-b/`. Brett
photographed the boot live (console photo 17:07 — small print
blurred, NOT transcribed by Muse; panel WAIT photo 17:07; then full
logpages 1/4–4/4 + final FAIL panel 17:08, and asked "Am I good to
reboot? Need to leave my desk" — Muse answered yes, evidence
complete; Brett confirmed "Done" 17:09, Mac back at proxy).

**Build — passed, diff audit passed (with two documented
corrections):** branch `donor-integration-tier-b` off clean
integration HEAD `ba3a0e71b`. (The tier-a branch checkout carried
an uncommitted Tier A diff; it was preserved to
`tier-a-working.diff` in this run dir BEFORE switching, then the
tree was reset clean and the Tier A diff re-applied exactly once.)
Components, in order: (ii) Tier A prints (saved diff, 6 files, 159
insertions), (i) AP-ON block exactly as built for the AP-ON boot —
re-applied from `run-2026-10-29-apon/apon-branch.diff` (221 lines;
`git apply --include` for core.c, hand-merge for apple.c/rtkit.c/
rtkit.h where Tier A touched the same regions — same code,
relocated past Tier A call sites), (iii) Tier B prints P0–P6.
Final diff vs `ba3a0e71b`: 7 files, 477 insertions, 5 deletions —
ONLY the three components. Forbidden-string scan on added lines
clean: no SET_IOP, no ADOPT-RETRY, no SNAP3, no POST-RETRY, no
settle delay; msleep appears ONLY in the P6 post-refusal window
(permitted: after the boot is already over). Strict mode OFF
(parameter present in baseline, default off, unused).
Documented deviation (one, disclosed, not hidden): the Slot A block
calls `apple_rtkit_set_ap_power_on_tier_b()` instead of the exported
`apple_rtkit_set_ap_power_on()` wrapper. Reason: the wrapper
collapses send_ret/wait_ret into one return and offers no sampling
hook, so P1's separated rets and 100 ms CSTS samples cannot be
implemented through it. The variant is line-for-line the same send
+ wait (same word, same endpoint, same 1 s bound sliced into 100 ms
waits, same state check), used ONLY by the Slot A block. The message
itself is identical; see P0 confirmation below. Two build
corrections, both recorded (neither skipped a gate): (1) First
detached build failed fast on a duplicated
`apple_rtkit_is_crashed` definition (insert repeated the anchor)
and a duplicated `set_ap_power_on` declaration in rtkit.h; both
deduped, then rebuilt. The failed build's stale Image.gz (Tier A
hash) was NEVER booted. (2) First SNAP2-FAIL/VERIFY placement was
wrong (insert appended AFTER the anchor: SNAP2-FAIL landed after
`goto out` as dead code — caught by the vmlinux string check, which
showed NVME-SNAP2-FAIL missing — and VERIFY landed after the enable
call). Both blocks were moved to their correct positions (VERIFY
before `nvme_enable_ctrl()`, SNAP2-FAIL before `goto out` in the
failure branch) and the build was redone; final string check passes
for ALL prints. Detached build EXIT=0 (`make olddefconfig` first,
ARCH=arm64). **Image.gz SHA-256
`e782d36e4d85b14c15d467d3ac49fa677672d304ba621ca38eca87e2db78a908`
(2,961,634 bytes)**, CONFIG_ARM64=y, objects (apple.o, rtkit.o)
newer than source edits, vmlinux strings verified: ADOPT-MSG-WORD,
ADOPT-MSG-CSTS, ADOPT-MSG-RET, ADOPT-ACK-RX, ADOPT-POST-REFUSAL,
ADOPT-AP-ON-BEFORE, ADOPT-AP-ON-REFUSED, ADOPT-AP-ON-VERIFY,
ADOPT-AP-ON-GATE, ADOPT-CSTS-WATCH, NVME-SNAP-PREENABLE,
ADOPT-EARLY-BUFFER, ADOPT-PRE-CFS-WARN, NVME-WAIT-READY,
NVME-SNAP2-FAIL. Live tree `~/linux-asahi` untouched (HEAD
77cb8f24c, same 16 pre-existing modified/untracked entries,
nothing pushed).

**Pre-boot gates — all passed:** `/dev/m1n1 -> ttyACM1` present
(Mac at proxy after Tier A; re-enumerated ttyACM1 at 17:09 after
this run's reboot). Chainload FIRST, raw mode, exit 0, "Proxy is
alive again". m1n1 base read twice after chainload, agreement:
**`0x10004c58000`** (new base, no reuse). Top_of_kdata
(chainloaded) `0x1000573c000`. Live CTRR_D sysregs LWR
`0x10004b74000` / UPR `0x10004c57000` → `[0x10004b74000,
0x10004c58000)`, size `0xE4000`, exactly `[base−0xE4000, base)`.
Formula confirmed again, inversion excluded. CTRR_C sysregs
recorded, not used: LWR `0x100056c8000` / UPR `0x100056d3000`
(stock kboot reserve `0x100056c8000 / 0xb000`). Augmented DTB
**`a9cb079ede4ce4f4d35bbd927e5fae991aa1bf11ac5465b1aef70291346f3ed8`**
(35,390 bytes): exactly ONE memreserve line `0x0000010004b74000 /
0xE4000` (inserted AFTER `/dts-v1/`, as in Tier A), dtc round-trip
diff vs original shows only that line, orig DTB `d7091e74…`
unchanged. Used for BOTH producer and linux.py inputs. Producer,
single effective attempt, exit 0, PRODUCER_ARMED: `C9_ADOPT_ARM`
index 418, result 1, `a=0x474000, b=0, c=0xde71ce55, d=0`, both read
sets 5/5 probe hashes, `/chosen` disabled / `0xde71ce55` / `0x5f`.
(A first producer invocation failed at startup on a missing
`t8132-j604-ramoops-ctrr.dtb` — the augmented DTB under the
filename the script expects — BEFORE any proxy interaction: no
NVMe touched, no arm. The file was supplied (copy of this run's
augmented DTB) and the script rerun as the clean first attempt;
this is NOT a retry on contaminated producer state. No nvme_init
UartTimeout recurrence.) Prepared-adopt.dtb verified (dtc +
reservation parse), SHA
`02a469419d171155fdc19a50b34891641833b3186eede7a9e0dcb337c88390b4`:
first reservation CTRR_D `0x10004b74000 / 0xE4000`, then prepared
FDT `0x10007d74000 / 0x20a3e`, m1n1 image `0x10004c58000 /
0x3c0000`, CTRR_C `0x100056c8000 / 0xb000`. linux.py
prepared-DTB read-back PASSED, SHA
`f00499361197723ed0b0d63653576aed7de84359d5ecbb8bf979cf7f31af989e`:
first reservation CTRR_D `0x10004b74000 / 933888`, 5th reservation
is the initrd (1,030,603 bytes) as expected. (A first read-back
invocation used the WRONG input file — the readback script still
carried the Tier A run path, so it prepared Tier A's DTB (first
reservation `0x10005528000`) and its result was DISCARDED as
invalid. It touched only DTB-preparation scratch, not NVMe or the
producer arm, and linux.py re-prepares its own DTB anyway; the
script path was fixed and the read-back redone correctly with this
run's DTB. The discarded wrong-input result is NOT used anywhere in
this note.) Payloads re-verified: producer `2bf344d6…`, initramfs
`1057580b…`, Tier B kernel `e782d36e…`. Strict OFF.

**linux.py — started guard PASSED:** started 17:06:53 under pty,
process alive (PID 140658) + linux-launch.log created showing
kernel loading (2,961,634 bytes), DTB/initramfs loads, and bootargs
exactly as baseline. No serial console, no memblock=debug, no strict
parameter. Webcam started before linux.py (ffmpeg PID 140543,
finalized cleanly after the run: cam-boot.mkv 21,500,407 bytes,
186.1 s). Host-side note (standing pattern, not a failure): after
the kernel takeover ("Preparing to boot kernel at 0x10010200000
with fdt at 0x10007d74000"), the host miniterm thread raised a
serial-disconnect exception. Host log contains no kernel console
lines (console is framebuffer-only after kboot_boot). Orphaned
linux.py host processes were terminated after Brett's reboot (as in
Tier A).

**Logpages — Brett-photo-confirmed (his photos supersede webcam):**
- **LOGPAGE 1/4 CRC `B1820E6D`** (webcam frame-150 confirms this
  CRC, which was partially cut in the forwarded frame): SNAP
  `BOOT=DE71CE55 CSTS=00000000 SART=01FF CC=00474000`; OFFERED
  DISABLED; MARK_RUNNING BEFORE MBOX_START (inherited session, no
  INIT/HELLO/EPMAP); ANSCHK `CPU=00000010 BST=DE71CE55 RUN=1`;
  ADOPT-PRE `CPU=00000010 BST=DE71CE55 SART=01FF CC=00474000
  CSTS=00000000`; ADOPT-CSTS-WATCH ADOPT-PRE `CSTS=00000000
  CC=00474000 BST=DE71CE55 CPU=00000010`; ADOPT-RX-COUNT ADOPT-PRE
  all zero, `ALLOCFAIL=0`; MARK_RUNNING again; inherited endpoints
  0x01/0x02 marked discovered (no STARTEP); adopting already-
  running session (no INIT/HELLO/EPMAP sent); ADOPT-OK `RET=0
  ADOPTED=1`; ADOPT-CSTS-WATCH ADOPT-OK `CSTS=00000000 CC=00474000
  BST=DE71CE55 CPU=00000010`; ADOPT-RX-COUNT ADOPT-OK all zero,
  `ALLOCFAIL=0`; ADOPT-FIFO ADOPT-OK `CTRL=00026601
  FULL_BIT=00010000 EMPTY_BIT=00020000`.
- **LOGPAGE 2/4 CRC `62EAF648`** (webcam frame-130 confirms CRC and
  every value below): ADOPT-AP-ON-BEFORE `IOP=32 AP=32 BST=DE71CE55
  CPU=00000010 CC=00474000 CSTS=00000000 SART=01FF`; ADOPT-CSTS-
  WATCH MSG-SEND `CSTS=00000000 CC=00474000 BST=DE71CE55
  CPU=00000010`; ADOPT-RX-COUNT MSG-SEND all zero, `ALLOCFAIL=0`;
  ADOPT-FIFO MSG-SEND `CTRL=00026601 FULL_BIT=00010000
  EMPTY_BIT=00020000 FULL=0 EMPTY=1`; **P0: ADOPT-MSG-WORD
  `MSG=00B0000000000020 EP=0`**; **P1: ADOPT-MSG-CSTS `T=0MS
  CSTS=00000000 CC=00474000` (twice, both 0 — first BEFORE the FIFO
  write, second AFTER management_send() returns, in log order);
  `T=100MS CSTS=00000002 CC=00474000`; `T=200MS CSTS=00000002`;
  `T=300MS CSTS=00000002`; `T=400MS CSTS=00000002`; `T=500MS
  CSTS=00000002`; `T=600MS CSTS=00000002`; `T=700MS
  CSTS=00000002`** (continuing on page 3).
- **LOGPAGE 3/4 CRC `5BA8C545`** (webcam frames 90/110 confirm CRC
  and every value below): ADOPT-MSG-CSTS `T=800MS CSTS=00000002`;
  `T=900MS CSTS=00000002`; `T=1000MS CSTS=00000002 CC=00474000`;
  **ADOPT-MSG-RET `SEND_RET=0 WAIT_RET=-62`**; **P5: ADOPT-FIFO
  MSG-SENT `CTRL=00107801 FULL_BIT=00010000 EMPTY_BIT=00020000
  FULL=0 EMPTY=0`**; ADOPT-CSTS-WATCH MSG-SENT `CSTS=00000002
  CC=00474000 BST=DE71CE55 CPU=00000010`; **P4: ADOPT-RX-COUNT
  MSG-SENT `MGMT=0 CRASHLOG=1 SYSLOG=0 DEBUG=0 IOREPORT=0
  UNKNOWN7=0 OSLOG=0 TRACEKIT=0 APP=0 OTHER=0 QUEUED=0
  ALLOCFAIL=0`**; ADOPT-AP-ON `RET=-62 AP_AFTER=32 IOP=32
  BST=DE71CE55 CPU=00000010 CC=00474000 CSTS=00000002 SART=01FF`;
  **(g) ADOPT-AP-ON-GATE `ACK_RECV=0 CFS_SET=1`**;
  **ADOPT-AP-ON-REFUSED `REASON=CFS_AFTER_MESSAGE RET=-62
  AP_AFTER=32 BST=DE71CE55 CPU=00000010 CC=00474000
  CSTS=00000002 RTK_CRASHED=0 ACK_RECV=0 CFS_SET=1`**;
  ADOPT-CSTS-WATCH MSG-REFUSED `CSTS=00000002 CC=00474000
  BST=DE71CE55 CPU=00000010`; ADOPT-RX-COUNT MSG-REFUSED
  `MGMT=0 CRASHLOG=1 SYSLOG=0 DEBUG=0 IOREPORT=0 UNKNOWN7=0
  OSLOG=0 TRACEKIT=0 APP=0 OTHER=0 QUEUED=0 ALLOCFAIL=0` (tail
  confirmed in webcam frames 90/110); **P6: ADOPT-POST-REFUSAL
  `T=+0S AP=32 DONE=0 CSTS=00000002 CC=00474000 BST=DE71CE55`**
  (+0S CPU/CRASHED fields are Brett-photo-only; they are not
  visible in the webcam frames and are not needed for the verdict
  — the +1S/+5S lines below carry the full field set).
- **LOGPAGE 4/4 CRC `945B3259`** (webcam frame-120 confirms CRC
  and every value below): **P6: ADOPT-POST-REFUSAL `T=+1S AP=32
  DONE=0 CSTS=00000002 CC=00474000 BST=DE71CE55 CPU=00000010
  CRASHED=0`**; **ADOPT-POST-REFUSAL `T=+5S AP=32 DONE=0
  CSTS=00000002 CC=00474000 BST=DE71CE55 CPU=00000010
  CRASHED=0`**; `RESET FAILURE STATUS: -19`.
- **P2: ADOPT-ACK-RX never appears** in any photographed logpage
  (all four pages, Brett + webcam) — no ACK arrived at any time in
  the boot.
- ADOPT-EARLY-BUFFER does NOT appear (early-buffer theory remains
  untested, not refuted). ADOPT-PRE-CFS-WARN does NOT appear,
  correctly silent (CFS was 0 at every PRE). Oops: NONE observed.
- **Absent — and therefore nonexistent for this boot:** no
  SNAP-PREENABLE, no ADOPT-AP-ON-VERIFY, no WAIT series, no DEVICE
  NOT READY, no SNAP2, no SNAP2-FAIL, no ADOPT-POST, no RB/TCB
  dumps, no disable values. No VERIFY or SNAP2-FAIL value may be
  claimed. The gate refused before disable, so VERIFY was never
  printed (by design: printed only if the gate passes).

**Panel — Brett-photo-confirmed, webcam-corroborated, OUT-PATH
panel:** Brett (intermediate WAIT): ADOPT / WAIT / DIRECT MATCH 0
OF 5 / NAMESPACE NO / ANS BR NA / ANS CRASH NO / RESET -19 /
**BOOT `D5AD99F8`** / PHASE WAIT NAMESPACE / ERROR NONE. Webcam
frame-50 confirms this WAIT panel exactly, same BOOT id. Brett
(final FAIL, same BOOT `D5AD99F8`): ADOPT / FAIL / DIRECT MATCH 0
OF 5 / NAMESPACE NO / ANS BR NA / ANS CRASH NO / RESET -19 /
**BOOT `D5AD99F8`** / PHASE NO NAMESPACE / ERROR NO NVME. Webcam
frame-70 confirms this FAIL panel exactly, same BOOT id.
Distinction, stated explicitly: this panel follows the refused
gate's `out` path (RESET -19 is reset_work's failure status,
namespaces dead because the driver released). It must NOT be
misread as enable-failure evidence — no enable was attempted.

**Interpretation — §6B A2-REFUSED, send-triggered (the
discriminating result):**
- **Outcome: A2-REFUSED.** Gate REFUSED `CFS_AFTER_MESSAGE`,
  booleans `ACK_RECV=0 CFS_SET=1` (separate, per the (g) reporting
  rule). No enable attempted, no wait series, no SNAP2, no POST.
  This boot is NOT scored as an enable failure.
- **P0 (encoding): CORRECT.** Word `00B0000000000020` = `(0xb <<
  52) | 0x20`, the producer's own boot-time ON.
  Encoding-malformed is closed for good.
- **P1 (timing): SEND-TRIGGERED.** CSTS 0 at BOTH T=0MS samples
  (before the FIFO write and after `management_send()` returns),
  then 2 ALREADY at T=100MS, frozen at 2 through T=1000MS. CFS set
  WITHIN 100 ms of the FIFO write — not near/after the deadline,
  not a timeout/watchdog shape. CC stayed `00474000` (the
  producer's SHN state) throughout.
- **Send vs wait, separated:** `SEND_RET=0` (FIFO write succeeded)
  with `WAIT_RET=-62` (no ACK within 1 s). The failure is in the
  wait/ACK half only because the controller faulted first; the
  write itself succeeded.
- **P2 (ACK): NEVER ARRIVED.** No ADOPT-ACK-RX line anywhere,
  `ACK_RECV=0`, completion DONE=0 throughout P6. There is no ACK to
  be late.
- **P6 (late/queued ACK): REFUTED for this boot's conditions.**
  Window empty at +0/+1/+5 s (DONE=0, CSTS still 2, AP still 32
  bookkeeping, CRASHED=0), including after the RX-side
  `apple_mbox_poll()` drain before +5 s. A late or queued ACK
  would have appeared here; none did.
- **P3 (alloc-failure): CLEAN.** `ALLOCFAIL=0` at every snapshot.
- **P4 (counters): CLEAN for the message question.** `MGMT=0` at
  send, sent, and refused points — no management ACK arrived. The
  single `CRASHLOG=1` count is a crashlog-endpoint message, NOT an
  AP ACK (MGMT is the AP-ACK endpoint count); do not conflate it.
  `QUEUED=0` throughout — no workqueue backlog.
- **P5 (FIFO): CONSUMED, not stuck.** MSG-SEND `FULL=0 EMPTY=1`
  (empty before the write); MSG-SENT `FULL=0 EMPTY=0` (FIFO state
  changed after the write — the word left the host FIFO; "written
  but stuck" is not the shape). Combined with P1, the fault
  follows the write, not a stuck FIFO.
- **(e) incipient/coincidental, further weakened:** Tier A showed
  no spontaneous pre-enable CFS in a message-free boot; Tier B
  shows CFS within 100 ms of the one message, in a boot whose
  pre-message CSTS samples were all 0. A coincidental fault
  expiring exactly in the first 100 ms after the write, in the one
  boot with a message, is the remaining (e) residue — possible in
  principle, n=1, but no longer the leading reading.
- **Per §6B's REFUSED branch with P1 send-triggered + P6 empty +
  P0 correct + P3/P4 clean: the message line is CLOSED.** Next is
  queue reuse on the integrated tree or a non-RTKit CFS mechanism
  investigation — NOT another power message, NOT a Tier B repeat,
  NOT a wait-variant under this amendment (a late ACK alone was
  refuted, and a wait change would not address a send-triggered
  fault). **Amendment A2 lapses for enable purposes on this refused
  boot** (§6B expiry); any further power-messaging experiment
  needs a new amendment, and none is recommended on this evidence.

**Tallies — fixed in advance, applied exactly:**
- **A2 tally: A2-REFUSED 1/1** (not scored as an enable failure; no
  enable attempted). A2-POST 0/0, A2-identical-failure 0/0; panel
  PASS vs POST-only not applicable (no POST).
- **Clean tally: unchanged at 5/17** (Tier B outcomes never enter
  it, even a POST + panel PASS would not have). Integrated tree
  alone still 2/3.
- **AP-ON tally: REFUSED 1/1 stands**, untouched by Tier B.
- Retry-diag tally POST 0/1, failed 1/1 stands.

**Close:** Mac rebooted to proxy by Brett himself (he needed to
leave his desk; the NEEDS-BRETT reboot step was already handled by
him — do not ask him to stay or to re-photograph). Webcam
frame-170 shows the post-reboot proxy screen (m1n1 logo, "Running
proxy..."); `/dev/m1n1 -> ttyACM1`. No further boot is dispatched
on this result. The next step is a Rank 3 queue-reuse design on the
INTEGRATED tree (or a non-RTKit CFS mechanism investigation), not
another message experiment.

## 18. Standing state at end of Oct 29

- Clean tally **5/17** (POSTs: Oct 28 run 6, adopt+reserve #1, IOQA
  snapshot, integrated boot2, Tier A; failures as tallied in §§6,
  8, 11). Integrated tree alone 2/3. Panel PASSes confirmed by
  Brett photo: sustained (§2) only — reserve-repro, boot2, and
  Tier A panel PASSes all remain UNCONFIRMED (see §§1, 8, 15).
- Message line CLOSED (§17). Amendments A1 and A2 both LAPSED for
  enable purposes. Contract §6 C1 reverts to full prohibition of
  AP/IOP power renegotiation before first I/O; any further
  power-messaging experiment needs a NEW amendment, and none is
  recommended on current evidence.
- Transient branch CLOSED (§11). Disable timing alone NOT a sole
  cause (§3). IOQA pre-enable write NOT the missing step (§4).
  Reserve formula CONFIRMED by live sysregs (§6); memblock
  membership of the reserve still unobserved.
- Next candidates, Brett's choice, design first, no build/boot
  without approval: **Rank 3 queue reuse on the INTEGRATED tree**
  (producer + contract change, highest cost) OR a **non-RTKit CFS
  mechanism investigation**. NOT another power message, NOT a Tier
  B repeat, NOT a wait-variant, NOT a retry-diag repeat, NOT a
  second enabled boot, NOT a P1/P2/P4 bisect (repeat-hold
  precondition unmet).

## 19. Open items (unchanged from Oct 28 unless noted)

- What the Go init does after READS MATCH in ADOPT mode
  (interactive shell/disk-write path is a separate step, blocked on
  reliable enable).
- Making the CTRR_D reserve durable (per-boot DTB route works and
  is reversible; CTRR-patched m1n1 as enrolled proxy is a separate
  later decision — NOT approved).
- Prep (b) automated CTRR reservations and prep (c) ramoops
  verification (both designed Oct 29, neither built as standalone
  artifacts; the self-verifying reserve procedure — chainload-first,
  base twice, live sysreg readback, DTB assertions, prepared-DTB
  read-back — was implemented procedurally in the reserve-verify
  and all later runs).
- Simplified producer host sequence (preload → one init/read →
  prompt handoff) — designed, NOT implemented.
- C10 chainload overlap (options: `--no-sepfw` retry — needs
  Brett's approval; diff Oct 12 chainload.py vs current).
- Adopted shutdown path.
- Reserve-repro panel PASS confirmation (needs Brett's word that he
  saw PASS, or a future settling boot; do not close it on the
  sustained PASS alone). Integrated boot2 panel PASS also remains
  unconfirmed (POST Brett-photo-confirmed, no panel photo) — do not
  upgrade it. Tier A panel PASS likewise remains open (panel lost
  after initial load).
- Repo notes still owed after this commit: none for Oct 29 runs.
  The X1 note correction and RTKit correction in this commit close
  the two outstanding Oct 12 / Oct 28 corrections.
- This commit is LOCAL ONLY on adoption-ram (not pushed by Muse —
  sunki's key is passphrase-protected, no agent in Muse's session).
  Brett pushes from his own terminal; push command is in the commit
  message body. Branch adoption-ram; main untouched at 1cefd1b.
- Mac state at commit time: back at proxy (Brett rebooted Oct 29
  17:09, "Done"); no boot in progress.
