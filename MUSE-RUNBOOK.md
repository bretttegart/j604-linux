# Muse runbook: J604 ANS cold-start A/B test

> **Executed on Oct 7:** TETHER-A passed; CHAIN-A and CHAIN-B crashed; the
> stage1 shutdown audit then passed all measured teardown operations. Continue
> with the [post-audit diagnostic plan](POST-SHUT-AUDIT-PLAN-2026-10-07.md).
> The instructions below preserve the original experiment; results are in
> [TEST-RESULTS.md](TEST-RESULTS.md).

The original session starts with preparation and `BASE-0`. Its first objective is a reproducible
tethered read-only control and complete evidence from the failing SSD chain.
Then test one protocol difference: explicit IOP INIT on T8132 cold startup.

This runbook was prepared by static review on 2026-10-07. Read
[the review](REVIEW-2026-10-07.md) for evidence and
the longer-term desktop roadmap. Record outcomes in
[TEST-RESULTS.md](TEST-RESULTS.md), distinguishing observation from inference.

## Scope of this session

- Work from `~/git/j604-linux`; live source trees are `~/linux-asahi` and
  `~/m1n1-ctrr`; host proxy tools are in `~/bootloader/proxyclient`.
- Preserve the dirty live trees and existing `r5` payloads. Build experiments
  from a captured snapshot in isolated worktrees or copies. Include the
  untracked `t8132-j604-ramoops.dts` when copying the kernel state.
- Linux tests only read the internal SSD. Use the existing macOS/ESP staging
  workflow for individually named boot files, retaining existing boot files.
  No partitioning, filesystem creation, firmware restore, or boot-object
  replacement is needed for these experiments.
- Keep EP7, IRQs, power domains, NVMMU layout, queue settings, CTRR reservations,
  idle workaround, and timer workaround fixed between A and B. Leave GPU,
  desktop, hypervisor, and `rtkit_sleep()` behavior changes for separate tests.
- Start each hardware case from a fresh boot into the installed LabOS proxy.
  A crashed ANS instance is not a valid starting state for another comparison.
  Only one program may own `/dev/m1n1`; only one recorder may own the webcam.

## 1. Freeze the inputs before editing

These are host-only preparation commands. Use the same shell for the later
examples, or restore `J604_RUN_ROOT` to the directory printed here.

```bash
J604_RUN_ROOT=$(mktemp -d /home/btega/j604-boot/ans-review-XXXXXXXX)
mkdir -p "$J604_RUN_ROOT/snapshot" "$J604_RUN_ROOT/BASE-0"
printf '%s\n' "$J604_RUN_ROOT"

git -C /home/btega/git/j604-linux rev-parse HEAD > "$J604_RUN_ROOT/snapshot/review-repo-head.txt"
git -C /home/btega/linux-asahi rev-parse HEAD > "$J604_RUN_ROOT/snapshot/kernel-head.txt"
git -C /home/btega/linux-asahi status --short > "$J604_RUN_ROOT/snapshot/kernel-status.txt"
git -C /home/btega/linux-asahi diff HEAD --binary > "$J604_RUN_ROOT/snapshot/kernel.patch"
git -C /home/btega/m1n1-ctrr rev-parse HEAD > "$J604_RUN_ROOT/snapshot/m1n1-head.txt"
git -C /home/btega/m1n1-ctrr status --short > "$J604_RUN_ROOT/snapshot/m1n1-status.txt"
git -C /home/btega/m1n1-ctrr diff HEAD --binary > "$J604_RUN_ROOT/snapshot/m1n1.patch"
git -C /home/btega/bootloader rev-parse HEAD > "$J604_RUN_ROOT/snapshot/proxy-head.txt"
git -C /home/btega/bootloader diff HEAD --binary > "$J604_RUN_ROOT/snapshot/proxy.patch"

cp /home/btega/linux-asahi/.config "$J604_RUN_ROOT/snapshot/kernel.config"
cp /home/btega/linux-asahi/arch/arm64/boot/dts/apple/t8132-j604-ramoops.dts "$J604_RUN_ROOT/snapshot/"
cp /home/btega/linux-asahi/arch/arm64/boot/Image.gz "$J604_RUN_ROOT/snapshot/"
cp /home/btega/j604-boot/t8132-j604-ramoops.dtb "$J604_RUN_ROOT/snapshot/"
cp /home/btega/j604-boot/initramfs.cpio.gz "$J604_RUN_ROOT/snapshot/"
cp /home/btega/j604-boot/init.go "$J604_RUN_ROOT/snapshot/"
cp /home/btega/j604-boot/r5/stage1-diag.bin "$J604_RUN_ROOT/snapshot/"
cp /home/btega/j604-boot/r5/stage2-diag.bin "$J604_RUN_ROOT/snapshot/"
cp /home/btega/m1n1-ctrr/build/m1n1.bin "$J604_RUN_ROOT/snapshot/m1n1-current.bin"
cp /home/btega/j604-boot/m1n1-ctrr-c87cf83b.bin "$J604_RUN_ROOT/snapshot/m1n1-known-tethered.bin"
sha256sum "$J604_RUN_ROOT"/snapshot/* > "$J604_RUN_ROOT/snapshot.sha256"
```

Check statuses for additional untracked inputs; a Git diff does not include
them. Preserve any newly relevant files too. Compare the payload hashes with
the review. Differences are not automatically errors, but must be explained
before using historical results as the control.

Keep full local logs; redact the device serial before sharing or committing
them. Do not add videos, firmware blobs, or large binaries to this repository.

## 2. BASE-0: reproduce the existing tethered control

Use the frozen kernel, DTB, initramfs, and saved `c87cf83b…` bootloader. This
case uses the old diagnostic init, so its display and automatic reboot
behavior are historical limitations, not new test behavior.

Start the camera before booting, using the existing working camera setup.
If using `~/j604-boot/webcam-record.sh`, record for 300 seconds to
`$J604_RUN_ROOT/BASE-0/screen.mkv` in a separate terminal. Verify a preview is
readable first; raw52's dark frames were inadequate for a full transcription.

From the host, with the Mac freshly in its installed proxy:

```bash
cd /home/btega/bootloader/proxyclient
sg dialout -c "script -qefc 'env M1N1DEVICE=/dev/m1n1 timeout 90 venv/bin/python tools/chainload.py -n -r $J604_RUN_ROOT/snapshot/m1n1-known-tethered.bin' '$J604_RUN_ROOT/BASE-0/chainload.log'"
```

Wait for `Proxy is alive again`. Then:

```bash
sg dialout -c "script -qefc 'env M1N1DEVICE=/dev/m1n1 timeout 210 venv/bin/python tools/linux.py -b \"idle=nop nokaslr loglevel=8 console=tty0 fbcon=nodefer\" $J604_RUN_ROOT/snapshot/Image.gz $J604_RUN_ROOT/snapshot/t8132-j604-ramoops.dtb $J604_RUN_ROOT/snapshot/initramfs.cpio.gz' '$J604_RUN_ROOT/BASE-0/linux.log'"
```

Expected: Linux reaches init and the NVMe namespace/read check succeeds.
The current init may instead show diagnostic text and park because ANSCHK
is present; that alone is not failure. Determine whether the namespace is
present and the read check actually ran. If the old init hides that result,
record BASE-0 as incomplete and use the corrected common init in TETHER-A
to obtain the measurement. Do not infer RDOK just from enumeration.

Host timeout 124 is not a kernel failure classification. A chainload into a
bare proxy should reconnect; a combined boot image that immediately enters
Linux may not. Stop retrying if the USB connection repeatedly cycles: inspect
the screen and recover to a fresh proxy before another test.

If the previously working path clearly fails, capture that regression first.
Do not interpret a later A/B result against an assumed working control.

## 3. Prepare shared diagnostics: kernel A and one common initramfs

These are implementation tasks for Muse, not changes already made here.
Do them once, before building the two comparison kernels.

**Kernel diagnostics:**

1. Move the `ANSBR 3` print outside the comment. Mark every reset-work path
   unambiguously, including the running-but-not-BOOT_STATUS_OK path. Include
   `CPU_CONTROL`, `BOOT_STATUS`, and software RTKit running/crashed state.
2. Raise the printk ring to 1 MiB (`CONFIG_LOG_BUF_SHIFT=20`). Add finite,
   boot-time diagnostics for reset results, CPU RUN, management TX/RX,
   HELLO/version, endpoint-map completion, buffer requests/replies, IOP ACK,
   AP ON, and completion wait results. Include device identity and message
   values. Explicit prints are simplest for the current configuration;
   `loglevel=8` does not turn on compiled-out `dev_dbg()` calls.
3. Keep full crash text and unknown-section dumps. Record SART address,
   size, and flags through the driver where appropriate; avoid arbitrary
   MMIO probing from the host. Do not alter SART permissions for observation.

**Diagnostic init:**

1. Identify the experiment from a `j604.test=` boot argument and print
   `/proc/cmdline`, the kernel version, and the current boot ID if available.
2. Capture `/dev/kmsg` without duplicate records. Read continuously while
   waiting for storage, retaining sequence numbers. Do not stop before a
   delayed probe finishes, and report gaps/overruns.
3. Show a persistent summary of branch, CPU/BOOT_STATUS, namespace/read-test
   outcome, first crash/assertion, and reset error. Recognize the actual
   `co-processor has crashed` message and retain the owning device name.
4. Preserve the complete log in RAM. Page it on the framebuffer without
   truncating bytes: wrap long lines, show page numbers, and cycle slowly
   enough to record every page. Timed cycling works without adding evdev.
5. Keep the live failure visible; do not automatically reboot. Do not let
   stale pstore content prevent the current boot's diagnostics from running.
6. When NVMe is present, record logical block size and capacity, read the
   GPT header at the reported logical-block offset, and repeat reads of a
   fixed small region to compare checksums. Use O_RDONLY. Reopening the
   device or repeating buffered reads may hit the cache; label these as a
   smoke test, not proof of repeated physical media reads or write safety.

If textual evidence is insufficient, the next logging improvement is to
retain an owned copy of the binary crash buffer and expose it through an
available RAM-based interface. The callback's existing buffer is freed on
return. Do not make an unproven USB/network transport a prerequisite for the
first comparison; paginated text is the immediate available channel.

Use the existing kernel toolchain and captured configuration in an isolated
tree. The current build uses Clang/LLVM for arm64; a typical build is
`make ARCH=arm64 LLVM=1 -j8 Image.gz`, after `olddefconfig`. Record the actual
tool versions and configuration diff. Do not replace the configuration with
a new defconfig. Preserve the frozen DTB for this comparison.

Save the outputs as:

```text
$J604_RUN_ROOT/common/initramfs.cpio.gz
$J604_RUN_ROOT/common/t8132-j604-ramoops.dtb   (copy of frozen DTB)
$J604_RUN_ROOT/A/Image.gz
$J604_RUN_ROOT/A/source.patch
$J604_RUN_ROOT/A/kernel.config
$J604_RUN_ROOT/A/build.log
```

Verify the common initramfs contains the new ARM64 init. Verify the kernel
contains both branch markers, and the A source diff adds diagnostics without
changing the original cold/warm startup decisions. Keep all A/B artifacts
after each build; do not let a subsequent build overwrite kernel A.

## 4. TETHER-A and CHAIN-A: establish the instrumented comparison

For **TETHER-A**, use the same two-command method as BASE-0 with kernel A,
the common DTB/initramfs, and the frozen `m1n1-current.bin`. Include
`j604.test=TETHER-A` in bootargs. This verifies the exact bootloader build
used in the diagnostic stage images as well as the new diagnostics. If this
regresses, compare the saved `c87cf83b…` bootloader separately before proceeding.

For **CHAIN-A**, assemble an image with that same bootloader, kernel A,
common DTB, and common initramfs:

```bash
mkdir -p "$J604_RUN_ROOT/CHAIN-A"
python3 /home/btega/git/j604-linux/assemble_boot.py \
  --m1n1 "$J604_RUN_ROOT/snapshot/m1n1-current.bin" \
  --kernel "$J604_RUN_ROOT/A/Image.gz" \
  --dtb "$J604_RUN_ROOT/common/t8132-j604-ramoops.dtb" \
  --initramfs "$J604_RUN_ROOT/common/initramfs.cpio.gz" \
  --var 'chosen.bootargs=idle=nop nokaslr loglevel=8 console=tty0 fbcon=nodefer j604.test=CHAIN-A' \
  --out "$J604_RUN_ROOT/CHAIN-A/stage2-ans-a.bin"
```

Read the existing stage1 chainload specification to identify the ESP PARTUUID;
verify it against the actual ESP. Stage `stage2-ans-a.bin` through the existing
macOS workflow. Record its hash after copying to the ESP, with a fresh read
of the destination file. Keep `/stage2.bin` and `/stage2-diag.bin` intact.

Create a temporary stage1 that points at the new filename. Set
`J604_ESP_PARTUUID` to the verified value first:

```bash
: "${J604_ESP_PARTUUID:?Set this to the verified existing ESP PARTUUID}"
python3 /home/btega/git/j604-linux/assemble_boot.py \
  --m1n1 "$J604_RUN_ROOT/snapshot/m1n1-current.bin" \
  --var "chainload=${J604_ESP_PARTUUID};/stage2-ans-a.bin" \
  --out "$J604_RUN_ROOT/CHAIN-A/stage1-ans-a.bin"
```

After a fresh boot into the installed proxy, upload this temporary stage1
with `chainload.py -n -r`, recording the session as in BASE-0. The temporary
stage1 performs the SSD read and normal ANS shutdown. It does not replace the
installed LabOS boot object. Capture the full screen sequence through Linux
init. Confirm `j604.test=CHAIN-A`, branch 2, CPU/BOOT_STATUS, and the first
crash. If it takes another branch, report that rather than calling it a
reproduction of the cold-path failure.

Firmware evidence per case: retain the two raw mBoot identifiers from the
bootloader log, plus any separately obtained macOS build/LabOS identity.
An installed macOS version alone does not establish the coprocessor firmware.

## 5. Kernel B: one T8132 cold-start change

Start from kernel A's exact source/configuration and common initramfs. In
`apple_nvme_reset_work()`, immediately after the write that sets CPU RUN in
the stopped-CPU branch, replace that branch's call with:

```c
if (of_device_is_compatible(anv->dev->of_node,
                            "apple,t8132-nvme-ans2"))
        ret = apple_rtkit_wake(anv->rtk);
else
        ret = apple_rtkit_boot(anv->rtk);
```

Do not replace all calls to `apple_rtkit_boot()`. Preserve the reset order,
already-working warm branch, and EP7 code. The source difference A→B should
be only this conditional call; build metadata and payload test labels will
necessarily differ. Record that diff and hash kernel B.

Assemble/stage `stage2-ans-b.bin` and a corresponding temporary
`stage1-ans-b.bin` by the CHAIN-A recipe, substituting kernel B and
`j604.test=CHAIN-B`. Use the identical m1n1 prefix, DTB, and common initramfs.
Verify the destination hash. Boot once from a fresh installed proxy.

## 6. Interpret before choosing another change

| Case | Required observation | Next action |
|---|---|---|
| TETHER-A | Namespace plus completed read/checksum test; complete diagnostics. | Proceed to CHAIN-A. |
| CHAIN-A | Actual cold branch and complete failure trace, or an unexpected success with artifact IDs. | If reproduced, run CHAIN-B. If not, resolve the changed conditions first. |
| CHAIN-B succeeds | INIT/handshake completes; controller ready; namespace and read check succeed. | Revert to the unchanged A image for CHAIN-A2, then repeat B on two fresh boots. |
| CHAIN-B fails differently | First protocol divergence, message order, assertion, error, and registers captured. | Choose the next experiment from that divergence. Do not call it “same crash.” |
| CHAIN-B fails identically | Same failing branch and comparable complete crash evidence. | Audit shutdown ACK/reset handling next; preserve A/B logs. |
| Missing diagnostics or wrong artifact/branch | Incomplete or invalid comparison. | Repair measurement/provenance; do not infer a driver result. |

Three fresh B successes with repeated reads, accompanied by reproducible A
failure, support the INIT hypothesis. They still do not establish sustained
I/O reliability, write safety, suspend, or all firmware versions.

If shutdown handling becomes the next test, first observe the actual
sleep/quiesce ACKs and teardown outcomes with behavior held fixed. Then
normalize `rtkit_sleep()`'s Boolean convention and propagate its failure in
a separate variant if warranted. Instrument the successful
`nvme_shutdown()` path, not only `nvme_init()` cleanup. Keep the chosen Linux
kernel fixed for that separate experiment. Do not leave ANS running while
freeing its firmware-visible memory or removing mappings.

## 7. Return an evidence package

For each attempted case, append one summary row in TEST-RESULTS.md and a
record using its template. Keep larger artifacts under `J604_RUN_ROOT`:

- Exact command, payload and ESP destination hashes, component hashes,
  source/configuration diffs, build log, and toolchain versions.
- Full host transcript, video/full page capture, current-boot kernel log
  when recoverable, and retained binary firmware crashlog if available.
- Firmware IDs, observed branch/registers, first assertion, handshake
  milestone reached, namespace geometry, and read-test results.
- Host exit status separately from Mac outcome. Mark unreadable or absent
  evidence as unknown. Redact device serials from shared copies.

End the first session with a clear A/B result or a specific failed
prerequisite. The next session can then address shutdown/state or begin the
tethered desktop work without repeating an ambiguous experiment.
