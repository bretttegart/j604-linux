# Desk check — does the kernel's ps_ans reset cover "ANS2"? — Oct 12, 2026

Follow-up to the lead left open in the
[E4 cold session note](C9-E4-L1-SESSION-2026-10-12.md): the device
tree gives the NVMe node a single reset (`resets = <&ps_ans>`) while
m1n1's proven cycle calls `pmgr_reset` for both ANS and ANS2.

## Evidence

- **Kernel/DT**: `ps_ans` is `power-controller@538` in
  `t8132-pmgr.dtsi` — PMGR register offset `0x538`, label `ans`,
  `#reset-cells = <0>`, `apple,always-on`. No second ANS power
  domain exists in the DT.
- **m1n1, measured**: the diagnostic trace of the m1n1 cycle in the
  E4-L1 run (`trace-nvme-shutdown.json`) records `PMGR_BEFORE` /
  `PMGR_AFTER` events at address `0x380700538` — PMGR base
  `0x380700000` + offset `0x538` — exactly the device the kernel's
  `ps_ans` reset targets.
- **The second call is a no-op on this machine**: the trace records
  two `PMGR_ALIAS` resolutions, one with result 0 and one with
  result −1 (name not found). Only one PMGR device is actually reset
  in m1n1's cycle. This matches the m1n1 source comment: "Some
  machines call this ANS, some ANS2..." — the two names are
  alternatives across machines, not two devices on this one.

## Conclusion

The reset-coverage lead is closed. Linux's single `&ps_ans` reset
targets the same PMGR device (PMGR+0x538) that m1n1's proven cycle
resets; there is no un-reset ANS2 domain on the J604.

With this, the cold path has construction (E4-L1), same-session
history (E4-L1), and reset coverage (this check) all eliminated,
matching the warm path's eliminations. The remaining warm-path test
is E5 (m1n1 hands a live session to Linux in the same power session).
Beyond that, the strongest untried evidence is the firmware's own
crashlog payload for the sleep crash — the panel shows only that an
endpoint-1 message arrives at +0 ms; reading its content requires a
harness that exports the raw kernel log or the crashlog buffer, which
the current panel-only harness cannot do.
