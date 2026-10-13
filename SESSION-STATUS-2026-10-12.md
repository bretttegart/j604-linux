# Stopped session status — 2026-10-12

**Work stopped at the user's request after C12 bootlooped.** The current
LabOS boot object is the failing C12 padded proxy. Restoration after C12
has not been performed. No further Mac tests are running.

| Case | Result | What it establishes |
|---|---|---|
| E5 retained live ANS handoff | Linux sleep FAIL | A verified m1n1 restart plus retained buffers/mappings is insufficient to rescue Linux sleep. Linux renegotiates RTKit; an unchanged session was not transferred. |
| C10 embedded image through USB proxy | Shell PASS; initial reads 5/5 | Linux, keyboard and warm read-only NVMe access work on that path. |
| C10 installed embedded image | Apple-logo bootloop | Installed boot fails; no Linux/ANS fault context captured. |
| Preserved standalone proxy restore | PASS, operator + USB | The smaller `dfdb3bfa…` image boots from LabOS and responds. |
| C11 pause through USB proxy | Hold and shell PASS | Complete appended payload matches byte-for-byte before host resume. Four old block hashes match; the changed boot-log block repeats consistently. |
| C11 installed pause image | Bootloop; no m1n1/C11 text | The intended pre-payload checkpoint is not observed. Exact failure stage remains unknown. |
| C12 exact preserved proxy padded to C11 size | Bootloop, operator report | A larger installed image/loading/layout change reproduces failure without Linux or the diagnostic executable changes. No exact size limit or firmware cause is established. |

The historical LBA 4096 reference contains dated Boot Picker log text inside
`iBootSystemContainer`. Three subsequent O_DIRECT checks return identical
current hashes, while four other blocks match their historical references.
The old checker still correctly reports historical comparison 4/5; no new
reference hash was adopted and no current 5/5 PASS is claimed.

Read [C12's findings and recovery instructions](C12-SIZE-SESSION-2026-10-12.md)
before restarting work. Restore the known smaller proxy as the first physical
step on resumption. Its image SHA-256 is
`dfdb3bfa56e7f5266f0e4c3c1fa27a61c03d2ec921e7771ae1aabaf7dce23dfd`.
The local package server remains available for that recovery; no restoration
is being attempted as part of the stop-and-document request.

Artifacts remain under `/home/btega/j604-boot/ans-review-n6miVhGq/`, especially
`C9-PREP-E5-20261012`, `C10-EMBED-20261012`, `C11-PAUSE-20261012`, and
`C12-SIZE-20261012`. Raw firmware, videos, disk blocks, payload binaries and
large build trees are kept locally, outside Git. The repository contains
source changes, manifests, result records, evidence hashes and session notes.

Two questions remain separate: the large installed-image boot failure and
Linux's ANS sleep/restart failure. Neither is fixed. A persistent Linux root
filesystem, graphical desktop and broader laptop support remain future work.
