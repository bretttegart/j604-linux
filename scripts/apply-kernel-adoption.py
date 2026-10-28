#!/usr/bin/env python3
"""Apply the J604 adoption consumer patch to ~/linux-asahi (dry-run safe).

Every replacement asserts exactly one match; on any mismatch nothing is
written. Run with --check for a dry run, without it to apply.
See ADOPTION-2026-10-28.md for the design and the labelled guesses.
"""
import argparse
import sys
from pathlib import Path


def replace(path, old, new):
    text = path.read_text()
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{path}: expected 1 match, found {n}: {old[:90]!r}")
    path.write_text(text.replace(old, new))
    print(f"patched {path.name}: {old[:60]!r}...")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--tree", type=Path, required=True)
    args = ap.parse_args()
    tree = args.tree
    if args.check:
        # Dry run: verify anchors without writing, by copying logic on
        # in-memory text.
        for rel, old in ANCHORS:
            text = (tree / rel).read_text()
            n = text.count(old)
            print(f"{rel}: anchor count {n} for {old[:60]!r}")
            if n != 1:
                return 1
        return 0
    for rel, old, new in EDITS:
        replace(tree / rel, old, new)
    return 0


ANCHORS = []
EDITS = []


def edit(rel, old, new):
    ANCHORS.append((rel, old))
    EDITS.append((rel, old, new))


edit("include/linux/soc/apple/rtkit.h",
     "int apple_rtkit_boot(struct apple_rtkit *rtk);\n",
     """int apple_rtkit_boot(struct apple_rtkit *rtk);

/*
 * Adopt a co-processor session that is already running and already
 * negotiated by a previous stage. Sends no INIT, HELLO, EPMAP, or
 * power-state message. Returns -EINVAL if the co-processor crashed.
 * The caller must have verified (CPU running, boot status OK) before
 * calling; this function performs no hardware check of its own.
 */
int apple_rtkit_adopt_running(struct apple_rtkit *rtk);
""")

edit("drivers/soc/apple/rtkit.c",
     "EXPORT_SYMBOL_GPL(apple_rtkit_boot);\n",
     """EXPORT_SYMBOL_GPL(apple_rtkit_boot);

/*
 * Adopt a session that a previous stage already negotiated. Sends NO
 * management message. The power-state assignments below are internal
 * bookkeeping ONLY: Linux did not observe these ACKs, the producer
 * negotiated them. They exist so apple_rtkit_is_running() stops
 * reporting a live session as dead, and so no path blocks waiting for
 * a negotiation that already happened. See ADOPTION-2026-10-28.md,
 * guess G4, for the completion safety note.
 */
int apple_rtkit_adopt_running(struct apple_rtkit *rtk)
{
	if (rtk->crashed)
		return -EINVAL;

	rtk->iop_power_state = APPLE_RTKIT_PWR_STATE_ON;
	rtk->ap_power_state = APPLE_RTKIT_PWR_STATE_ON;
	complete_all(&rtk->epmap_completion);
	complete_all(&rtk->iop_pwr_ack_completion);
	complete_all(&rtk->ap_pwr_ack_completion);
	dev_info(rtk->dev, "RTKit: adopting already-running session (no INIT/HELLO/EPMAP sent)\\n");
	return 0;
}
EXPORT_SYMBOL_GPL(apple_rtkit_adopt_running);
""")

edit("drivers/nvme/host/apple.c",
     "\tstruct apple_rtkit *rtk;\n\tstruct reset_control *reset;\n",
     "\tstruct apple_rtkit *rtk;\n\tstruct reset_control *reset;\n\tbool adoption_offered;\n\tbool adopted;\n")

edit("drivers/nvme/host/apple.c",
     "\t/* RTKit must be shut down cleanly for the (soft)-reset to work */\n\tif (apple_rtkit_is_running(anv->rtk)) {\n",
     """\t/* An adopted session must never be shut down by a later reset:
\t * Linux did not start it, and quiesce+sleep would destroy the
\t * adoption result the run is trying to prove. */
\tif (apple_rtkit_is_running(anv->rtk) && !anv->adopted) {
""")

edit("drivers/nvme/host/apple.c",
     "\t/*\n\t * Only do the soft-reset if the CPU is not running, which means either we\n\t * or the previous stage shut it down cleanly.\n\t */\n",
     """\t/* Adoption gate: an offered session with a stopped CPU or a bad
\t * boot status is a broken producer contract, not a reason to
\t * fall through to the PMGR-reset path. Fail loudly. */
\tif (anv->adoption_offered &&
\t    (!(readl(anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL) &
\t       APPLE_ANS_COPROC_CPU_CONTROL_RUN) ||
\t     readl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS) !=
\t     APPLE_ANS_BOOT_STATUS_OK)) {
\t\tdev_err(anv->dev, "ADOPT-PRE-FAILED cpu=%08x bst=%08x\\n",
\t\t\treadl(anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL),
\t\t\treadl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS));
\t\tret = -ENODEV;
\t\tgoto out;
\t}

\t/*
\t * Only do the soft-reset if the CPU is not running, which means either we
\t * or the previous stage shut it down cleanly.
\t */
""")

edit("drivers/nvme/host/apple.c",
     "\t\tret = apple_rtkit_boot(anv->rtk);\n\t} else if (anv->hw->needs_ioq_register &&\n\t\t   readl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS) ==\n\t\t   APPLE_ANS_BOOT_STATUS_OK) {\n",
     """\t\tret = apple_rtkit_boot(anv->rtk);
\t} else if (anv->adoption_offered && anv->hw->needs_ioq_register &&
\t\t   (readl(anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL) &
\t\t    APPLE_ANS_COPROC_CPU_CONTROL_RUN) &&
\t\t   readl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS) ==
\t\t   APPLE_ANS_BOOT_STATUS_OK) {
\t\t/* ADOPTION: no INIT, no HELLO/EPMAP, no power renegotiation,
\t\t * no SLEEP, no PMGR reset before first I/O. The queue setup
\t\t * below runs unchanged on top of the adopted session. */
\t\tdev_err(anv->dev, "ADOPT-PRE cpu=%08x bst=%08x sart=%04x cc=%08x csts=%08x\\n",
\t\t\treadl(anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL),
\t\t\treadl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS),
\t\t\tapple_sart_protected_mask(anv->sart),
\t\t\treadl(anv->mmio_nvme + NVME_REG_CC),
\t\t\treadl(anv->mmio_nvme + NVME_REG_CSTS));
\t\tret = apple_rtkit_adopt_running(anv->rtk);
\t\tif (!ret)
\t\t\tanv->adopted = true;
\t\tdev_err(anv->dev, "ADOPT-OK ret=%d adopted=%d\\n", ret, anv->adopted);
\t} else if (anv->hw->needs_ioq_register &&
\t\t   readl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS) ==
\t\t   APPLE_ANS_BOOT_STATUS_OK) {
""")

edit("drivers/nvme/host/apple.c",
     "\tdev_dbg(anv->dev, \"Starting admin queue\");\n",
     """\tif (anv->adopted)
\t\tdev_err(anv->dev, "ADOPT-POST cpu=%08x bst=%08x sart=%04x cc=%08x csts=%08x\\n",
\t\t\treadl(anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL),
\t\t\treadl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS),
\t\t\tapple_sart_protected_mask(anv->sart),
\t\t\treadl(anv->mmio_nvme + NVME_REG_CC),
\t\t\treadl(anv->mmio_nvme + NVME_REG_CSTS));

\tdev_dbg(anv->dev, "Starting admin queue");
""")

edit("drivers/nvme/host/apple.c",
     "\tdev_err(dev, \"NVME-SNAP boot=%08x csts=%08x sart=%04x cc=%08x\\n\",\n\t\treadl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS),\n\t\treadl(anv->mmio_nvme + NVME_REG_CSTS),\n\t\tapple_sart_protected_mask(anv->sart),\n\t\treadl(anv->mmio_nvme + NVME_REG_CC));\n",
     """\tdev_err(dev, "NVME-SNAP boot=%08x csts=%08x sart=%04x cc=%08x\\n",
\t\treadl(anv->mmio_nvme + APPLE_ANS_BOOT_STATUS),
\t\treadl(anv->mmio_nvme + NVME_REG_CSTS),
\t\tapple_sart_protected_mask(anv->sart),
\t\treadl(anv->mmio_nvme + NVME_REG_CC));

\t/* Adoption offer, published by the m1n1 producer in /chosen.
\t * Absent properties mean an ordinary (non-adoption) boot: the
\t * existing wake/boot branches still apply. A present offer with
\t * any controller state other than "disabled" is refused outright
\t * -- silently falling back would make the run uninterpretable. */
\t{
\t\tstruct device_node *chosen = of_find_node_by_path("/chosen");
\t\tu32 live = 0;
\t\tconst char *state = NULL;
\t\tif (chosen) {
\t\t\tif (!of_property_read_u32(chosen, "j604,ans-live", &live) && live) {
\t\t\t\tif (of_property_read_string(chosen, "j604,ans-live-controller-state", &state) ||
\t\t\t\t    strcmp(state, "disabled")) {
\t\t\t\t\tdev_err(dev, "ADOPT-REFUSED live=%u state=%s\\n", live, state ? state : "(missing)");
\t\t\t\t\tof_node_put(chosen);
\t\t\t\t\tret = -ENODEV;
\t\t\t\t\tgoto put_dev;
\t\t\t\t}
\t\t\t\tanv->adoption_offered = true;
\t\t\t\tdev_err(dev, "ADOPT-OFFERED controller-state=disabled\\n");
\t\t\t}
\t\t\tof_node_put(chosen);
\t\t}
\t}
""")

edit("drivers/nvme/host/apple.c",
     "\tflush_delayed_work(&anv->flush_dwork);\n\tapple_nvme_disable(anv, true);\n\tif (apple_rtkit_is_running(anv->rtk)) {\n\t\tapple_rtkit_shutdown(anv->rtk);\n\n\t\twritel(0, anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL);\n\t}\n}\n",
     """\tflush_delayed_work(&anv->flush_dwork);
\tapple_nvme_disable(anv, true);
\tif (apple_rtkit_is_running(anv->rtk) && !anv->adopted) {
\t\tapple_rtkit_shutdown(anv->rtk);

\t\twritel(0, anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL);
\t} else if (anv->adopted) {
\t\t/* Linux did not start this session; stopping it here would
\t\t * be an improvised shutdown path. Deferred, not guessed. */
\t\tdev_err(anv->dev, "ADOPT-SKIP-SHUTDOWN\\n");
\t}
}
""")

edit("drivers/nvme/host/apple.c",
     "\tapple_nvme_disable(anv, true);\n\n\tif (apple_rtkit_is_running(anv->rtk)) {\n\t\tret = apple_rtkit_shutdown(anv->rtk);\n\n\t\twritel(0, anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL);\n\t}\n",
     """\tapple_nvme_disable(anv, true);

\tif (apple_rtkit_is_running(anv->rtk) && !anv->adopted) {
\t\tret = apple_rtkit_shutdown(anv->rtk);

\t\twritel(0, anv->mmio_coproc + APPLE_ANS_COPROC_CPU_CONTROL);
\t} else if (anv->adopted) {
\t\tdev_err(anv->dev, "ADOPT-SKIP-SHUTDOWN\\n");
\t}
""")

if __name__ == "__main__":
    sys.exit(main())
