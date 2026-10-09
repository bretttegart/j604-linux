# Installed firmware inventory — Oct 9

User collected these reports in macOS and returned them to Fedora:
`/home/btega/Downloads/j604-firmware-inventory-20261009T132914/`.
This directory contains metadata reports only, not ANS firmware images.
No additional Linux payload was built or booted during this review.

## What the reports establish

- Live macOS is **26.6.2 (25G83)**.
- Main macOS Preboot is mounted at `/System/Volumes/Preboot` (`disk4s2`
  in this inventory). iSCPreboot is mounted at `/System/Volumes/iSCPreboot`.
- LabOS is in a separate APFS container, UUID
  `EFDE6F33-3F73-4DD6-BAEE-50DCDCF8C6EB`, on physical store `disk0s3`.
  LabOS Data UUID is `BFADFFD5-AC55-403F-8A24-1217858C9FD7`; System UUID
  is `46727C64-DC7F-4B50-844E-5E3CC41A2C02`.
- LabOS **Preboot is unmounted**, UUID
  **`F759066A-59CD-4808-BF39-2BBD8BBF07D6`**, currently `disk3s4`.
  The collector uses the persistent UUID rather than assuming that disk
  numbering remains the same after a reboot.
- Current macOS chosen metadata reports stage-two/OS firmware
  `mBoot-18000.161.10` and stage-one/system firmware `mBoot-20457.1.29`.
  These reports do not establish an incompatible combination or its cause.

## Coverage correction

The original inventory script stopped at:

```text
find: /System/Volumes/iSCPreboot/.TemporaryItems: Operation not permitted
```

Its `set -e` propagated `find`'s nonzero exit. Therefore it never scanned
normal macOS Preboot, and LabOS Preboot was unmounted anyway. Its four
version-plist paths do **not** establish that installed ANS images are absent.
The script now prunes known housekeeping directories, records each scan's
status, and continues after a partial scan.

## Signed SFR manifest recovered from chosen metadata

The `sfr-manifest-data` property contains a 12,200-byte DER IM4M manifest.
Its SHA-384 is:

```text
315d71cc99ad4bb2a7d7717ebcd7605bdf01025c9aa74418d34bfde0713d7b3f643b26de2d6ef4336d60b5e4f1cc9d27
```

This agrees with the current chosen `sfr-manifest-hash`. Several chosen
secure-boot-hash properties, including `ansf`, repeat that common manifest
hash. They must not be mistaken for hashes of individual firmware payloads.

A bounded DER walk of the `ansf` entry finds a 48-byte `DGST` value:

```text
a22d9804b32ff94be7582b822b3ed5c52473ca29313e1664dc7b71540337d17980b953cf447b03a6b1a8fe5407a4a542
```

The digest TLV begins at manifest offset `0x2f5`. The whole local 26.6.2
ANS IM4P hashes differently with SHA-384; digest coverage must be validated
against an installed candidate before using that comparison to identify an
image. More importantly, this is **current macOS boot evidence**, not a
capture of the LabOS chosen node used for C5. Neither the manifest nor a
common RTKit version alone proves a candidate matches C5.

Offline binary and analysis records are preserved under
`/home/btega/j604-boot/ans-review-n6miVhGq/ANS-FIRMWARE-INVENTORY-20261009/`
as `sfr-manifest.der` and `manifest-analysis.json`.

## Next action in macOS

Run [the installed-firmware collector](scripts/collect-ans-firmware-macos.sh):

```bash
scp btega@sunki:/home/btega/git/j604-linux/scripts/collect-ans-firmware-macos.sh ~/Downloads/
bash ~/Downloads/collect-ans-firmware-macos.sh
```

It verifies LabOS Preboot's UUID, resolves the current device identifier,
and mounts that volume read-only at a temporary directory if unmounted.
An already-mounted volume is read in place without changing its mount mode.
The exit handler unmounts only a volume this script mounted; it never uses
forced unmounts. Read-only mount behavior is documented in Apple's
[diskutil manual](https://leopard-adc.pepas.com/documentation/Darwin/Reference/ManPages/man8/diskutil.8.html).

It inventories both normal Preboot and iSCPreboot, explicitly visits
`SFR/current` to handle a possible symlink, and scans LabOS Preboot. It copies
selected ANS images and manifests, preserving root labels and relative paths,
with SHA-256 checksums. Other IMG4/IM4P files in firmware paths are inspected
for ANS type/description within their first 512 bytes using binary-safe
system `grep`, without requiring `strings` or Apple developer tools.
Files over 64 MiB are
listed rather than copied. This is discovery with explicit coverage logs,
not a guarantee that every possible firmware storage format is recognized.

Copy the resulting `j604-firmware-collection-*` directory back to Fedora
Downloads. Then validate the checksums, inspect manifests and image types,
decompress candidate payloads, and compare their RTKit/client identity and
manifest association with C5 before interpreting its PC/stack.

Validation: Bash syntax passes. Mocked command runs cover an unmounted
volume (read-only mount and owned unmount), a UUID mismatch (no mount), an
already-mounted volume (no mount/unmount), continuation after a partial
`find` failure, binary copying, and the Linux-host guard. The actual macOS
collection remains pending. Mock harness is retained with offline artifacts
as `check-collector.py`.

## Returned collection and offline candidate — completed

Collection received at
`/home/btega/Downloads/j604-firmware-collection-20261009T135607/`.
**All 185 copied-file SHA-256 checksums pass.** Mount actions confirm the
LabOS Preboot mount and subsequent unmount succeeded. Both iSCPreboot
scans and LabOS Preboot completed; main Preboot's scan was partial because
`com.apple.security.cryptexd` denied traversal. Its other boot paths were
inventoried. No IMG4/IM4P firmware images were selected: the collection
contains 155 IM4M files, 25 plists, and five DER files. This does not imply
an ANS image is absent from other storage or an embedded bundle.

The returned version files distinguish three components:

| Component | Version | Build |
| --- | --- | --- |
| Running macOS and its restore files | 26.6.2 | 25G83 |
| LabOS Preboot restore/cryptex files | 26.7.1 | 25G241 |
| iSCPreboot SFR/current | 27.0.1 | 26A434 |

LabOS's restore BuildManifest contains the J604 identity (`j604ap`, chip
`0x8132`, board `0x22`) but no ANS component entry. Its boot directory is
`BFADFFD5-AC55-403F-8A24-1217858C9FD7/boot/`
`F739608175A3A1C3D67712DB665235B94A2F18DDCF8047E92418D4F42F3AE648257A136D9E11E3D947123524621B87B6/`.
These component versions are observations, not proof that combining them
causes the ANS crash. Asahi's [boot-flow documentation](https://github.com/AsahiLinux/docs/blob/main/docs/fw/boot.md)
distinguishes the early loader from the OS-specific loader in Preboot.

The collected `SFR/current/apticket.der` is byte-for-byte identical to the
previously recovered chosen `sfr-manifest-data`. Using that SFR build as a
lead, the host fetched just BuildManifest and T8132 ansf/rans entries from
[Apple's 27.0.1 restore archive](https://updates.cdn-apple.com/2026FallFCS/59241290-5d51-4ca8-9df4-31624b9a4eac/UniversalMac_27.0.1_26A434_Restore.ipsw)
with verified HTTP byte ranges. The successful extraction downloaded
**4,419,622 bytes**, rather than the entire 26,637,307,067-byte archive.
ZIP CRC checks passed. Nothing was installed or flashed.

For `Firmware/ansf.t8132_ASP3.release.im4p`:

- Description: `AppleStorageFirmwareASP3-241.0.12~642`.
- Container SHA-256:
  `5db4aac1f16e1889f93352e012708f654ef10f41dc471c399cda24497c5bc7b9`.
- **Container SHA-384 exactly equals the installed SFR's individual ANS DGST**
  (`a22d9804...07a4a542`, full digest above), also present in the restore
  archive's J604 erase/upgrade BuildManifest identities. This validates the
  digest coverage for this candidate as the whole IM4P container.
- Decompressed image: 6,986,032 bytes, SHA-256
  `93d9bdf1f39b3fef55c7a30603be39f6fc29b854c2afea65e318cea870239486`.
- Embedded RTKit string: **`RTKit_release-3514.0.15.release`**, matching C5.
- Embedded client: `t8132_ASP3.release-AppleStorageFirmwareASP3-241.0.12~642~241.0.12~642`.
- `rans` has a different container/type/description but the same compressed
  payload and decompressed image. It was retained for analysis only.

Evidence and derived metadata are in
[ANS-FIRMWARE-CANDIDATE-2026-10-09.json](ANS-FIRMWARE-CANDIDATE-2026-10-09.json).
Binary artifacts, original BuildManifest, range-download log, hashes, and
tentative disassembly are in
`/home/btega/j604-boot/ans-review-n6miVhGq/ANS-FIRMWARE-CANDIDATE-27.0.1/`.
Collection review is `ANS-FIRMWARE-INVENTORY-20261009/collection-review.json`.

## Historical pending check — superseded by live capture and C5 repeat

The candidate is an exact match to **current macOS SFR's manifest**, and
matches C5's RTKit string. LabOS's actual chosen SFR manifest has not yet
been captured directly. Runtime PC-to-file mapping also remains unvalidated:
straight Mach-O mapping is only a hypothesis, and the apparent Ccst frame
locations did not uniformly line up with call-return sites. Do not infer a
power/thermal fix from that tentative disassembly. The full transcribed
Cver prefix was not found verbatim in the image; its first 16 instruction
bytes occur at file offset `0x4214`, which alone is not unique build identity.

Next, return the Mac to a **fresh LabOS Running proxy screen**. The prepared
[metadata capture](scripts/capture-labos-adt.py) reads only the boot-argument
and ADT DRAM buffers via the existing proxy protocol, saves raw bytes and
checksums, and leaves the proxy available. It avoids the standard setup
module's panic-counter reset and heap-limit changes, and performs no ANS
MMIO, boot, power, reset or firmware-upload operations.

Fedora-host command once the proxy is ready:

```bash
/home/btega/bootloader/proxyclient/venv/bin/python \
  /home/btega/git/j604-linux/scripts/capture-labos-adt.py
```

Inspect LabOS's chosen manifest hashes/data and ANS memory mapping before
using the candidate for address-level conclusions. If needed, acquire a
bounded firmware DRAM capture only after the ADT identifies and validates
that region. Then continue with the unchanged C5 repeat in the next-test
plan. The metadata reader's syntax, imports, layouts and `--help` pass;
hardware execution remains pending (`/dev/m1n1` is currently absent).

## Fresh LabOS live capture — completed at 14:18 MDT

The user confirms a full-Mac restore using
`UniversalMac_26.6.2_25G83_Restore.ipsw`. Preserve that history. The current
metadata does not establish when the later SFR/LabOS components appeared,
does not disprove the restore, and does not justify blaming the crash on
an incompatible combination.

The fresh proxy capture directly reports:

- LabOS boot UUID `BFADFFD5-AC55-403F-8A24-1217858C9FD7`, matching the
  collected Preboot paths and boot manifest `f7396081...621b87b6`.
- Stage-two tag `mBoot-18000.161.10.701.1`; stage-one/system tag
  `mBoot-20457.1.29`. m1n1's display labels these 26.7 and 27.0; those labels
  are version-family mappings, whereas the collected plists identify
  26.7.1 and 27.0.1 component builds.
- ANS manifest pointer `0x103fff58078`, length `0x2fa8` (12,200 bytes).
  Read from bounded DRAM, it is **byte-for-byte identical** to the installed
  SFR/current apticket and current macOS chosen manifest. Its SHA-384 matches
  LabOS's chosen `ansf`/`sfr-manifest-hash`.
- ANS nub marked `pre-loaded=1`, `running=1`. ADT segment table identifies
  `__TEXT`: physical `0x10000004000`, IOVA 0, size `0x244000` (2,375,680
  bytes). Explicit chosen DRAM bounds are base `0x10000000000`, size
  `0x400000000` (16 GiB); the text and manifest reads are within them.
- Captured ANS __TEXT SHA-256:
  `abc2261691bb8016a93f71b6ea516dd643fc8bb32d1c77c2febda88283620e1c`.
  Comparing against the candidate Mach-O's __TEXT (`fileoff=0x4000`) finds
  just **six differing bytes**, in two startup metadata fields at text
  offsets `0x4225–0x4226` and `0x423e–0x4241`. Exact differences are retained
  in JSON; no instruction-level difference was found at C4/C5's reported
  PC windows. This is strong image identity and fresh-boot mapping evidence,
  not a claim that the entire live image is byte-identical to the IPSW.

The raw capture is
`/home/btega/j604-boot/ans-review-n6miVhGq/LABOS-ADT-20261009T141804-0600/`;
ADT SHA-256 is
`a64ec21f9fc087ff852cdea5336112fbb9d2afc552f48b4770b7c4b0953d2c98`.
[Live capture summary](LABOS-FIRMWARE-CAPTURE-2026-10-09.json) records the
comparison and restore-history distinction. Reads left the proxy available;
no ANS MMIO, power/reset operations or Linux upload occurred during capture.

The reader now has `--ans-text` for this bounded manifest/text acquisition.
One intermediate attempt stopped at its DRAM-bound guard before reading
ANS memory: the explicit bounds are on `/chosen`, not `/arm-io`; corrected
and captured successfully. The initial and successful follow-up ADTs have
the same hash.

Fresh-boot firmware identity is now established beyond a version string.
C5's call-stack layout and asynchronous fault-address translation still
need validation: do not equate its PC with the instruction that caused
SError or infer a thermal fix from nearby strings. Next is the unchanged
C5 repeat, with a full-console camera view, followed by comparison against
this known pre-handoff baseline. No additional Linux boot has yet occurred
at the time of this capture note.


## C5 repeat: runtime mapping resolved

[The 14:24 unchanged repeat](C5-REPEAT-SESSION-2026-10-09.md) is complete.
Cver payload +16 gives 0x184000 for first C5 and 0xc0c000 for the repeat.
All ten addresses normalize to the same sequence; all nine noninitial
frames land on call instructions in matched __TEXT. IOVA 0 in the ADT is
not the runtime code base. The earlier zero-slide disassembly is superseded.
Crg8 serialization and asynchronous fault-address translation remain open;
see the updated plan. No further unchanged repeat is needed.
