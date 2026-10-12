#!/usr/bin/env python3
"""Inspect a captured ADT binary offline; never open a proxy connection."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def walk(node):
    yield node
    for child in node:
        yield from walk(child)


def audit(adt, raw, bus, ap):
    result = {
        "adt_sha256": hashlib.sha256(raw).hexdigest(),
        "targets": {"bus": hex(bus), "ap": hex(ap)},
        "raw_reg_matches": [], "translated_reg_matches": [],
        "range_translation_matches": [], "decode_errors": [],
        "visited_nodes": 0, "reg_ranges_checked": 0,
    }
    # Recurse explicitly: the local ADTNode.walk_tree() implementation skips
    # intermediate nodes and is unsuitable for a complete range lookup.
    for node in walk(adt):
        result["visited_nodes"] += 1
        regs = node.getprop("reg")
        if isinstance(regs, list):
            for index, reg in enumerate(regs):
                if not hasattr(reg, "addr") or not isinstance(reg.addr, int):
                    continue
                result["reg_ranges_checked"] += 1
                if reg.addr <= bus < reg.addr + reg.size:
                    result["raw_reg_matches"].append({
                        "path": node._path, "index": index,
                        "address": hex(reg.addr), "size": hex(reg.size)})
                try:
                    address, size = node.get_reg(index)
                    if address <= ap < address + size:
                        result["translated_reg_matches"].append({
                            "path": node._path, "index": index,
                            "address": hex(address), "size": hex(size)})
                except (AttributeError, TypeError, ValueError) as error:
                    result["decode_errors"].append({
                        "path": node._path, "index": index, "error": str(error)})
        ranges = node.getprop("ranges")
        if isinstance(ranges, list):
            for index, region in enumerate(ranges):
                if not isinstance(region.bus_addr, int):
                    continue
                if region.bus_addr <= bus < region.bus_addr + region.size:
                    result["range_translation_matches"].append({
                        "path": node._path, "index": index,
                        "bus_start": hex(region.bus_addr),
                        "parent_start": hex(region.parent_addr),
                        "size": hex(region.size),
                        "translated_target": hex(bus - region.bus_addr + region.parent_addr)})
    sart = adt["/arm-io/sart-ans"]
    result["sart"] = {
        "version": sart.getprop("sart-version"),
        "regs": [{"index": index, "bus_address": hex(reg.addr),
                  "ap_address": hex(sart.get_reg(index)[0]), "size": hex(reg.size)}
                 for index, reg in enumerate(sart.reg)],
        "power_reg_offset": sart.getprop("sart-power-reg-offset"),
        "power_canary_offset": sart.getprop("power-canary-offset"),
    }
    result["caveat"] = (
        "Register-range lookup only. Firmware VA/bus identity and "
        "asynchronous FAR validity are not established.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adt", type=Path)
    parser.add_argument("--proxyclient", type=Path,
                        default=Path("/home/btega/bootloader/proxyclient"))
    parser.add_argument("--bus", type=lambda value: int(value, 0), default=0x29f008000)
    parser.add_argument("--ap", type=lambda value: int(value, 0), default=0x49f008000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.proxyclient.resolve()))
    from m1n1.adt import load_adt
    raw = args.adt.read_bytes()
    result = audit(load_adt(raw), raw, args.bus, args.ap)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        with args.output.open("x") as handle:
            handle.write(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
