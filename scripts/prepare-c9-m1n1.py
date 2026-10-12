#!/usr/bin/env python3
"""Add C9 observation hooks to disposable m1n1 source copies, never live trees."""
import argparse
import difflib
from pathlib import Path
import shutil


def replace(text, old, new, count=1):
    actual = text.count(old)
    if actual != count:
        raise ValueError(f"Expected {count} copies, found {actual}: {old!r}")
    return text.replace(old, new)


def prepare(root, variant):
    templates = Path(__file__).resolve().parents[1] / "diagnostics/m1n1-c9"
    if (root / "src/c9diag.c").exists():
        raise ValueError(f"Already instrumented: {root}")
    changed = {}
    for name in ("nvme.c", "asc.c", "rtkit.c", "sart.c", "pmgr.c", "proxy.c"):
        path = root / "src" / name
        old = path.read_text()
        text = old.replace('#include "adt.h"', '#include "adt.h"\n#include "c9diag.h"', 1)
        if '#include "c9diag.h"' not in text:
            text = text.replace('\n#include ', '\n#include "c9diag.h"\n#include ', 1)
        changed[name] = [old, text]

    old, text = changed["asc.c"]
    text = replace(text, '    asc->cpu_base = base;', '''    asc->cpu_base = base;
    if (!strcmp(path, "/arm-io/ans"))
        c9_diag_set_asc(base);''')
    # The upstream file did not need string.h before this exact path check.
    if '#include "string.h"' not in text:
        text = text.replace('#include "c9diag.h"', '#include "c9diag.h"\n#include "string.h"')
    text = replace(text, '    dma_rmb();', '''    dma_rmb();
    if (c9_diag_is_asc(asc->cpu_base))
        c9_diag_event(C9_RX, 1, msg->msg0, msg->msg1, 0, 0);''')
    text = replace(text, 'bool asc_send(asc_dev_t *asc, const struct asc_message *msg)\n{', '''bool asc_send(asc_dev_t *asc, const struct asc_message *msg)
{
    if (c9_diag_is_asc(asc->cpu_base))
        c9_diag_event(C9_TX_BEGIN, 0, msg->msg0, msg->msg1, 0, 0);''')
    text = replace(text, '        printf("asc: A2I mailbox full for 200ms. Is the ASC stuck?");', '''        if (c9_diag_is_asc(asc->cpu_base))
            c9_diag_event(C9_TX_END, 0, msg->msg0, msg->msg1, 0, 0);
        printf("asc: A2I mailbox full for 200ms. Is the ASC stuck?");''')
    text = replace(text, '    // printf("sent msg: %lx %x\\n", msg->msg0, msg->msg1);', '''    if (c9_diag_is_asc(asc->cpu_base))
        c9_diag_event(C9_TX_END, 1, msg->msg0, msg->msg1, 0, 0);
    // printf("sent msg: %lx %x\\n", msg->msg0, msg->msg1);''')
    text = replace(text, '    clear32(asc->cpu_base + ASC_CPU_CONTROL, ASC_CPU_CONTROL_START);', '''    clear32(asc->cpu_base + ASC_CPU_CONTROL, ASC_CPU_CONTROL_START);
    if (c9_diag_is_asc(asc->cpu_base))
        c9_diag_event(C9_CPU_STOP, 0, read32(asc->cpu_base + ASC_CPU_CONTROL), 0, 0, 0);''')
    changed["asc.c"][1] = text

    old, text = changed["rtkit.c"]
    text = replace(text, '    rtk->crashed = true;', '''    rtk->crashed = true;
    if (!strcmp(rtk->name, "nvme"))
        c9_diag_event(C9_CRASH, 1, (u64)rtk->crashlog_bfr.bfr, rtk->crashlog_bfr.sz, 0, 0);''')
    text = replace(text, '        *dva = (u64)phys;', '''        *dva = (u64)phys;
        if (!strcmp(rtk->name, "nvme"))
            c9_diag_event(C9_MAP, 1, (u64)phys, sz, *dva, 0);''')
    text = replace(text, '    if (rtk->sart) {\n        if (!sart_remove_allowed_region', '''    if (rtk->sart) {
        if (!strcmp(rtk->name, "nvme"))
            c9_diag_event(C9_UNMAP, 0, dva, sz, 0, 0);
        if (!sart_remove_allowed_region''')
    text = replace(text, '    int ret = rtkit_switch_power_state(rtk, RTKIT_POWER_SLEEP);', '''    int ret = rtkit_switch_power_state(rtk, RTKIT_POWER_SLEEP);
    if (!strcmp(rtk->name, "nvme"))
        c9_diag_event(C9_SLEEP_SWITCH, ret, rtk->ap_power, rtk->iop_power, rtk->crashed, 0);''')
    changed["rtkit.c"][1] = text

    old, text = changed["sart.c"]
    text = replace(text, '    sart->protected_entries = 0;', '''    if (!strcmp(adt_path, "/arm-io/sart-ans")) {
        c9_diag_sart_track(base, *sart_version, 0xffffffff);
        c9_diag_snapshot(5);
    }
    sart->protected_entries = 0;''')
    text = replace(text, '    return sart;', '''    if (!strcmp(adt_path, "/arm-io/sart-ans")) {
        c9_diag_sart_track(base, *sart_version, sart->protected_entries);
        c9_diag_snapshot(6);
    }
    return sart;''')
    text = replace(text, '    free(sart);\n}', '''    if (c9_diag_is_sart(sart->base))
        c9_diag_snapshot(24);
    free(sart);
}''')
    changed["sart.c"][1] = text

    old, text = changed["pmgr.c"]
    text = replace(text, '    u32 reg = read32(addr);\n    if (FIELD_GET', '''    u32 reg = read32(addr);
    if (!strncmp(dev->name, "ANS", 3))
        c9_diag_event(C9_PMGR_BEFORE, 0, addr, reg, pmgr_adt_get_id(dev), die);
    if (FIELD_GET''') if '    u32 reg = read32(addr);\n    if (FIELD_GET' in text else replace(text, '    u32 reg = read32(addr);\n    printf("SHAUD', '''    u32 reg = read32(addr);
    if (!strncmp(dev->name, "ANS", 3))
        c9_diag_event(C9_PMGR_BEFORE, 0, addr, reg, pmgr_adt_get_id(dev), die);
    printf("SHAUD''')
    text = replace(text, '    clear32(addr, PMGR_DEV_DISABLE);\n\n    return 0;', '''    clear32(addr, PMGR_DEV_DISABLE);
    if (!strncmp(dev->name, "ANS", 3))
        c9_diag_event(C9_PMGR_AFTER, 0, addr, read32(addr), pmgr_adt_get_id(dev), die);

    return 0;''')
    changed["pmgr.c"][1] = text

    old, text = changed["nvme.c"]
    helper = '''/* C9 helpers preserve the existing operation and return value. */
static bool c9_delete(struct nvme_command *cmd)
{
    bool ok = nvme_exec_command(&adminq, cmd, NULL);
    c9_diag_event(cmd->opcode == NVME_ADMIN_CMD_DELETE_SQ ? C9_DELETE_SQ : C9_DELETE_CQ,
                  ok, cmd->cdw10, 0, 0, 0);
    return ok;
}
static bool c9_ctrl_shutdown(void)
{
    bool ok = nvme_ctrl_shutdown();
    c9_diag_event(C9_CTRL_SHUT, ok, 0, 0, 0, 0);
    return ok;
}
static bool c9_ctrl_disable(void)
{
    bool ok = nvme_ctrl_disable();
    c9_diag_event(C9_CTRL_DISABLE, ok, 0, 0, 0, 0);
    return ok;
}
static int c9_reset(const char *name, u32 phase)
{
    int ret = pmgr_reset(nvme_die, name);
    c9_diag_event(C9_PMGR_ALIAS, ret, phase, nvme_die, 0, 0);
    /* pmgr_reset has returned with reset deasserted, or did not reset. */
    if (!ret)
        c9_diag_snapshot(phase);
    else
        c9_diag_skip_snapshot(phase, 2);
    return ret;
}

'''
    text = replace(text, 'bool nvme_init(void)\n{', '''bool nvme_init(void)
{
    c9_diag_event(C9_INIT_BEGIN, 0, nvme_initialized, 0, 0, 0);''')
    text = replace(text, '    adminq.adminq = true;', '''    adminq.adminq = true;
    c9_diag_event(C9_QUEUE, 0, (u64)adminq.cmds, NVME_QUEUE_SIZE * sizeof(*adminq.cmds), 0, 0);
    c9_diag_event(C9_QUEUE, 1, (u64)adminq.tcbs, NVME_QUEUE_SIZE * sizeof(*adminq.tcbs), 0, 0);
    c9_diag_event(C9_QUEUE, 2, (u64)adminq.cqes, NVME_QUEUE_SIZE * sizeof(*adminq.cqes), 0, 0);
    c9_diag_event(C9_QUEUE, 3, (u64)ioq.cmds, NVME_QUEUE_SIZE * sizeof(*ioq.cmds), 0, 0);
    c9_diag_event(C9_QUEUE, 4, (u64)ioq.tcbs, NVME_QUEUE_SIZE * sizeof(*ioq.tcbs), 0, 0);
    c9_diag_event(C9_QUEUE, 5, (u64)ioq.cqes, NVME_QUEUE_SIZE * sizeof(*ioq.cqes), 0, 0);''')
    text = replace(text, '    nvme_initialized = true;', '''    nvme_initialized = true;
    c9_diag_event(C9_INIT_END, 1, nvme_base, nvmmu_base, nvme_die, 0);
    c9_diag_snapshot(11);''')
    text = replace(text, 'out_adminq:\n    free_queue(&adminq);\n    return false;', '''out_adminq:
    free_queue(&adminq);
    c9_diag_event(C9_INIT_END, 0, nvme_base, nvmmu_base, nvme_die, 0);
    return false;''')
    start = text.index('void nvme_shutdown(void)\n{')
    end = text.index('\nbool nvme_flush', start)
    shutdown = text[start:end]
    shutdown = replace(shutdown, 'void nvme_shutdown(void)\n{', '''void nvme_shutdown(void)
{
    c9_diag_event(C9_SHUT_BEGIN, 0, nvme_initialized, 0, 0, 0);''')
    shutdown = replace(shutdown, 'nvme_exec_command(&adminq, &cmd, NULL)', 'c9_delete(&cmd)', 2)
    shutdown = replace(shutdown, 'nvme_ctrl_shutdown()', 'c9_ctrl_shutdown()')
    shutdown = replace(shutdown, 'nvme_ctrl_disable()', 'c9_ctrl_disable()')
    shutdown = replace(shutdown, '    rtkit_sleep(nvme_rtkit);', '''    c9_diag_snapshot(20);
    rtkit_sleep(nvme_rtkit);
    c9_diag_snapshot(21);''') if '    rtkit_sleep(nvme_rtkit);' in shutdown else replace(shutdown, '    ret = rtkit_sleep(nvme_rtkit);', '''    c9_diag_snapshot(20);
    ret = rtkit_sleep(nvme_rtkit);
    c9_diag_snapshot(21);''')
    shutdown = replace(shutdown, 'pmgr_reset(nvme_die, "ANS")', 'c9_reset("ANS", 22)')
    shutdown = replace(shutdown, 'pmgr_reset(nvme_die, "ANS2")', 'c9_reset("ANS2", 23)')
    shutdown = replace(shutdown, '    nvme_initialized = false;', '''    nvme_initialized = false;
    c9_diag_event(C9_SHUT_END, 1, 0, 0, 0, 0);
    c9_diag_snapshot(25);''')
    text = text[:start] + helper + shutdown + text[end:]
    changed["nvme.c"][1] = text

    old, text = changed["proxy.c"]
    text = replace(text, '        case P_NVME_INIT:', '''        case 0xf04: /* C9 diagnostic store; no disk operations */
            reply->retval = c9_diag_get(request->args[0], request->args[1]);
            break;
        case P_NVME_INIT:''')
    changed["proxy.c"][1] = text

    patch = ""
    for name, (old, text) in changed.items():
        patch += "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True),
                                            fromfile=f"a/src/{name}", tofile=f"b/src/{name}"))
    makefile = root / "Makefile"
    old = makefile.read_text()
    text = replace(old, '\tsart.o \\', '\tsart.o \\\n\tc9diag.o \\')
    patch += "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True),
                                        fromfile="a/Makefile", tofile="b/Makefile"))
    (root.parent / f"{variant.lower()}-diagnostic.patch").write_text(patch)
    for name, (_, text) in changed.items():
        (root / "src" / name).write_text(text)
    makefile.write_text(replace(old, '\tsart.o \\', '\tsart.o \\\n\tc9diag.o \\'))
    for name in ("c9diag.c", "c9diag.h"):
        shutil.copyfile(templates / name, root / "src" / name)
    # The build label is data only, and identical ABI/constants across variants.
    source = root / "src/c9diag.c"
    source.write_text(source.read_text().replace('"C9-UNSET"', f'"C9-{variant}"'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--local", type=Path, required=True)
    args = parser.parse_args()
    roots = [args.upstream.resolve(), args.local.resolve()]
    if roots[0] == roots[1] or roots[0].parent != roots[1].parent:
        parser.error("Use two distinct source copies in the same C9 preparation directory")
    for root in roots:
        if not root.parent.name.startswith("C9-PREP-") or (root / ".git").exists():
            parser.error("Refusing a live Git tree or a path outside C9-PREP-* source copies")
    prepare(args.upstream.resolve(), "UPSTREAM")
    prepare(args.local.resolve(), "LOCAL")
    print("Instrumented both disposable source copies; no image sent.")


if __name__ == "__main__":
    main()
