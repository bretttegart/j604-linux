# Session-state comparison design — Oct 12, 2026

Question left by the [receive-ring diagnostic](C9-TRACE-SESSION-2026-10-12.md):
the IOP SLEEP ACK never reaches the mailbox when Linux asks, and the
firmware enters its crash path on receipt of the request, while m1n1's
identical exchange completes. The request, the quiesce step and the
receive path are each eliminated. What remains is the state of the
session the request is made in. This note records which session
dimensions have been compared desk-side, which are proven identical,
and the experiment queue for the rest.

## Dimensions proven identical (desk, with evidence)

| Dimension | m1n1 (working) | Linux (failing) | Evidence |
|---|---|---|---|
| IOP SLEEP request word | `0060000000000001` | `0060000000000001` | L1 trace idx 210; Linux word is deterministic from `apple_rtkit_set_iop_power_state` + `APPLE_RTKIT_MGMT_PWR_STATE` (type 6, state 1) in the ORDER tree |
| AP QUIESCED word / ACK | `00b0000000000010`, ACK received | same word, ACK received | L1 trace idx 207–209; ORDER/TRACE panels `AP SLEEP ACK YES` |
| HELLO negotiation | firmware offers min=max=12; reply `00200000000c000c` | want = min(12, fw max) = 12; reply built identically | L1 init trace idx 12–13; `apple_rtkit_management_rx_hello` in the ORDER tree |
| Endpoints started | {1, 2, 3, 4, 8} (STARTEP, flag 0x2) | {1, 2, 3, 4, 8} (EPMAP handler starts SYSLOG/CRASHLOG/DEBUG/IOREPORT/OSLOG; client registers none) | L1 init trace STARTEP records; `apple_rtkit_management_rx_epmap` in the ORDER tree. C8's extra ep7 start was a local addition, removed in parity and falsified by the ORDER runs |
| Controller state at sleep | queues deleted, controller shutdown, controller disabled, in that order, before the power requests | IO queues removed, `nvme_disable_ctrl(shutdown)` then disable, all inside `apple_nvme_disable(anv, true)`, which the remove path calls before the RTKit prepare block | L1 trace idx 197–206 (DELETE_SQ, DELETE_CQ, CTRL_SHUT, CTRL_DISABLE); `apple_nvme_remove` / `apple_nvme_disable` in the ORDER tree |
| Buffer/SART posture at sleep | 3 mappings held at sleep, released after CPU stop | RTKit buffers and queue mappings held at sleep (release would be in reinit/teardown, after prepare) | L1 trace: MAP ×3 before, UNMAP ×3 at idx 219–221, after SLEEP_SWITCH and CPU_STOP; L1 SART snapshots identical across sleep/reset |
| Pre-sleep power biography | IOP INIT `0x220` → IOP ACK (state `0x20`) → AP ON `0x20` | wake sends IOP INIT (`0x220`), boot waits the IOP ACK, then AP ON (`0x20`) — same constants | L1 trace idx 10, 141–149; `apple_rtkit_wake` / `apple_rtkit_boot` in the ORDER tree. Source-matched; the Linux wake ACK's `new_state` value has not been capture-verified (see E1) |

## Dimensions that still differ or are unverified

1. **Session activity before the request.** m1n1's sleep follows a
   minimal session (init, five reads, shutdown). Linux's follows a full
   OS probe plus reads. Queue *creation* happens in both; queue *use*
   (real read commands, completions) also happens in both, but the
   volume and the surrounding endpoint traffic differ (m1n1 session:
   ep2 16 TX/17 RX, ep4 37/37; Linux serves I/O over MMIO queues and
   its service endpoints see only their buffer handshakes).
2. **Linux wake IOP ACK state (capture gap, item 7 above).**
3. **Crashlog buffer registration details** (sizes/addresses differ;
   no evidence tying them to the sleep path; listed for completeness).

## Experiment queue

### E1 — sleep before any reads (warm, one run) — NEXT
Runtime variant of the TRACE cell: after the namespace appears, unbind
immediately, skipping the five direct reads entirely. Same kernel
power behavior as ORDER/TRACE. The init also records the boot-time
IOP PWR ACK `new_state` on the panel (capture item 2 above).

- If the IOP SLEEP ACK arrives (prepare returns 0, reinit runs, bind
  proceeds): session *activity* (queue use after probe) is implicated;
  bisect reads vs elapsed time next.
- If it fails identically (no ACK in the ring, crash flag, `-62`):
  the poison is established by probe itself; go to E3.
- Ambiguity: probe still creates queues and the init still waits for
  the namespace, so E1 cannot separate queue creation from boot state;
  that is E3's job. A pass must also be read against the warm-control
  gate (branch 3, no crash before unbind) as usual.

### E3 — sleep at probe, before queue creation (warm, one run; only if E1 fails)
Diagnostic kernel: in `apple_nvme_probe`, immediately after RTKit
boot and AP ON complete, run the same prepare sequence
(AP QUIESCED → IOP SLEEP) and print the outcome, before any queue
creation. No unbind, no reads.

- ACK arrives: queue creation (or a later probe step) establishes the
  failing state; bisect probe steps.
- No ACK: the failing state is established by the wake/boot handshake
  itself despite the byte-identical messages above; the comparison
  then moves to register-level session state (ASC/mailbox registers,
  SART contents as Linux leaves them vs as m1n1 leaves them), captured
  from both sides at the same session point.

### E5 — cold-direction transfer (later; only on an E1/E3 localization)
Repeat the winning minimal-session configuration in an L1-style cell
(m1n1 init/read/shutdown, then Linux) to test whether the same state
explains the cold-boot IOP ACK timeout, whose crash notification
precedes the ACK wait in the boot path.

## Non-goals

No further receive-path instrumentation (the ring result closed that
side). No delay sweeps, IOP OFF requests, or firmware changes. Each
cell keeps the established controls: fresh diagnostic proxy per run,
hash-verified payloads, warm-control gate before any unbind, crash
gate before any bind, no SSD writes.
