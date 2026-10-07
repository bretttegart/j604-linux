#!/usr/bin/env python3
"""Assemble an m1n1 boot image: m1n1.bin + appended payload segments.

Segment layout follows src/payload.c (m1n1): the runtime scans from
_payload_start, identifying each segment by magic:
  - kernel: raw Image (ARM64 magic at 0x38) or gzip stream
  - FDT: d00dfeed magic
  - initramfs: 'm1n1_initramfs' + u32le size + cpio (gz) bytes
  - vars: 'key=value' lines, newline-terminated (check_var)
Terminated with a zero pad (the scanner stops on zero words).

Usage:
  assemble_boot.py --m1n1 m1n1.bin --out stage1.bin \
      --var chainload=<PARTUUID>;/stage2.bin
  assemble_boot.py --m1n1 m1n1.bin --kernel Image.gz --dtb x.dtb \
      --initramfs initramfs.cpio.gz \
      --var chosen.bootargs="console=tty0 ..." --out stage2.bin
"""
import argparse
import struct
import sys

INITRAMFS_MAGIC = b"m1n1_initramfs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m1n1", required=True)
    ap.add_argument("--kernel")
    ap.add_argument("--dtb")
    ap.add_argument("--initramfs")
    ap.add_argument("--var", action="append", default=[],
                    help="key=value payload variable (repeatable)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    out = bytearray()
    out += open(a.m1n1, "rb").read()
    if a.kernel:
        out += open(a.kernel, "rb").read()
    if a.dtb:
        out += open(a.dtb, "rb").read()
    if a.initramfs:
        data = open(a.initramfs, "rb").read()
        out += INITRAMFS_MAGIC + struct.pack("<I", len(data)) + data
    for v in a.var:
        if "=" not in v or "\n" in v:
            sys.exit(f"bad var: {v!r}")
        out += (v + "\n").encode()
    out += b"\x00" * 4096

    open(a.out, "wb").write(out)
    print(f"{a.out}: {len(out)} bytes")


if __name__ == "__main__":
    main()
