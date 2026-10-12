/* SPDX-License-Identifier: MIT */
#ifndef C9DIAG_H
#define C9DIAG_H
#include "types.h"

enum c9_event_kind {
    C9_INIT_BEGIN = 1, C9_INIT_END, C9_SHUT_BEGIN, C9_SHUT_END,
    C9_CTRL_SHUT, C9_CTRL_DISABLE, C9_DELETE_SQ, C9_DELETE_CQ,
    C9_SLEEP_SWITCH, C9_CPU_STOP, C9_PMGR_ALIAS, C9_PMGR_BEFORE,
    C9_PMGR_AFTER, C9_RX, C9_TX_BEGIN, C9_TX_END, C9_CRASH,
    C9_MAP, C9_UNMAP, C9_QUEUE, C9_SART_TRACK,
};

void c9_diag_event(u32 kind, s32 result, u64 a, u64 b, u64 c, u64 d);
void c9_diag_set_asc(u64 base);
bool c9_diag_is_asc(u64 base);
bool c9_diag_is_sart(u64 base);
void c9_diag_sart_track(u64 base, u32 version, u32 protected_mask);
void c9_diag_snapshot(u32 phase);
void c9_diag_skip_snapshot(u32 phase, u32 reason);
u64 c9_diag_get(u64 selector, u64 phase);
#endif
