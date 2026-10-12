# Linux ANS teardown ordering experiment — Oct 12, 2026

The next temporary Linux image tests one source-derived ordering difference
from the successful measured m1n1 shutdown. It keeps the grouped parity
kernel behavior and warm direct-read gate, then changes only the `nvme-apple`
platform remove path:

1. Request AP QUIESCED and IOP SLEEP, recording the return code.
2. Stop the ANS coprocessor and record CPU_CONTROL and BOOT_STATUS.
3. Reinitialize RTKit, which stops mailbox work and releases its shared
   buffers/SART mappings; record each release and the return code.
4. Detach the power domains, with begin/end markers.

The earlier parity kernel called `apple_rtkit_shutdown()`, which performs
steps 1 and 3, and only then stopped the coprocessor. The new
`apple_rtkit_shutdown_prepare()` exposes step 1 separately so this single
remove path can stop the CPU before RTKit reinitialization. Suspend and
system-shutdown paths retain their prior order. If either sleep request
fails, removal still stops the CPU, reports the failure and skips RTKit
reinitialization, matching the previous helper's early-return behavior.

The fixed panel now reports printk sequence gaps, filtered-message overflow,
and reader errors separately. It also shows the latest teardown marker. This
should distinguish the three causes combined as `LOG INCOMPLETE` in R3 and
show whether teardown reached CPU stop, buffer release, and power-domain
detach. Existing RTKit diagnostics report the actual AP/IOP acknowledgements.

The kernel built successfully with `ARCH=arm64 LLVM=1 Image.gz`; its config
SHA-256 matches P0/P1. The ARM64 fixed init and deterministic initramfs also
build successfully. `git apply --check` accepted the saved parity-to-order
patch against the preserved parity source.

## First run

The first ordering image was handed off at 14:01 MDT from a fresh proxy.
The handoff returned 0, the host trace had no NVMe init, and payload hashes
were unchanged. Linux matched all five warm direct reads, performed one
unbind, and displayed `TEARDOWN GENPD DETACH END`. It also displayed an ANS
crash notification, zero printk sequence gaps, no log-reader error, and 23
selected messages dropped after the verifier's 256-message retention cap.
Because that cap was treated as a log-integrity failure, the verifier stopped
before evaluating its crash gate and did not bind the device. The crash flag
is evidence that a crash notification arrived during this run; it is not yet
the result of the verifier's post-unbind crash decision.

The final screen does not expose the AP/IOP sleep ACKs, shutdown return, CPU
register readback or RTKit reinit return. A second initramfs has been built
with a 1024-message retention cap and explicit fields for those values. It
uses the same kernel and is ready for a fresh proxy run. The first run's
initramfs and screen capture are preserved under
`/home/btega/j604-boot/ans-review-n6miVhGq/C9-ORDER-20261012/`.

## Second run

The expanded initramfs was run at 14:07 MDT from a fresh proxy. The handoff
returned 0, with no m1n1 NVMe init and unchanged payloads. Linux again matched
all five warm reads and unbound once. The screen recorded AP QUIESCED ACK
`YES`, IOP SLEEP ACK `NO`, and shutdown prepare return `-62` (`-ETIME`). The
CPU_CONTROL readback was zero; RTKit reinit was not called because the IOP
sleep request timed out. The power-domain detach reached its end marker.
The ANS crash flag was set, so the verifier stopped before bind. Log capture
was complete: zero sequence gaps, zero retained-message overflow and no
reader error.

This run locates the stop before the proposed buffer-release ordering can
take effect. It does not test whether stopping the CPU before buffer release
changes the crash outcome, because `apple_rtkit_shutdown_prepare()` returned
before RTKit reinit. The code waits one second for each RTKit power ACK, and
the source maps a missing IOP ACK to `-ETIME`. The next small diagnostic adds
the management-send return for the IOP SLEEP request, to tell whether the
request was accepted by the mailbox before waiting for the ACK.

## Third run

The third image was run at 14:12 MDT, again from a fresh proxy. The handoff
returned 0, with no m1n1 NVMe init and unchanged payloads. The five warm reads
matched and one unbind completed. The panel reported IOP SLEEP TX `0`, no IOP
SLEEP ACK, and shutdown prepare `-62`. It also reported AP QUIESCED ACK `YES`,
ANS crash `YES`, CPU_CONTROL `0`, zero log gaps/drops and no reader error.
The crash gate stopped before bind; RTKit reinit was not called.

This confirms the mailbox accepted the outgoing IOP SLEEP request, but Linux
did not observe its ACK within the one-second wait. It does not establish
whether firmware failed to generate the ACK, Linux missed it, or the crash
notification interrupted progress. The buffer-release ordering hypothesis
remains untested because the shutdown handshake returns before reinit.

The next diagnostic will preserve a compact RTKit mailbox trace from the
IOP SLEEP request through the timeout, including incoming management messages
and crash notifications. It will not change power requests or retry the
transition. The third run's fixed-screen capture and host traces are saved
under the run directory in the results file; no rebind was attempted.

## Comparison and next steps

The successful m1n1 shutdown traces from upstream F, local U and relocated FR
all contain the same endpoint-0 Management sequence, with no trace drops:
AP power-state request (type 11, state `0x10`, message
`00b0000000000010`), AP ACK, IOP SLEEP request (type 6, state 1, message
`0060000000000001`), then IOP SLEEP ACK (type 7, state 1, message
`0070000000000001`). Linux's third run logged a successful mailbox send for
the same IOP SLEEP request but no parsed ACK before timeout. The m1n1 traces
show what a successful exchange looks like; they do not prove that Linux
received the same response or that firmware behavior was identical.

The next kernel should keep the power-management requests, timeout and
ordering semantics unchanged. In the disposable kernel tree, keep the RTKit
diagnostic ring open after NVME_READY, then freeze it only after the IOP SLEEP
wait returns and CPU_CONTROL has been stopped. Emit a bounded summary of
endpoint-0 receives between the IOP SLEEP send and `-ETIME`, including message
type/value and crash-notification timing. Keep collection allocation-free in
the receive path and avoid printk there; summarize after the wait so the
instrumentation does not delay the handshake. Do not retry the request or
attempt rebind after the crash gate.

Interpret the next capture against the m1n1 sequence: an IOP ACK in the raw
receive ring without a Linux ACK callback points toward receive/workqueue or
completion handling; no IOP ACK, with only a crash message or no receive,
points toward further firmware/state investigation. Only after locating the
missing ACK should we revisit RTKit reinit and buffer-release ordering. A
fresh LabOS proxy is required for that run; the existing proxy bootloader can
continue to be used, and no bootloader installation is part of this test.

Artifacts and hashes are recorded in
[`C9-ORDER-RESULTS-2026-10-12.json`](C9-ORDER-RESULTS-2026-10-12.json) and
the exact source delta is
[`diagnostics/kernel-c9/parity-to-order.patch`](diagnostics/kernel-c9/parity-to-order.patch).
The temporary kernel image and initramfs are under
`/home/btega/j604-boot/ans-review-n6miVhGq/C9-ORDER-20261012/`. The input
m1n1, DTB, read hashes, and bounded fresh-proxy handoff procedure match the
previous R run. This remains a targeted experiment, not a production fix or
proof that ordering caused the earlier crash.
