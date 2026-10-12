# C9 Linux-managed ANS teardown test — Oct 12, 2026

**R stopped after one Linux unbind: five warm direct reads matched, then an
ANS crash was reported before any rebind.** The final panel also reports
incomplete log capture. This is a Linux-managed teardown failure without
prior m1n1 storage use. It is not a failed rebind/cold-start result, and
does not yet identify the operation that caused the crash.

Run directory:
`/home/btega/j604-boot/ans-review-n6miVhGq/C9-RUNTIME-20261012/`.
The owner supplied a fresh LabOS proxy for each of three attempts. The first
two stopped at verifier guards before either driver control was written;
the third performed one unbind and stopped before bind. No SSD data writes,
internal mounts, ESP changes, blessing, installed bootloader replacement
or push occurred.

## Test implementation and checks

The kernel is the exact [P0/P1 parity image](C9-PARITY-SESSION-2026-10-12.md).
The temporary local m1n1 and input DTB also match P0/P1. Only the initramfs
and cell label change. Each host trace contains zero m1n1 INIT_BEGIN events,
pre-handoff CPU RUN=`0x10` and BOOT_STATUS=`0xde71ce55`. Kernel/initramfs/
prepared-DTB readbacks are unchanged and the boot requests acknowledge zero.

[`c9_runtime.go`](init/c9_runtime.go) adds this sequence to the existing
[fixed-screen verifier](init/c9_status.go):

1. Resolve the actual `4c5cc0000.nvme` platform device and its `nvme-apple`
   driver link; require `apple,t8132-nvme-ans2` compatibility.
2. Discover ANS namespaces through sysfs ancestry and select **namespace
   ID 1**, not an arbitrary namespace or a fixed controller number. Check
   its 4096-byte logical block size and actual block-device node.
3. Complete the five aligned O_DIRECT reference reads, closing the read
   descriptor and releasing its buffer before proceeding. Retain these
   before-read counts/hashes separately from the after-read result.
4. Require a completed `/dev/kmsg` marker, no observed log gaps/errors,
   ANS warm branch 3 and no crash/reset failure. Check every ANS namespace
   and partition for mounts and holders, not just namespace 1.
5. Write the exact platform device name to `unbind` once. Require the
   driver link and all ANS namespaces to disappear. Check logs before bind.
6. Only if those checks pass, write `bind` once, discover the rebound
   namespace ID 1, verify its ancestry, and repeat the direct reads.

Control writes have 90-second deadlines, namespace discovery 45 seconds,
direct reads 90 seconds and log markers five seconds. A blocked operation
is reported as pending/INCONCLUSIVE; a deadline does not cancel target code.
No later action, retry, cleanup rebind or reboot is queued after failure.
Controller numbering may change; reset-error attribution follows controllers
whose sysfs parents have been verified as the actual ANS device.

The init stores bounded selected ANS phase messages and report JSON on
tmpfs. These are not exported digitally to Fedora. The fixed panel supplies
only the displayed summary; its raw log-integrity counters are not shown.

[`build-c9-init.py`](scripts/build-c9-init.py) builds both Go source files
as a stripped static ARM64 ELF and verifies its deterministic newc/gzip
archive contains the exact executable and required directories. Final init
is 2424994 bytes; final gzip archive is 986613 bytes, SHA-256
`1f199d0cb9d8ca2df640ba328a817d884c51e29e8e5e7c285f77558ef1051aa4`.

Eleven [native checks](init/c9_runtime_test.go) pass with Go's race detector:
namespace ancestry/renumbering, explicit ID-1 selection with multiple
namespaces, rejection of mounts on another ANS namespace or partition,
holder and compatibility gates, proof of unbound state, dynamic reset-error
attribution, stop-on-first-failure, no bind after an unresolved timeout,
actual O_DIRECT fixture reads/mismatch/cancellation, ANS/MTP log attribution,
newline-terminated marker/readback with metadata, and no creation of missing
control files. The complete ARM64 init/archive build succeeds.

## Preserved attempts

| Attempt | Boot ID prefix | Before reads | Driver controls | Result |
|---|---|---:|---|---|
| `R-RUN`, 13:33 MDT | `03776046` | 0/5 | Neither attempted | Discovery rejected multiple ANS namespaces |
| `R2-RUN`, 13:38 MDT | `9859e707` | 5/5 | Neither attempted | Log marker deadline before unbind |
| `R3-RUN`, 13:42 MDT | `0296c6f4` | 5/5 | One unbind; no bind | ANS crash reported in teardown; log incomplete |

The first guard was too strict: ANS legitimately exposes multiple
namespaces. It was corrected to select sysfs `nsid=1`; checks for mounts
and holders still cover all namespaces. The second marker omitted a newline.
This kernel's printk implementation can leave a final record without a
newline unfinalized until later output. The final marker explicitly ends in
newline, and readback ignores `/dev/kmsg` metadata continuation lines.
Neither preparatory failure is classified as an ANS restart failure.
Each original image, manifest, source version, host trace and camera frame
is preserved; later builds use separate `corrected/` and `final/` inputs.

## Final observed panel

| Field | Observed |
|---|---|
| Cell / status | C9 R / FAIL |
| Before direct reads | MATCH 5 OF 5 |
| After direct reads | 0 OF 5; none attempted |
| Namespace at end | NO, following intentional unbind |
| ANS branch | 3, the original warm wake; no rebind branch entered |
| ANS crash / reset error | YES / NONE |
| Unbind / bind | OK / NA |
| Boot ID prefix | `0296c6f4` |
| Final phase / error | CHECK UNBOUND / LOG INCOMPLETE |

The final frame is `R3-RUN/status-final.jpg`; its SHA-256 and all attempt
transcriptions are in the [machine summary](C9-RUNTIME-RESULTS-2026-10-12.json).
The C920 captured bounded 1920×1080 MJPEG stills with 60 startup frames
discarded. Initial and final frames agree.

The program reached CHECK UNBOUND only after the unbind write completed,
the driver link disappeared and all ANS namespaces were absent. The next
log check failed before bind. Its ANS crash flag was false at the verified
warm gate and true on the final panel. This places the observed notification
in the Linux teardown interval; it does not locate the firmware fault within
an individual operation.

`LOG INCOMPLETE` combines sequence gaps, filtered-log capacity overflow or
a reader error. The panel does not distinguish them. No full phase log,
shutdown ACK proof, post-unbind SART table or new fault-register context was
exported. Do not infer a clean RTKit shutdown from `UNBIND OK`:
`apple_nvme_remove()` ignores `apple_rtkit_shutdown()`'s return.

## Concrete next comparison

The preserved parity source shows an ordering difference:

- Linux `apple_rtkit_shutdown()` sends AP QUIESCED and IOP SLEEP requests,
  then calls `apple_rtkit_reinit()`, which stops the mailbox/workqueue and
  releases RTKit shared buffers/SART mappings. `apple_nvme_remove()` writes
  CPU control zero **after** that call, then detaches power domains.
- The successful measured m1n1 path confirms sleep ACKs, stops the CPU,
  performs the resolved ANS reset, then frees RTKit buffers/removes mappings.

This is a source/capture difference, not proof of causation. The next
comparison should expose the exact log-integrity failure and capture actual
power ACKs, CPU-stop, buffer release/SART state and power-domain teardown
phases. A targeted NVMe teardown ordering experiment can then test CPU stop
before buffer release, without treating generic sysfs completion as ACK proof.
No such kernel change or additional transition was executed here.
