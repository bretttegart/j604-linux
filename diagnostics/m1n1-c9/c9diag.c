/* SPDX-License-Identifier: MIT */
/* C9 observations only: no power/reset/ANS register writes, no hook printf. */
#include "adt.h"
#include "c9diag.h"
#include "utils.h"

#define C9_EVENT_CAP 1024
#define C9_SNAPSHOT_CAP 32
#ifndef C9_VARIANT
#define C9_VARIANT "C9-UNSET"
#endif

struct c9_event {
    u64 ticks;
    u32 kind;
    s32 result;
    u64 a, b, c, d;
};

struct c9_snapshot {
    u64 ticks, base;
    u32 phase, protected_mask, version, status;
    u32 config_before[16], paddr[16], size[16], config_after[16];
};

struct c9_store {
    char magic[8];
    u32 abi, bytes, event_cap, snapshot_cap;
    u32 events, snapshots, event_dropped, snapshot_dropped;
    u64 ans_cpu_base;
    char variant[16];
    struct c9_event event[C9_EVENT_CAP];
    struct c9_snapshot snapshot[C9_SNAPSHOT_CAP];
};

_Static_assert(sizeof(struct c9_event) == 48, "C9 event ABI");
_Static_assert(sizeof(struct c9_snapshot) == 288, "C9 snapshot ABI");
_Static_assert(sizeof(struct c9_store) == 58432, "C9 store ABI");

static struct c9_store store = {
    .magic = "C9DIAG1", .abi = 1, .bytes = sizeof(store),
    .event_cap = C9_EVENT_CAP, .snapshot_cap = C9_SNAPSHOT_CAP,
    .variant = C9_VARIANT,
};
static u64 sart_base;
static u32 sart_version, sart_protected = 0xffffffff;

void c9_diag_event(u32 kind, s32 result, u64 a, u64 b, u64 c, u64 d)
{
    /* m1n1 ASC/proxy calls run synchronously on the primary CPU. */
    if (store.events >= C9_EVENT_CAP) {
        store.event_dropped++;
        return;
    }
    struct c9_event *event = &store.event[store.events++];
    *event = (struct c9_event){get_ticks(), kind, result, a, b, c, d};
}

void c9_diag_set_asc(u64 base)
{
    store.ans_cpu_base = base;
}

bool c9_diag_is_asc(u64 base)
{
    return store.ans_cpu_base && store.ans_cpu_base == base;
}

bool c9_diag_is_sart(u64 base)
{
    return sart_base && sart_base == base;
}

void c9_diag_sart_track(u64 base, u32 version, u32 protected_mask)
{
    sart_base = base;
    sart_version = version;
    sart_protected = protected_mask;
    c9_diag_event(C9_SART_TRACK, 0, base, version, protected_mask, 0);
}

void c9_diag_snapshot(u32 phase)
{
    if (store.snapshots >= C9_SNAPSHOT_CAP) {
        store.snapshot_dropped++;
        return;
    }
    struct c9_snapshot *snapshot = &store.snapshot[store.snapshots++];
    snapshot->ticks = get_ticks();
    snapshot->base = sart_base;
    snapshot->phase = phase;
    snapshot->protected_mask = sart_protected;
    snapshot->version = sart_version;
    /* Unsupported/unidentified blocks produce metadata only. */
    if (!sart_base || sart_version != 3) {
        snapshot->status = 1;
        return;
    }
    for (unsigned int i = 0; i < 16; i++) {
        snapshot->config_before[i] = read32(sart_base + 4 * i);
        snapshot->paddr[i] = read32(sart_base + 0x40 + 4 * i);
        snapshot->size[i] = read32(sart_base + 0x80 + 4 * i);
        snapshot->config_after[i] = read32(sart_base + 4 * i);
    }
}

void c9_diag_skip_snapshot(u32 phase, u32 reason)
{
    if (store.snapshots >= C9_SNAPSHOT_CAP) {
        store.snapshot_dropped++;
        return;
    }
    struct c9_snapshot *snapshot = &store.snapshot[store.snapshots++];
    snapshot->ticks = get_ticks();
    snapshot->base = sart_base;
    snapshot->phase = phase;
    snapshot->protected_mask = sart_protected;
    snapshot->version = sart_version;
    snapshot->status = reason ? reason : 1;
}

u64 c9_diag_get(u64 selector, u64 phase)
{
    if (selector == 0)
        return (u64)&store;
    if (selector == 1)
        return sizeof(store);
    if (selector == 2) {
        /* Initial host snapshot resolves only the ADT-identified SARTv3. */
        if (!sart_base) {
            int path[8];
            int node = adt_path_offset_trace(adt, "/arm-io/sart-ans", path);
            u32 version;
            u64 base;
            if (node < 0 || ADT_GETPROP(adt, node, "sart-version", &version) < 0 ||
                adt_get_reg(adt, path, "reg", 0, &base, NULL) < 0)
                return 0;
            c9_diag_sart_track(base, version, 0xffffffff);
        }
        c9_diag_snapshot(phase);
        return store.snapshots;
    }
    return 0;
}
