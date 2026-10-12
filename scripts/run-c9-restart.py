#!/usr/bin/env python3
"""One C9 m1n1 init/read/shutdown/init/read cell; no SSD write commands."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys

STORE_BYTES = 58432
EVENT_BYTES = 48
SNAPSHOT_BYTES = 288
KINDS = {
    1: "INIT_BEGIN", 2: "INIT_END", 3: "SHUT_BEGIN", 4: "SHUT_END",
    5: "CTRL_SHUT", 6: "CTRL_DISABLE", 7: "DELETE_SQ", 8: "DELETE_CQ",
    9: "SLEEP_SWITCH", 10: "CPU_STOP", 11: "PMGR_ALIAS", 12: "PMGR_BEFORE",
    13: "PMGR_AFTER", 14: "RX", 15: "TX_BEGIN", 16: "TX_END", 17: "CRASH",
    18: "MAP", 19: "UNMAP", 20: "QUEUE", 21: "SART_TRACK",
    22: "HOLD", 23: "HOLD_ARM",
}


class PhaseTimeout(Exception):
    pass


def buffer_ranges(trace):
    """Require the three successful ANS RTKit maps for the latest init."""
    events = trace["events"]
    begin = max(i for i, event in enumerate(events) if event["kind"] == "INIT_BEGIN")
    maps = [event for event in events[begin:] if event["kind"] == "MAP"]
    if len(maps) != 3 or sorted(event["b"] for event in maps) != [16384, 16384, 32768]:
        raise ValueError("Expected exactly three RTKit buffers totalling 64 KiB")
    if any(event["result"] != 1 or event["a"] != event["c"] or event["a"] & 0x3fff for event in maps):
        raise ValueError("Invalid RTKit physical mapping")
    ranges = [(event["a"], event["b"]) for event in maps]
    if any(a < b + m and b < a + n for i, (a, n) in enumerate(ranges)
           for b, m in ranges[i+1:]):
        raise ValueError("Overlapping RTKit buffers")
    return ranges


def retained_findings(trace, first):
    holds = [event for event in trace["events"] if event["kind"] == "HOLD"]
    arms = [event for event in trace["events"] if event["kind"] == "HOLD_ARM"]
    if len(arms) != 1 or arms[0]["result"] != 1:
        raise ValueError("Missing one-shot retention arm")
    if (len(holds) != 3 or any(event["result"] != 1 for event in holds)
            or sorted((event["a"], event["b"]) for event in holds) != sorted(first)):
        raise ValueError("Old RTKit buffers were not all retained")
    return {"bytes": sum(size for _, size in first), "buffers": len(holds)}


def relocation_findings(first, second):
    if sorted(size for _, size in first) != sorted(size for _, size in second):
        raise ValueError("RTKit buffer sizes differ across restart")
    if any(a < b + m and b < a + n for a, n in first for b, m in second):
        raise ValueError("Replacement RTKit buffer overlaps an old buffer")
    return {"pass": True, "first": [{"address": hex(a), "bytes": n} for a, n in first],
            "second": [{"address": hex(a), "bytes": n} for a, n in second]}


def decode(raw):
    if len(raw) != STORE_BYTES or raw[:8] != b"C9DIAG1\0":
        raise ValueError("Invalid diagnostic length/magic")
    abi, size, event_cap, snapshot_cap, events, snapshots, event_dropped, snapshot_dropped = (
        struct.unpack_from("<8I", raw, 8))
    if (abi, size, event_cap, snapshot_cap) != (1, STORE_BYTES, 1024, 32):
        raise ValueError("Unsupported C9 ABI")
    if events > event_cap or snapshots > snapshot_cap:
        raise ValueError("Invalid C9 record counts")
    result = {
        "abi": abi, "bytes": size,
        "variant": raw[48:64].split(b"\0", 1)[0].decode("ascii"),
        "ans_cpu_base": hex(struct.unpack_from("<Q", raw, 40)[0]),
        "event_count": events, "snapshot_count": snapshots,
        "event_dropped": event_dropped, "snapshot_dropped": snapshot_dropped,
        "events": [], "snapshots": [],
    }
    for index in range(events):
        ticks, kind, value, a, b, c, d = struct.unpack_from("<QIi4Q", raw, 64 + index * EVENT_BYTES)
        event = {"index": index, "ticks": ticks, "kind": KINDS.get(kind, f"UNKNOWN_{kind}"),
                 "result": value, "a": a, "b": b, "c": c, "d": d}
        if kind in (14, 15, 16):
            event.update(endpoint=b, message=f"{a:016x}")
            if b == 0:
                event.update(management_type=(a >> 52) & 0xff, power_state=a & 0xffff)
        result["events"].append(event)
    for index in range(snapshots):
        offset = 64 + 1024 * EVENT_BYTES + index * SNAPSHOT_BYTES
        ticks, base, phase, protected, version, status = struct.unpack_from("<QQ4I", raw, offset)
        words = struct.unpack_from("<64I", raw, offset + 32)
        snapshot = {"index": index, "ticks": ticks, "base": hex(base), "phase": phase,
                    "protected_mask": protected, "version": version, "status": status,
                    "slots": []}
        for slot in range(16):
            before, addr, length, after = words[slot], words[16 + slot], words[32 + slot], words[48 + slot]
            snapshot["slots"].append({
                "index": slot, "config_before": before, "paddr_raw": addr,
                "size_raw": length, "config_after": after,
                "stable": before == after, "flags": after & 0xff,
                "upper_config_bits": after & 0xffffff00,
                "physical_base": hex(addr << 12), "bytes": length << 12,
            })
        result["snapshots"].append(snapshot)
    return result


def shutdown_findings(trace):
    events = trace["events"]
    starts = [index for index, event in enumerate(events) if event["kind"] == "SHUT_BEGIN" and event["a"] == 1]
    if not starts:
        return {"pass": False, "issues": ["No initialized shutdown begin"]}
    shutdown = events[starts[-1]:]
    issues = []
    for kind in ("DELETE_SQ", "DELETE_CQ", "CTRL_SHUT", "CTRL_DISABLE", "SHUT_END"):
        found = [event for event in shutdown if event["kind"] == kind]
        if len(found) != 1 or found[0]["result"] != 1:
            issues.append(f"Missing/failed {kind}")
    switches = [event for event in shutdown if event["kind"] == "SLEEP_SWITCH"]
    if len(switches) != 1 or (switches[0]["result"], switches[0]["a"], switches[0]["b"], switches[0]["c"]) != (1, 0x10, 1, 0):
        issues.append("Sleep switch did not confirm AP QUIESCED / IOP SLEEP")
    for msg_type, state, label in ((11, 0x10, "AP QUIESCED"), (7, 1, "IOP SLEEP")):
        if not any(event["kind"] == "RX" and event.get("endpoint") == 0 and
                   event.get("management_type") == msg_type and event.get("power_state") == state
                   for event in shutdown):
            issues.append(f"Missing actual {label} ACK")
    stops = [event for event in shutdown if event["kind"] == "CPU_STOP"]
    if len(stops) != 1 or stops[0]["a"] & 0x10:
        issues.append("CPU RUN clear not captured")
    resets = [event for event in shutdown if event["kind"] == "PMGR_ALIAS"]
    if len(resets) != 2 or not any(event["result"] == 0 for event in resets):
        issues.append("No successful resolved ANS/ANS2 reset")
    if any(event["kind"] == "CRASH" for event in shutdown):
        issues.append("ANS crash during shutdown")
    return {"pass": not issues, "issues": issues, "reset_aliases": resets}


def run(args):
    if not args.manifest or not args.output:
        raise ValueError("A manifest and new output directory are required")
    manifest = json.loads(args.manifest.read_text())
    relocate = args.relocate_buffers
    if relocate and manifest["variant"] != "C9-LOCAL-R":
        raise ValueError("Relocation requires the bounded retention image")
    if not relocate and manifest["variant"] == "C9-LOCAL-R":
        raise ValueError("Retention image requires --relocate-buffers")
    if hashlib.sha256(Path(manifest["raw_binary"]).read_bytes()).hexdigest() != manifest["raw_binary_sha256"]:
        raise ValueError("Temporary m1n1 image differs from manifest")
    device = os.environ.get("M1N1DEVICE", "/dev/m1n1")
    if not Path(device).exists():
        raise ValueError(f"Missing proxy: {device}")
    if subprocess.run(["fuser", "-s", device], check=False).returncode == 0:
        raise ValueError("Proxy is already in use")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    sys.path.insert(0, str(args.proxyclient.resolve()))
    from m1n1.proxy import UartInterface, M1N1Proxy
    from m1n1.tgtypes import BootArgs_r1, BootArgs_r2, BootArgs_r3
    from m1n1.adt import load_adt
    iface = None
    timed_out = False
    phase = "connect"
    trace_address = None
    result = {"started_at": datetime.now().astimezone().isoformat(),
              "variant": manifest["variant"], "device": device, "reads": {},
              "disk_write_commands": 0, "status": "RUNNING"}
    result["relocate_buffers"] = relocate

    def alarm_handler(signum, frame):
        raise PhaseTimeout(f"Host deadline at {phase}; target code may still be running")

    signal.signal(signal.SIGALRM, alarm_handler)

    def operation(label, fn, seconds=20):
        nonlocal phase, timed_out
        phase = label
        (args.output / "phase.txt").write_text(label + "\n")
        print(f"C9 HOST phase={label}", flush=True)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            return fn()
        except PhaseTimeout:
            timed_out = True
            raise
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    def save_trace(label):
        raw = operation(f"capture-{label}", lambda: iface.readmem(trace_address, STORE_BYTES))
        trace = decode(raw)
        if trace["variant"] != manifest["variant"]:
            raise ValueError("Wrong temporary image variant")
        (args.output / f"trace-{label}.bin").write_bytes(raw)
        (args.output / f"trace-{label}.json").write_text(json.dumps(trace, indent=2) + "\n")
        if trace["event_dropped"] or trace["snapshot_dropped"]:
            raise ValueError("Diagnostic capture overflow; cell cannot be marked PASS")
        if any(not slot["stable"] for snapshot in trace["snapshots"] if snapshot["status"] == 0
               for slot in snapshot["slots"]):
            result["unstable_sart_snapshot"] = True
        return trace

    def read_set(label, buffer):
        hashes = {}
        for lba in (0, 1, 2, 128, 4096):
            sentinel = hashlib.sha256(f"{label}:{lba}".encode()).digest() * 128
            operation(f"{label}-sentinel-{lba}", lambda: iface.writemem(buffer, sentinel))
            ok = operation(f"{label}-read-{lba}", lambda: proxy.nvme_read(1, lba, buffer))
            if ok != 1:
                raise ValueError(f"NVMe read failed: {label} LBA {lba}")
            raw = operation(f"{label}-readback-{lba}", lambda: iface.readmem(buffer, 4096))
            if raw == sentinel:
                raise ValueError("Read buffer still contains its sentinel")
            if lba == 1:
                if raw[:8] != b"EFI PART":
                    raise ValueError("Missing GPT signature at 4Kn LBA 1")
                if struct.unpack_from("<Q", raw, 32)[0] <= 4096:
                    raise ValueError("GPT disk bounds do not cover the read set")
            (args.output / f"{label}-lba-{lba:06d}.bin").write_bytes(raw)
            hashes[str(lba)] = hashlib.sha256(raw).hexdigest()
            result["reads"][label] = hashes.copy()
            (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return hashes

    try:
        iface = operation("connect", lambda: UartInterface(device))
        iface.dev.timeout = 5
        proxy = M1N1Proxy(iface, debug=False)
        operation("nop", iface.nop)
        address = operation("bootargs-pointer", proxy.get_bootargs)
        revision = int.from_bytes(operation("bootargs-revision", lambda: iface.readmem(address, 4))[:2], "little")
        layouts = {0: BootArgs_r1, 1: BootArgs_r1, 2: BootArgs_r2, 3: BootArgs_r3}
        layout = layouts[revision]
        raw_args = operation("bootargs", lambda: iface.readmem(address, layout.sizeof()))
        ba = layout.parse(raw_args)
        adt_address = (ba.devtree - ba.virt_base + ba.phys_base) & ((1 << 64) - 1)
        ram_end = ba.phys_base + (ba.mem_size_actual or ba.mem_size)
        if not (0 < ba.devtree_size <= 16 * 1024 * 1024 and
                ba.phys_base <= adt_address < adt_address + ba.devtree_size <= ram_end):
            raise ValueError("ADT outside DRAM bounds")
        raw_adt = operation("adt", lambda: iface.readmem(adt_address, ba.devtree_size))
        adt = load_adt(raw_adt)
        sart = adt["/arm-io/sart-ans"]
        if sart.getprop("sart-version") != 3 or sart.get_reg(0)[0] != 0x485c50000:
            raise ValueError("Unexpected SART version/address")
        if adt["/arm-io/ans"].get_reg(0)[0] != 0x481600000:
            raise ValueError("Unexpected ANS address")
        (args.output / "bootargs.bin").write_bytes(raw_args)
        (args.output / "adt.bin").write_bytes(raw_adt)
        result["adt_sha256"] = hashlib.sha256(raw_adt).hexdigest()
        result["ans_manifest_hash_from_adt"] = adt["/chosen/secure-boot-hashes"].getprop("ansf").hex()
        trace_address = operation("trace-pointer", lambda: proxy.request(0xf04, 0))
        trace_size = operation("trace-size", lambda: proxy.request(0xf04, 1))
        if trace_size != STORE_BYTES or not (ba.phys_base <= trace_address < trace_address + STORE_BYTES <= ram_end):
            raise ValueError("Diagnostic store outside DRAM or wrong size")
        initial = save_trace("preflight")
        if any(event["kind"] == "INIT_BEGIN" for event in initial["events"]):
            raise ValueError("This temporary image already used NVMe; fresh cell required")
        operation("snapshot-before-init", lambda: proxy.request(0xf04, 2, 0))
        save_trace("before-init")
        buffer = operation("read-buffer", lambda: proxy.memalign(16384, 16384))
        if not (ba.phys_base <= buffer < buffer + 16384 <= ram_end) or buffer & 0x3fff:
            raise ValueError("Invalid aligned DRAM read buffer")
        result["read_buffer"] = hex(buffer)
        ok = operation("first-init", proxy.nvme_init, seconds=45)
        first_trace = save_trace("first-init")
        phase = "first-init"
        if ok != 1 or any(event["kind"] == "CRASH" for event in first_trace["events"]):
            raise ValueError("First init failed; this does not test restart")
        first = read_set("first", buffer)
        if manifest.get("expected_read_hashes") and first != manifest["expected_read_hashes"]:
            raise ValueError("First reads differ from saved C9 reference hashes")
        operation("snapshot-first-reads", lambda: proxy.request(0xf04, 2, 10))
        first_reads_trace = save_trace("first-reads")
        if relocate:
            first_ranges = buffer_ranges(first_reads_trace)
            if operation("arm-buffer-retention", lambda: proxy.request(0xf04, 3)) != 1:
                raise ValueError("Could not arm one-shot retention")
        operation("shutdown", proxy.nvme_shutdown, seconds=45)
        shutdown_trace = save_trace("shutdown")
        findings = shutdown_findings(shutdown_trace)
        result["shutdown"] = findings
        phase = "shutdown"
        if not findings["pass"]:
            raise ValueError("Shutdown not proven: " + "; ".join(findings["issues"]))
        if relocate:
            result["retention"] = retained_findings(shutdown_trace, first_ranges)
        ok = operation("second-init", proxy.nvme_init, seconds=45)
        second_trace = save_trace("second-init")
        phase = "second-init"
        begins = [event for event in second_trace["events"] if event["kind"] == "INIT_BEGIN"]
        if ok != 1 or len(begins) != 2 or begins[-1]["a"] != 0:
            raise ValueError("Second init failed or was an already-initialized no-op")
        if any(event["kind"] == "CRASH" for event in second_trace["events"]):
            raise ValueError("ANS crash during restart")
        if relocate:
            result["relocation"] = relocation_findings(first_ranges, buffer_ranges(second_trace))
        second = read_set("second", buffer)
        operation("snapshot-second-reads", lambda: proxy.request(0xf04, 2, 30))
        save_trace("second-reads")
        if first != second:
            raise ValueError("Block hashes changed across restart")
        result["status"] = "PASS"
        result["phase"] = "complete"
        # Leave successful ANS running; any next cell needs a fresh LabOS boot.
    except Exception as error:
        result.update(status="FAIL", phase=phase, error=f"{type(error).__name__}: {error}",
                      host_deadline=timed_out)
        # Do not queue requests after a timeout or failed operation.
        print(result["error"], flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if iface is not None:
            iface.dev.close()
        result["finished_at"] = datetime.now().astimezone().isoformat()
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
    return 0 if result["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxyclient", type=Path, default=Path("/home/btega/bootloader/proxyclient"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--relocate-buffers", action="store_true",
                        help="retain old buffers through shutdown and require non-overlapping replacements")
    parser.add_argument("--decode", type=Path, help="decode a saved store offline; never open serial")
    args = parser.parse_args()
    if args.decode:
        print(json.dumps(decode(args.decode.read_bytes()), indent=2))
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
