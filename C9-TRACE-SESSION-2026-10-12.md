# RTKit receive-ring diagnostic over the IOP SLEEP wait — Oct 12, 2026

This run executes the next diagnostic specified at the end of the
[teardown ordering session](C9-ORDER-SESSION-2026-10-12.md). It changes no
power-management request, timeout or ordering relative to the ORDER kernel.
The only kernel changes (exact delta in
[`diagnostics/kernel-c9/order-to-trace.patch`](diagnostics/kernel-c9/order-to-trace.patch)):

1. The RTKit diagnostic ring capacity rises from 1024 to 8192 records.
2. The `nvme-ready` trace dump is removed, so the ring stays open past
   NVMe ready instead of freezing at boot.
3. A filtered dump, `apple_rtkit_diag_trace_dump_mgmt()`, freezes the ring
   and prints only endpoint-0/1 receives, endpoint-0 sends and reinit
   markers. The remove path calls it immediately after the IOP SLEEP wait
   returns and CPU_CONTROL has been stopped and read back, so the window
   covers every mailbox receive from boot through the sleep timeout,
   recorded in the mailbox RX path before workqueue dispatch.

The verifier init gains matching panel fields (`TRACE TOT/DROP`,
`RX>SLEEP`, `RING ACK` plus the first post-sleep crashlog-endpoint receive
delta), parsed from the RTKTRACE lines; a Go unit test covers the window
logic, including that a pre-sleep ACK does not count. Records are
allocation-free in the receive path and nothing prints there; the summary
is emitted after the wait, as specified.

## Procedure note (first attempt failed before any payload)

The first launch of this cell failed at host preparation
(`trace-pointer`: proxy request `0xf04` answered `Bad Command`). The
runner requires the C9-diagnostic m1n1 to already be the running proxy;
a freshly rebooted Mac provides only the stock proxy. The diagnostic
image (hash-verified against the manifest) was chainloaded with
`tools/chainload.py -n -r` from the bootloader proxyclient, after which
the cell ran normally. The failed attempt loaded no payload, issued no
disk commands and is preserved as `RUN-1` in the run directory.

## Result

One run, Oct 12 14:37 MDT handoff from the chainloaded diagnostic proxy;
`kboot` return 0. Linux booted warm (ANS branch 3), matched all five
direct reads, and completed one unbind. The fixed panel reports:

| Field | Observed |
|---|---|
| Before reads | MATCH 5 OF 5 |
| AP SLEEP ACK | YES |
| IOP SLEEP TX / ACK (parsed) | 0 / NO |
| Shutdown prepare | `-62` |
| CPU_CONTROL / BOOT_STATUS | 0 / 0 |
| RTKit reinit | not called (prepare failed) |
| Trace ring | total 105, dropped 0 |
| Receives after the IOP SLEEP send | exactly one: endpoint 1 (crashlog) |
| IOP SLEEP ACK in the raw ring | NO |
| Crashlog-endpoint receive delta | +0 ms (sub-millisecond after the send record) |
| ANS crash | YES |
| Log capture | 0 gaps, 0 drops, no reader error |
| Bind | not attempted (crash gate) |

Primary frame: `TRACE-RUN/frames/f070.jpg` in the run directory,
SHA-256 `fe72e0bce8217030be89817ca217c51be61186d0702530b2490ab4587a3a75fb`.

## Interpretation

The pre-registered discriminator was: an IOP SLEEP ACK present in the
raw receive ring without a parsed ACK would point at Linux receive,
workqueue or completion handling; no ACK in the ring points at the
firmware/state side. The ring is recorded where the mailbox FIFO is
read, before any workqueue dispatch, and this run captured the complete
session (105 records, none dropped).

**The IOP SLEEP ACK never reached the mailbox FIFO.** Linux receive
handling is therefore not where the ACK is lost. The only receive after
the sleep send was a single crashlog-endpoint message within the same
millisecond as the send record, consistent with the firmware entering
its crash path on receipt of the sleep request rather than after a
delay. (The panel does not carry that message's payload word; telling a
crashlog buffer request from a crash notification needs the raw kmsg,
which this reporting path does not export.)

This does not prove why the firmware refuses Linux's request while
answering m1n1's identical type-6/state-1 exchange. The request bytes,
the AP QUIESCED step and the SART state have each been checked; what
still differs between the two drivers is everything the session
established before the request — boot-time endpoint and buffer setup,
queue creation and use, and the AP power state Linux leaves the
coprocessor in. The next discriminator belongs on that side of the
exchange (for example, comparing the firmware-visible session state
after a Linux boot against the state after an m1n1 session, or testing
whether a sleep request sent before any queue creation behaves
differently), not in further receive-path instrumentation.

Artifacts and hashes are recorded in
[`C9-TRACE-RESULTS-2026-10-12.json`](C9-TRACE-RESULTS-2026-10-12.json).
Run directory:
`/home/btega/j604-boot/ans-review-n6miVhGq/C9-TRACE-20261012/`.
This remains a diagnostic result, not a fix.
