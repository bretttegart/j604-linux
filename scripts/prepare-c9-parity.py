#!/usr/bin/env python3
"""Prepare the grouped Linux parity screen in a disposable C8 kernel copy."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one exact source match: {old[:90]}")
    return text.replace(old, new)


def prepare(root):
    root = root.resolve()
    if not root.parent.name.startswith("C9-PARITY-") or root.name != "kernel-src":
        raise ValueError("Use a disposable C9-PARITY-*/kernel-src copy")
    changes = {}
    for name in ("drivers/nvme/host/apple.c", "drivers/soc/apple/rtkit.c", "drivers/soc/apple/rtkit-internal.h"):
        changes[name] = [(root / name).read_text(), None]
    name = "drivers/nvme/host/apple.c"
    text = changes[name][0]
    start = text.index("\t} else if (anv->hw->needs_ioq_register &&")
    end = text.index('\n\tdev_err(anv->dev,\n\t\t"ANSCHK post', start)
    text = text[:start] + '''\t} else {
\t\tdev_err(anv->dev, "ANSBR 3\\n");
\t\tret = apple_rtkit_wake(anv->rtk);
\t}
''' + text[end:]
    start = text.index("\t/*\n\t * m1n1 clears CC.EN")
    end = text.index("\t/* Setup the admin queue */", start)
    changes[name][1] = text[:start] + text[end:]
    name = "drivers/soc/apple/rtkit.c"
    text = changes[name][0]
    text = replace(text, "\t/* Advertised by newer firmware and required to complete RTKit boot. */\n\tAPPLE_RTKIT_EP_UNKNOWN7 = 7,\n", "")
    text = replace(text, "\t\tcase APPLE_RTKIT_EP_UNKNOWN7:\n", "")
    text = replace(text, "#define APPLE_RTKIT_SYSTEM7_BUFFER_REPLY 5\n\n", "")
    text = replace(text, "\t\t\t\t\t   ep == APPLE_RTKIT_EP_UNKNOWN7 ?\n\t\t\t\t\t   APPLE_RTKIT_SYSTEM7_BUFFER_REPLY :\n", "")
    start = text.index("static void apple_rtkit_system7_rx(")
    end = text.index("static void apple_rtkit_syslog_rx_init(", start)
    text = text[:start] + text[end:]
    text = replace(text, "\tcase APPLE_RTKIT_EP_UNKNOWN7:\n\t\tapple_rtkit_system7_rx(rtk, rtk_work->msg);\n\t\tbreak;\n", "")
    old = "\tapple_rtkit_free_buffer(rtk, &rtk->system7_buffer);\n"
    if text.count(old) != 2:
        raise ValueError("Expected reinit and free EP7 release sites")
    text = text.replace(old, "")
    changes[name][1] = text
    name = "drivers/soc/apple/rtkit-internal.h"
    changes[name][1] = replace(changes[name][0], "\tstruct apple_rtkit_shmem system7_buffer;\n", "")
    patch = "".join("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
        fromfile=f"a/{name}", tofile=f"b/{name}")) for name, (old, new) in changes.items())
    for name, (_, new) in changes.items():
        if "system7" in new or "UNKNOWN7" in new or "SYSTEM7" in new:
            raise ValueError(f"EP7 code remains in {name}")
    (root.parent / "c8-to-parity.patch").write_text(patch)
    hashes = {name: {"before": hashlib.sha256(old.encode()).hexdigest(),
                     "after": hashlib.sha256(new.encode()).hexdigest()} for name, (old, new) in changes.items()}
    (root.parent / "source-changes.json").write_text(json.dumps(hashes, indent=2) + "\n")
    for name, (_, new) in changes.items():
        (root / name).write_text(new)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source)
