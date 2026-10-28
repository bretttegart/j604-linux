#!/usr/bin/env python3
"""Prepare the J604 live-session adoption producer in a disposable C9 copy.

Precondition: the copy already carries the C9 instrumentation (run
scripts/prepare-c9-m1n1.py first, and use its LOCAL copy). This script
adds ONLY the adoption producer on top; it never touches a live tree.

Adoption vs E5, in code: E5's handoff called rtkit_quiesce() (AP and IOP
to QUIESCED 0x10) and then let Linux renegotiate INIT/HELLO. This handoff
calls no quiesce, no sleep, no PMGR reset, and no free: the ASC CPU must
be RUNNING with IOP and AP power ON at arm time, or adoption is refused.

Usage: python3 prepare-adoption.py <disposable-C9-PREP-*-local-copy>
Writes diagnostics/m1n1-adoption.patch next to the copy's parent dir
(the same convention as prepare-c9-live.py).
"""
import argparse
import difflib
from pathlib import Path


def prepare(root):
    root = root.resolve()
    if not root.parent.name.startswith("C9-PREP-") or (root / ".git").exists():
        raise ValueError("Use a disposable C9-PREP-* source copy")
    if not (root / "src/c9diag.c").exists():
        raise ValueError("Copy lacks C9 instrumentation; run prepare-c9-m1n1.py first")
    changes = {}

    def edit(name, old, new):
        path = root / "src" / name
        original, text = changes.get(name, (path.read_text(), path.read_text()))
        if text.count(old) != 1:
            raise ValueError(f"Expected one source match in {name}: {old[:80]!r}")
        changes[name] = (original, text.replace(old, new))

    edit("nvme.h", "void nvme_shutdown(void);", """void nvme_shutdown(void);
bool nvme_adopt_handoff(void);
bool nvme_adopt_armed(void);""")

    edit("rtkit.h", "bool rtkit_quiesce(rtkit_dev_t *rtk);", """bool rtkit_quiesce(rtkit_dev_t *rtk);
bool rtkit_is_power_on(rtkit_dev_t *rtk);""")

    edit("rtkit.c", "bool rtkit_quiesce(rtkit_dev_t *rtk)", """/* Adoption gate: RUNNING means IOP and AP power are both ON. A QUIESCED
 * session (0x10, E5's state) is NOT running and must refuse adoption. */
bool rtkit_is_power_on(rtkit_dev_t *rtk)
{
    return rtk->iop_power == RTKIT_POWER_ON &&
           rtk->ap_power == RTKIT_POWER_ON;
}

bool rtkit_quiesce(rtkit_dev_t *rtk)""")

    edit("nvme.c", "void nvme_shutdown(void)\n{", """/* ADOPTION (Option A): retain a RUNNING controller-disabled session.
 * Deletes SQ/CQ and disables the controller, exactly as E5 did, but
 * sends NO quiesce, NO sleep, NO PMGR reset, and frees NOTHING. The
 * prepared FDT reserves every current MAP/QUEUE allocation and publishes
 * the /chosen adoption properties (see c9_diag_reserve_adopt).
 */
static bool adopt_attempted, adopt_armed;

bool nvme_adopt_armed(void) { return adopt_armed; }

bool nvme_adopt_handoff(void)
{
    if (adopt_attempted || !nvme_initialized || !nvme_asc || !nvme_rtkit)
        return false;
    adopt_attempted = true;
    struct nvme_command cmd = {0};
    cmd.opcode = NVME_ADMIN_CMD_DELETE_SQ;
    cmd.cdw10 = 1;
    if (!c9_delete(&cmd))
        return false;
    cmd.opcode = NVME_ADMIN_CMD_DELETE_CQ;
    if (!c9_delete(&cmd) || !c9_ctrl_shutdown() || !c9_ctrl_disable())
        return false;
    /* Unlike E5, do NOT quiesce: adoption requires a running session.
     * rtkit_is_power_on() is false for QUIESCED, SLEEP, and OFF alike. */
    if (!asc_cpu_running(nvme_asc) || !rtkit_is_power_on(nvme_rtkit) ||
        read32(nvme_base + NVME_BOOT_STATUS) != NVME_BOOT_STATUS_OK ||
        (read32(nvme_base + NVME_CC) & NVME_CC_EN) ||
        (read32(nvme_base + NVME_CSTS) & NVME_CSTS_RDY))
        return false;
    adopt_armed = true;
    c9_diag_snapshot(31);
    c9_diag_event(C9_ADOPT_ARM, 1, read32(nvme_base + NVME_CC),
                  read32(nvme_base + NVME_CSTS),
                  read32(nvme_base + NVME_BOOT_STATUS), 0);
    return true;
}

void nvme_shutdown(void)
{
    if (adopt_armed) {
        if (!asc_cpu_running(nvme_asc) ||
            read32(nvme_base + NVME_BOOT_STATUS) != NVME_BOOT_STATUS_OK)
            panic("ADOPT: retained ANS stopped before kernel handoff\\n");
        printf("ADOPT: retain running ANS, buffers and SART mappings\\n");
        return;
    }""")

    edit("proxy.c", "        case P_NVME_INIT:", """        case 0xf06: /* One-shot adoption handoff; no disk operations */
            reply->retval = nvme_adopt_handoff();
            break;
        case P_NVME_INIT:""")

    edit("c9diag.h", "    C9_MAP, C9_UNMAP, C9_QUEUE, C9_SART_TRACK,\n};", """    C9_MAP, C9_UNMAP, C9_QUEUE, C9_SART_TRACK,
    C9_ADOPT_ARM = 25, C9_ADOPT_RESERVE,
};""")
    edit("c9diag.h", "u64 c9_diag_get(u64 selector, u64 phase);", """int c9_diag_reserve_adopt(void *fdt);
u32 c9_diag_protected_mask(void);
u64 c9_diag_get(u64 selector, u64 phase);""")

    edit("c9diag.c", '#include "utils.h"', '#include "utils.h"\n#include "nvme.h"\n#include "libfdt/libfdt.h"')
    edit("c9diag.c", '"C9-LOCAL"', '"C9-ADOPT"')
    edit("c9diag.c", "u64 c9_diag_get(u64 selector, u64 phase)", """u32 c9_diag_protected_mask(void)
{
    if (store.snapshots)
        return store.snapshot[store.snapshots - 1].protected_mask;
    return sart_protected;
}

int c9_diag_reserve_adopt(void *fdt)
{
    if (!nvme_adopt_armed())
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
        c9_diag_event(C9_ADOPT_RESERVE, 1, e->a, size, e->kind, 0);
    }
    if (maps != 3 || queues != 6)
        return -1;
    /* Publish the adoption contract for the Linux consumer. The consumer
     * refuses adoption unless controller-state is exactly "disabled".
     * BOOT_STATUS comes from the C9_ADOPT_ARM event (its c field), not
     * from a register read here: c9diag owns no NVMe register map. */
    u32 boot_status = 0;
    for (u32 i = begin; i < end; i++)
        if (store.event[i].kind == C9_ADOPT_ARM)
            boot_status = (u32)store.event[i].c;
    if (!boot_status)
        return -1;
    int node = fdt_path_offset(fdt, "/chosen");
    if (node < 0)
        return -1;
    if (fdt_setprop_u32(fdt, node, "j604,ans-live", 1) ||
        fdt_setprop(fdt, node, "j604,ans-live-controller-state",
                    "disabled", sizeof("disabled")) ||
        fdt_setprop_u32(fdt, node, "j604,ans-live-boot-status", boot_status) ||
        fdt_setprop_u32(fdt, node, "j604,ans-live-sart-mask",
                        c9_diag_protected_mask()))
        return -1;
    return 0;
}

u64 c9_diag_get(u64 selector, u64 phase)""")

    include = '#include "nvme.h"' if '#include "nvme.h"' in (root / "src/kboot.c").read_text() else '#include "adt.h"'
    edit("kboot.c", include, include + '\n#include "c9diag.h"')
    edit("kboot.c", "    if (fdt_pack(dt))", """    if (c9_diag_reserve_adopt(dt))
        bail("ADOPT: could not reserve retained ANS allocations\\n");

    if (fdt_pack(dt))""")

    patch = "".join("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
        fromfile=f"a/src/{name}", tofile=f"b/src/{name}")) for name, (old, new) in changes.items())
    (root.parent / "m1n1-adoption.patch").write_text(patch)
    for name, (_, new) in changes.items():
        (root / "src" / name).write_text(new)
    print("Adoption producer prepared; patch at", root.parent / "m1n1-adoption.patch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    prepare(args.root)
