#!/usr/bin/env python3
"""Add a bounded ANS buffer-retention experiment to a disposable C9 local copy."""
import argparse
import difflib
from pathlib import Path


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one exact source match: {old[:80]}")
    return text.replace(old, new)


HOLD = '''/* One-shot experiment: retain at most three ANS heap buffers / 64 KiB.
 * The caller has already removed the normal SART mapping. No power, mailbox,
 * reset or allocation sequence is changed; retained allocations die at reboot.
 */
static bool hold_armed, hold_used;
static u32 hold_count;
static u64 hold_bytes;

bool c9_diag_hold_buffer(void *pointer, u64 bytes)
{
    if (!hold_armed || hold_count >= 3 || !pointer || ((u64)pointer & 0x3fff) ||
        (bytes != 0x4000 && bytes != 0x8000) || bytes > 0x10000 - hold_bytes)
        return false;
    hold_bytes += bytes;
    c9_diag_event(C9_HOLD, 1, (u64)pointer, bytes, hold_count++, hold_bytes);
    if (hold_count == 3)
        hold_armed = false;
    return true;
}

'''


def prepare(root):
    root = root.resolve()
    if not root.parent.name.startswith("C9-PREP-") or (root / ".git").exists():
        raise ValueError("Use a disposable source copy under C9-PREP-*, without .git")
    changes = {}
    for name in ("rtkit.c", "c9diag.c", "c9diag.h"):
        changes[name] = [ (root / "src" / name).read_text(), None ]
    old = changes["rtkit.c"][0]
    start = old.index("bool rtkit_free_buffer(")
    end = old.index("static bool rtkit_handle_buffer_request", start)
    function = replace(old[start:end], "    free(bfr->bfr);",
        '''    if (strcmp(rtk->name, "nvme") || !c9_diag_hold_buffer(bfr->bfr, bfr->sz))
        free(bfr->bfr);''')
    changes["rtkit.c"][1] = old[:start] + function + old[end:]
    text = replace(changes["c9diag.h"][0], "C9_MAP, C9_UNMAP, C9_QUEUE, C9_SART_TRACK,",
                   "C9_MAP, C9_UNMAP, C9_QUEUE, C9_SART_TRACK, C9_HOLD, C9_HOLD_ARM,")
    changes["c9diag.h"][1] = replace(text, "u64 c9_diag_get(u64 selector, u64 phase);",
        "bool c9_diag_hold_buffer(void *pointer, u64 bytes);\nu64 c9_diag_get(u64 selector, u64 phase);")
    text = replace(changes["c9diag.c"][0], '"C9-LOCAL"', '"C9-LOCAL-R"')
    text = replace(text, "/* C9 observations only: no power/reset/ANS register writes, no hook printf. */",
        "/* C9 address-change experiment: bounded heap retention; no power/reset changes. */")
    text = replace(text, "u64 c9_diag_get(u64 selector, u64 phase)\n", HOLD + "u64 c9_diag_get(u64 selector, u64 phase)\n")
    text = replace(text, "    if (selector == 2) {", '''    if (selector == 3) {
        if (hold_used)
            return 0;
        hold_used = hold_armed = true;
        c9_diag_event(C9_HOLD_ARM, 1, 0, 0, 0, 0);
        return 1;
    }
    if (selector == 2) {''')
    changes["c9diag.c"][1] = text
    patch = "".join("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
        fromfile=f"a/src/{name}", tofile=f"b/src/{name}")) for name, (old, new) in changes.items())
    (root.parent / "relocate-from-local.patch").write_text(patch)
    for name, (_, new) in changes.items():
        (root / "src" / name).write_text(new)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source)
