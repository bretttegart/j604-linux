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
patch against the preserved parity source. These are preparation results;
the Mac has not run this image yet.

Artifacts and hashes are recorded in
[`C9-ORDER-RESULTS-2026-10-12.json`](C9-ORDER-RESULTS-2026-10-12.json) and
the exact source delta is
[`diagnostics/kernel-c9/parity-to-order.patch`](diagnostics/kernel-c9/parity-to-order.patch).
The temporary kernel image and initramfs are under
`/home/btega/j604-boot/ans-review-n6miVhGq/C9-ORDER-20261012/`. The input
m1n1, DTB, read hashes, and bounded fresh-proxy handoff procedure match the
previous R run. This remains a targeted experiment, not a production fix or
proof that ordering caused the earlier crash.
