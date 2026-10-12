# C9 proxy restart session — Oct 12, 2026

**U and F both PASS.** Each image initialized ANS, read five known blocks,
shut down/reset/released ANS, initialized it again, and reread identical
data. These are m1n1 proxy tests; untethered Linux remains unresolved.

The owner authorized preparation and execution, then restarted into a fresh
LabOS proxy between U and F. No Linux payload, camera/pager boot, SSD write
test, installed bootloader replacement, ESP copy, re-bless or firmware restore
occurred. The Mac was left at the temporary local C9 proxy with ANS running.
Return to a fresh LabOS proxy before the next independent cell.

## Artifacts and preparation

Directory: `/home/btega/j604-boot/ans-review-n6miVhGq/C9-PREP-20261012/`.

| Cell | Source lineage | Raw binary bytes | SHA-256 | Hardware result |
|---|---|---:|---|---|
| U | Asahi m1n1 `57a9339ffd1876e78297b17d34dece8cff8fa1ba` + C9 observations | 3997696 | `b6ea26213fcf7171aee8108efd629483daad2f4f35de1de888b284cc038b47a9` | PASS, finished 11:21:56 MDT |
| F | Preserved SHUT-AUDIT source tree, Git base `9e24b8751bd5064c5d37ec1bbbae6ee85caabbfd` with its existing changes + C9 observations | 3932160 | `8497c947355557e4dacbc9bc70226ec68894424f6a65b3e2214e3d977165fbcf` | PASS, finished 11:25:31 MDT |

Source copies are `upstream-src/` and `local-src/`. The original trees and
historical C7/C8 artifacts were preserved. The upstream archive is retained.
Full source hashes, diagnostic diffs, build logs and manifests are in the
preparation directory. F's USB build label is `C9-F-9e24b875-diag1`;
U's is `C9-U-57a9339f-diag1`. The diagnostic store carries distinct
`C9-UPSTREAM` / `C9-LOCAL` identities checked before any NVMe command.

Both builds use `USE_CLANG=1 CHAINLOADING=1 EXTRA_CFLAGS=-DNO_DISPLAY` and
the Rust 1.99 wcslen optimizer workaround
`RUSTFLAGS='-C llvm-args=-disable-loop-idiom-wcslen'`. The upstream Makefile
also contains that workaround. Images contain no kernel/DTB/initramfs or
chainload filename. They were each sent once using `chainload.py -n -r`;
both loaders returned zero and reported the proxy alive.

These are **observed upstream/local builds**, not untouched binaries. C9
adds bounded data records and read-only SART snapshots. Reset/power requests,
operation order, original return values and F's historical init-error cleanup
are preserved. Capturing data can affect timing; this session does not claim
equivalence to an uninstrumented restart. No delay sweep was performed.
The audit's 20-second hold is in `chainload_load`, which these direct proxy
cells do not call; no FAT/stage2 load occurred in either cell.

## Capture and validation

The capture store has a fixed ABI: 1024 48-byte events, 32 288-byte SART
snapshots, a 64-byte header, total 58432 bytes. Each valid snapshot preserves
all 16 CONFIG/PADDR/SIZE entries plus a second CONFIG read to identify
unstable entries. Mailbox events are filtered by the ADT-identified ANS ASC
base, so MTP ACKs cannot enter this trace. No allocations/prints are added
to those mailbox hooks. Unsupported or failed-reset snapshots are explicitly
unavailable rather than forced MMIO reads.

The C capture code passed native AddressSanitizer/UndefinedBehaviorSanitizer
checks covering ABI, full words, bounds, overflow, immutable earlier records,
unstable configuration, device filtering and raw export. The host decoder
passed 16 checks including malformed/truncated stores and rejection of
missing/stale sleep ACKs. Both target builds linked successfully. Host checks
are in `native-check/`; synthetic data was never sent to the Mac.

[`run-c9-restart.py`](scripts/run-c9-restart.py) imports proxy definitions
directly, without `m1n1.setup`. It validates live ADT and capture identity,
allocates an aligned DRAM buffer, fills a per-read sentinel, issues namespace-1
reads at LBAs 0, 1, 2, 128 and 4096, and saves actual readbacks and hashes.
LBA 1 contains `EFI PART` and reports sufficient disk bounds. It saves the
complete store before/after phases and has per-command host deadlines.
There are no NVMe write or flush calls. It performs one shutdown and one
second initialization, requiring a non-no-op init and matching read hashes.

Fresh preflight captures verified Mac16,1 / J604 / board 0x22 / T8132,
SARTv3 at `0x485c50000`, and the same ANS manifest hash in both sessions.
The console reports OS FW 26.7 and system FW 27.0. These labels describe
the currently booted LabOS environment; do not substitute earlier running
macOS 26.6.2 facts for the actual preflight.

The Oct 12 captured ANS manifest is byte-identical to the Oct 9 capture.
Live `__TEXT` differs from Oct 9 at two bytes (`0x4225`, `0x4226`); its
SHA-256 also differs between the two fresh C9 sessions. The cause of these
live-byte differences has not been established. They are recorded rather
than interpreted as an image-family change. No C9 firmware intervention
occurred. See `preflight/provenance-comparison.json` and both capture JSONs.

## Results

Machine-readable summary: [C9 restart results](C9-RESTART-RESULTS-2026-10-12.json).
Primary host evidence is in `U-RUN/` and `F-RUN/`, with loader/run transcripts
beside them. Each directory retains raw stores and decoded JSON at preflight,
before-init, first-init, first-reads, shutdown, second-init and second-reads.
Raw disk blocks remain in the local run directories; only their hashes are
included in the repository summary.

| Observation | U | F |
|---|---:|---:|
| First init + five controller reads | PASS | PASS |
| Delete SQ/CQ, controller shutdown and disable | Confirmed | Confirmed |
| Actual AP QUIESCED and IOP SLEEP ACKs | Captured | Captured |
| Sleep switch Boolean result / cached states | `1 / 0x10 / 0x01` | `1 / 0x10 / 0x01` |
| CPU RUN after stop | Clear (`0`) | Clear (`0`) |
| Resolved PMGR reset `ANS` / `ANS2` | `0 / -1` | `0 / -1` |
| Second init + same five hashes | PASS | PASS |
| Trace events / dropped | `376 / 0` | `394 / 0` |
| SART snapshots / dropped | `15 / 0` | `15 / 0` |
| Crash events | `0` | `0` |

`ANS` is the resolved PMGR device in this ADT. `ANS2 == -1` does not mean
the actual reset failed. Its snapshot has status 2 (unavailable), not a
fabricated empty table. PMGR records identify device id `0x94` at
`0x380700538`, with raw state `0x0f0020ff` before and after reset in both
cells. This agrees with Linux's `ps_ans` offset `0x538`; that correspondence
alone does not establish identical runtime reset sequencing.

Both cells captured protected mask `0x5f` (slots 0–4 and 6). The full SART
table is unchanged from post-sleep/CPU-stop to post-resolved-reset. RTKit
release subsequently removes slots **5, 7 and 8**, preserving every protected
entry. The second probe sees the same protected table, and the second boot
adds its RTKit buffers again. All valid snapshots are stable. The fixed
block hashes also agree across U and F, not only across each cell's restart.

## Interpretation and next discriminator

These two passes establish that the measured upstream and local proxy
paths can restart ANS on this J604 with the captured firmware provenance.
They provide no evidence that reset erased SART entries in those paths,
or that the local fork cannot perform a normal successful restart.
They do not establish that every firmware state, uninstrumented path or
Linux cold-start sequence works.

The next useful distinction is **L0/L1** from the
[C9 matrix](C9-REVIEW-2026-10-12.md): matched Linux RAM preload, first with
no m1n1 NVMe use, then with one m1n1 read/shutdown cycle and direct handoff,
without a second m1n1 init. That separates prior storage use from FAT/stage2
loading and relocation. If L1 fails, compare Linux's reset/SART/buffer
chronology with these successful m1n1 captures. If L1 passes while the
existing chain boot fails, inspect the chain-specific state differences.

Linux cells need a demonstrated reporting route before execution:
`console=tty0` and m1n1 USB teardown do not produce kernel logs over this
proxy. Further camera/pager diagnostic boots remain parked. No Linux
payload or parity experiment has been sent in C9.
