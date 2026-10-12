# C10 — embedded Linux and interactive shell — 2026-10-12

Goal: boot an interactive Linux shell with warm ANS access without requiring
m1n1 to read the OS payload from NVMe. This bypasses the failing storage
restart on the boot path; it does not repair ANS sleep/restart.

Run/artifact directory:
`/home/btega/j604-boot/ans-review-n6miVhGq/C10-EMBED-20261012/`.
Results and frame hashes: `C10-EMBED-RESULTS-2026-10-12.json`.

## Construction

The known C9 local m1n1 binary (`8497c947…`) receives appended kernel,
DTB, initramfs and `chosen.bootargs` payloads. There is no `chainload=`
variable. The source's embedded-payload path boots Linux directly;
the final NVMe shutdown is a no-op because m1n1 has not initialized NVMe.
Linux can use the working iBoot warm state.

The ELF gives `_payload_start = _end = 0x3c0000`, exactly the raw binary's
length. The initial assembled image's segments, wrapper, length and
terminator were checked byte-exact. Kernel (`c778d33a…`, E4) and DTB
(`d7091e74…`) remain unchanged throughout these tests.

m1n1 documents direct Linux payloads in stage 1 or stage 2:
[m1n1 user guide](https://asahilinux.org/docs/sw/m1n1-user-guide/#configuring-to-boot-linux-directly).
The installed stage-1 path still needs its own hardware result; a passing
proxy-loaded image does not establish installed untethered operation.

## Proxy-loaded results

1. **Embedded diagnostic image: PASS.** 7,946,390 bytes; unchanged X1
   init with storage-mode `j604.test=C10-EMBED`. Frame `frames/f010.jpg`
   shows namespace YES, branch 3, five matching O_DIRECT reads, no ANS
   crash, no reset error, boot ID prefix `aedb5106`.
2. **Initial shell image: PASS.** 8,136,572 bytes. The shell appears and
   the startup verifier matches five reads. The operator confirms keyboard
   input and a second `ans-check` PASS. Small text and controlling-terminal
   setup were improved in the final image.
3. **Final install candidate: proxy PASS.** 8,140,659 bytes; SHA-256
   `32e0d6282c003da3a4be730bd9841b3903f440751f963a38ddbe2a087a1c3dfa`.
   Frame `final-frames/f015.jpg` shows read-only setup YES, storage-check
   exit 0, five matching reads, the larger font and a clean `j604#` prompt.
   This exact file is packaged for installation.

The proxy chainloader exits 1 after USB reconnection times out because
Linux has booted instead of another proxy. The captured Linux screen is
the outcome evidence; host exit 1 is not classified as a Linux failure.
Each upload started from an operator-confirmed fresh installed proxy.

## Shell behavior

- Static ARM64 BusyBox provides ash, inspection commands and an editor.
- `ans-check` invokes the existing Go `readBlocks` implementation through
  a `--verify` mode. It identifies the ANS driver/compatible and namespace
  ID 1, checks 4 KiB geometry, uses O_DIRECT, verifies the same five hashes,
  and returns an exit status. It does not mount, unbind or paint the screen.
- PID 1 mounts proc, sysfs and devtmpfs, sets discovered NVMe block devices
  read-only, saves boot logs and the startup check in RAM, and respawns the
  shell on tty1. Internal partitions are not mounted by init.
- A 16x32 PSF2 console font doubles the kernel's GPL-2.0 VGA 8x16 bitmap.
  `setsid -c` explicitly supplies the controlling terminal.
- `ans-check`, `dmesg`, `ls /dev/nvme*`, `cat /proc/meminfo`, `vi` and
  `stty` are available. This is a small development userspace, not a distro.

## Builds and validation

BusyBox 1.36.1 comes from the existing local source tarball. Musl 1.2.5
comes from its [release archive](https://musl.libc.org/releases/musl-1.2.5.tar.gz),
SHA-256 `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4`.
The cross compiler is Fedora's aarch64-linux-gnu GCC 15.2.1. The exact
BusyBox configuration is tracked in `diagnostics/userspace-c10/busybox.config`.

Musl was configured with the ARM64 target, disabled shared libraries,
enabled the GCC wrapper, and explicit GNU cross CC/AR/RANLIB. Kernel
ARM64 UAPI headers were exported using that kernel's `headers_install.sh`
and a locally built `unifdef`. BusyBox was linked statically through
musl-gcc, with the exported headers supplied using `-idirafter`.
Sources, configure/build logs and provenance remain in the artifact directory.

`scripts/build-c10-shell.py` checks ARM64/static ELF headers, parses init
with the target BusyBox under qemu-aarch64-static, checks required applets
and the symlink installer, builds deterministic newc/gzip, and reads back
every entry byte-exact. Shell arithmetic and SHA-256 were also exercised
under emulation. Existing Go runtime tests pass; modified Python scripts
parse; `git diff --check` passes.

## Installed test — pending

`scripts/prepare-c10-install.py` creates a package containing the exact
tested image, a bare C9 local proxy fallback, hashes and an installer.
The installer accepts only the inventoried LabOS System volume UUID
`46727C64-DC7F-4B50-844E-5E3CC41A2C02`, verifies the chosen payload's SHA-256,
and invokes `kmutil configure-boot` with the raw format/entry-point settings.
The fallback returns to a usable proxy; it is not claimed to reconstruct
the previous boot object byte-for-byte.

Current package: `serve/c10-recovery.tar.gz`, SHA-256
`4af2fe1c85742dbb1da98eb672abc46af59fea41330c015802b259b7c153f881`.
It is served temporarily from Fedora at `http://192.168.0.11:8765/`.
The operator has instructions to use **macOS paired Recovery Terminal**;
the minimal Linux shell is not the installation environment.

In Recovery:

```sh
cd /tmp
curl -f http://192.168.0.11:8765/c10-recovery.tar.gz -o c10-install.tar.gz
tar -xzf c10-install.tar.gz
bash /tmp/c10-install/install.sh install /Volumes/LabOS
```

The original installer reported a payload mismatch in Recovery. The host
verified the served image and its archive member byte-exact, and the
operator reported the matching hash prefix `32e0d6`. The checksum-tool
pipeline could disguise a failed tool as a mismatch; the corrected
installer prefers OpenSSL, parses output with shell builtins, enables
pipefail and prints expected/actual hashes on a real mismatch. The Linux
image is unchanged. An OpenSSL-only environment without awk or shasum
was tested with the full installer and a mocked kmutil; correct-volume
acceptance and wrong-volume rejection both passed. The operator then
confirmed that neither checksum tool is available in this Recovery.
The current package includes `c10-sha256`, a native ARM64 macOS Go helper
that only reads the named file and prints its SHA-256. The installer prefers
this helper. Its source is tracked as `scripts/c10-sha256.go`, checked on
the host against the complete payload; the Mach-O architecture and code
signature were inspected. Go build: CGO_ENABLED=0, GOOS=darwin,
GOARCH=arm64, `-trimpath -ldflags='-s -w'`.

After successful installation, shut down, disconnect the proxy tether,
select LabOS and run `ans-check`. Repeat on a fresh boot before claiming
reproducible untethered operation. If needed, use the same package in
paired Recovery with `install.sh proxy /Volumes/LabOS` to install the
bare proxy fallback.

This changes LabOS's boot object. It does not repartition, format or install
a root filesystem. Updating this embedded kernel/init requires another
Recovery configure-boot operation. ANS sleep/restart, sustained storage
validation, a persistent root and broader laptop support remain separate work.
