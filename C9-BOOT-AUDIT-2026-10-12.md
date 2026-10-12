# Boot-path audit — Linux vs m1n1 ANS session construction — Oct 12, 2026

Desk audit following [E3](C9-E3-SESSION-2026-10-12.md): everything
after the boot is eliminated and every protocol message compares
identical, so the divergence must be in how the session is created.
Sources: kernel TRACE tree (`drivers/soc/apple/{rtkit,sart,mailbox}.c`,
`drivers/nvme/host/apple.c`) and the diagnostic m1n1 tree
(C9-PREP `local-src/src/{rtkit,sart,asc,nvme}.c`).

## Audited clean — no divergence

- **SART**: the kernel driver and m1n1 share the same register
  formats and ops per version (v0/v2/v3 constants identical);
  `flags_allow` 0xff both. Independently closed empirically: C9
  snapshots showed SART entries byte-identical across the transition.
- **Mailbox**: neither side programs FIFO control at init; the kernel
  driver touches only interrupt masks. T8132 ANS uses
  `apple,asc-mailbox-v4`, and message transfer demonstrably works in
  both directions.
- **Endpoint buffers**: both sides allocate on IOP request, at the
  IOP-requested size, at SART-allowed addresses (kernel
  `dma_alloc_coherent`, m1n1 `memalign(16K)`). Addresses differ by
  allocator; the RELOCATE cell eliminated address reuse.
- **CPU control register**: identical. m1n1 `ASC_CPU_CONTROL` is
  offset 0x44 from the `/arm-io/ans` reg base, START = bit 0x10,
  set with a read-modify-write. Linux `APPLE_ANS_COPROC_CPU_CONTROL`
  is offset 0x44 from the same "ans" resource, RUN = `BIT(4)`.
- **Boot message tail**: after EPMAP and a drain of stray messages,
  m1n1 sends AP power ON — the same final step as
  `apple_rtkit_boot`.

## The control that isolates construction

The RESTART cells proved m1n1's **first** sleep of a session booted
from iBoot's handoff state succeeds (init → read → shutdown → init →
read, all in m1n1). So the pre-state iBoot leaves is not the poison:
m1n1 constructs a sleep-capable session from it and Linux does not,
in both Linux branches (branch-2 cold in L1, branch-3 warm in
ORDER/TRACE/E1/E3). The local m1n1 experiment already knew part of
this — its handoff code comments that a kernel cold boot of the
26.6.2 firmware "crashes the IOP", so m1n1 performs the cold boot
itself and hands Linux the warm state. Today's results extend that:
even the warm state Linux wakes is not sleep-capable.

## Remaining construction differences

1. **CPU-start strobe before INIT (branch 3).** m1n1's `rtkit_boot`
   unconditionally does `asc_cpu_start()` — setting the CPU_CONTROL
   START bit — immediately before sending IOP INIT, on every boot,
   warm or cold. Linux's branch 3 writes CPU_CONTROL not at all; it
   relies on the bit already reading set. If the START write is a
   strobe the IOP's power logic needs after a foreign sleep, Linux
   never performs it.
2. **INIT before HELLO (branch 2).** m1n1 sends IOP PWR STATE = INIT
   before expecting HELLO on every boot ("can be sent unconditionally
   to wake up a possibly sleeping IOP"). Linux's branch 2 never sends
   INIT: `apple_rtkit_boot` only waits for the EPMAP and IOP-ACK
   completions and then sends AP ON.
3. **PMGR sequencing.** m1n1's proven cycle includes `pmgr_reset` of
   ANS and ANS2 between sleep and the next boot; Linux relies on
   genpd attach at probe and its reset-controller assert in branch 2.
   No concrete mechanism identified from source; listed for
   completeness, not as a candidate.

Receive-side handling (interrupt vs polling, workqueue dispatch) is
not a candidate: the receive-ring run proved the sleep ACK never
reaches the mailbox FIFO.

## Next experiment (E4)

One diagnostic kernel on the TRACE tree making Linux's construction
match m1n1's in both branches: branch 3 asserts CPU_CONTROL RUN
immediately before the wake INIT send; branch 2 sends IOP INIT before
the boot waits. Run warm (the E1-style cell). If the resulting session
sleeps cleanly, construction is the cause and the two changes can be
separated afterwards; if it still fails, the remaining suspect is
PMGR/domain state, and the follow-up is to have the diagnostic m1n1
run its proven sleep → reset → boot cycle and hand Linux that exact
state in the same power session.
