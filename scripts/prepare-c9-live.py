#!/usr/bin/env python3
"""Prepare the E5 live ANS handoff in a disposable C9 source copy."""
import argparse
import difflib
from pathlib import Path


def prepare(root):
    root = root.resolve()
    if not root.parent.name.startswith("C9-PREP-") or (root / ".git").exists():
        raise ValueError("Use a disposable C9-PREP-* source copy")
    changes = {}

    def edit(name, old, new):
        path = root / "src" / name
        original, text = changes.get(name, (path.read_text(), path.read_text()))
        if text.count(old) != 1:
            raise ValueError(f"Expected one source match in {name}: {old[:80]}")
        changes[name] = (original, text.replace(old, new))

    edit("nvme.h", "void nvme_shutdown(void);", """void nvme_shutdown(void);
bool nvme_c9_live_handoff(void);
bool nvme_c9_live_armed(void);""")
    edit("nvme.c", "void nvme_shutdown(void)\n{", """/* E5: retain the stopped controller's allocations and a running IOP.
 * No buffers, SART slots, CPU state or PMGR state are released/reset.
 * The prepared FDT reserves every current MAP/QUEUE allocation.
 */
static bool c9_live_attempted, c9_live_armed;

bool nvme_c9_live_armed(void) { return c9_live_armed; }

bool nvme_c9_live_handoff(void)
{
    if (c9_live_attempted || !nvme_initialized || !nvme_asc || !nvme_rtkit)
        return false;
    c9_live_attempted = true;
    struct nvme_command cmd = {0};
    cmd.opcode = NVME_ADMIN_CMD_DELETE_SQ;
    cmd.cdw10 = 1;
    if (!c9_delete(&cmd))
        return false;
    cmd.opcode = NVME_ADMIN_CMD_DELETE_CQ;
    if (!c9_delete(&cmd) || !c9_ctrl_shutdown() || !c9_ctrl_disable())
        return false;
    /* Unlike sleep, quiesce leaves the ASC CPU running. Both ACKs are
     * captured by the existing trace; the Boolean is checked directly. */
    if (!rtkit_quiesce(nvme_rtkit) || !asc_cpu_running(nvme_asc) ||
        read32(nvme_base + NVME_BOOT_STATUS) != NVME_BOOT_STATUS_OK ||
        (read32(nvme_base + NVME_CC) & NVME_CC_EN) ||
        (read32(nvme_base + NVME_CSTS) & NVME_CSTS_RDY))
        return false;
    c9_live_armed = true;
    c9_diag_snapshot(30);
    c9_diag_event(C9_LIVE_ARM, 1, read32(nvme_base + NVME_CC),
                  read32(nvme_base + NVME_CSTS),
                  read32(nvme_base + NVME_BOOT_STATUS), 0);
    return true;
}

void nvme_shutdown(void)
{
    if (c9_live_armed) {
        if (!asc_cpu_running(nvme_asc) ||
            read32(nvme_base + NVME_BOOT_STATUS) != NVME_BOOT_STATUS_OK)
            panic("E5: retained ANS stopped before kernel handoff\\n");
        printf("E5: retain live ANS, buffers and SART mappings\\n");
        return;
    }""")
    edit("proxy.c", "        case P_NVME_INIT:", """        case 0xf05: /* One-shot E5 controller quiesce / live retention */
            reply->retval = nvme_c9_live_handoff();
            break;
        case P_NVME_INIT:""")
    edit("c9diag.h", "C9_MAP, C9_UNMAP, C9_QUEUE, C9_SART_TRACK,", """C9_MAP, C9_UNMAP, C9_QUEUE, C9_SART_TRACK,
    C9_LIVE_ARM = 24, C9_LIVE_RESERVE,""")
    edit("c9diag.h", "u64 c9_diag_get(u64 selector, u64 phase);", """int c9_diag_reserve_live(void *fdt);
u64 c9_diag_get(u64 selector, u64 phase);""")
    edit("c9diag.c", '#include "utils.h"', '#include "utils.h"\n#include "nvme.h"\n#include "libfdt/libfdt.h"')
    edit("c9diag.c", '"C9-LOCAL"', '"C9-LOCAL-E5"')
    edit("c9diag.c", "u64 c9_diag_get(u64 selector, u64 phase)", """int c9_diag_reserve_live(void *fdt)
{
    if (!nvme_c9_live_armed())
        return 0;
    if (store.event_dropped || store.snapshot_dropped)
        return -1;
    u32 begin = 0, maps = 0, queues = 0, end = store.events;
    for (u32 i = 0; i < end; i++)
        if (store.event[i].kind == C9_INIT_BEGIN)
            begin = i;
    for (u32 i = begin; i < end; i++) {
        struct c9_event *e = &store.event[i];
        if (e->kind != C9_MAP && e->kind != C9_QUEUE)
            continue;
        if (!e->a || !e->b || (e->a & 0x3fff) || e->b > 0x8000)
            return -1;
        if (e->kind == C9_MAP) {
            if (e->result != 1 || e->a != e->c)
                return -1;
            maps++;
        } else {
            queues++;
        }
        u64 size = (e->b + 0x3fff) & ~0x3fffUL;
        if (fdt_add_mem_rsv(fdt, e->a, size))
            return -1;
        c9_diag_event(C9_LIVE_RESERVE, 1, e->a, size, e->kind, 0);
    }
    return maps == 3 && queues == 6 ? 0 : -1;
}

u64 c9_diag_get(u64 selector, u64 phase)""")
    include = '#include "nvme.h"' if '#include "nvme.h"' in (root / "src/kboot.c").read_text() else '#include "adt.h"'
    edit("kboot.c", include, include + '\n#include "c9diag.h"')
    edit("kboot.c", "    if (fdt_pack(dt))", """    if (c9_diag_reserve_live(dt))
        bail("E5: could not reserve retained ANS allocations\\n");

    if (fdt_pack(dt))""")
    patch = "".join("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
        fromfile=f"a/src/{name}", tofile=f"b/src/{name}")) for name, (old, new) in changes.items())
    (root.parent / "live-from-local.patch").write_text(patch)
    for name, (_, new) in changes.items():
        (root / "src" / name).write_text(new)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source)
