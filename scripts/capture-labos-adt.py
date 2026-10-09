#!/usr/bin/env python3
"""Read LabOS proxy boot arguments and ADT; no boot, power or reset operations."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--proxyclient', type=Path, default=Path('/home/btega/bootloader/proxyclient'))
    ap.add_argument('--output', type=Path)
    ap.add_argument('--ans-text', action='store_true',
                    help='also read the ADT-identified ANS manifest and __TEXT DRAM segment')
    args = ap.parse_args()
    device = os.environ.get('M1N1DEVICE', '/dev/m1n1')
    if not Path(device).exists():
        ap.error(f'{device} is absent; first boot the Mac to a fresh LabOS Running proxy screen')
    if shutil.which('fuser') and subprocess.run(['fuser', '-s', device]).returncode == 0:
        ap.error(f'{device} is already in use; close the other serial client')
    sys.path.insert(0, str(args.proxyclient.resolve()))
    from m1n1.proxy import UartInterface, M1N1Proxy
    from m1n1.tgtypes import BootArgs_r1, BootArgs_r2, BootArgs_r3
    from m1n1.adt import load_adt

    output = args.output or Path('/home/btega/j604-boot/ans-review-n6miVhGq') / (
        'LABOS-ADT-' + datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z'))
    output.mkdir(parents=True, exist_ok=False)
    iface = UartInterface(device)
    try:
        # Avoid m1n1.setup / ProxyUtils: those also alter panic-counter/heap state.
        iface.nop()
        proxy = M1N1Proxy(iface, debug=False)
        bootargs_address = proxy.get_bootargs()
        prefix = iface.readmem(bootargs_address, 4)
        revision = int.from_bytes(prefix[:2], 'little')
        layouts = {0: BootArgs_r1, 1: BootArgs_r1, 2: BootArgs_r2, 3: BootArgs_r3}
        if revision not in layouts:
            raise ValueError(f'Unsupported bootargs revision {revision}')
        layout = layouts[revision]
        raw_args = iface.readmem(bootargs_address, layout.sizeof())
        ba = layout.parse(raw_args)
        adt_address = (ba.devtree - ba.virt_base + ba.phys_base) & ((1 << 64) - 1)
        ram_end = ba.phys_base + (ba.mem_size_actual or ba.mem_size)
        if not (0 < ba.devtree_size <= 16 * 1024 * 1024 and
                ba.phys_base <= adt_address < adt_address + ba.devtree_size <= ram_end):
            raise ValueError('ADT range is outside reported DRAM or exceeds size bound')
        raw_adt = iface.readmem(adt_address, ba.devtree_size)
        (output / 'bootargs.bin').write_bytes(raw_args)
        (output / 'adt.bin').write_bytes(raw_adt)
        # Raw capture is preserved even if the host's ADT decoder rejects a property.
        summary = {'captured_at': datetime.now().astimezone().isoformat(),
                   'device': device, 'bootargs_address': hex(bootargs_address),
                   'bootargs_revision': revision, 'adt_address': hex(adt_address),
                   'adt_bytes': len(raw_adt), 'adt_sha256': hashlib.sha256(raw_adt).hexdigest(),
                   'bootargs_sha256': hashlib.sha256(raw_args).hexdigest(),
                   'operations': ['proxy nop', 'get bootargs pointer', 'read bootargs DRAM', 'read ADT DRAM'],
                   'linux_payload_sent': False}
        (output / 'capture.json').write_text(json.dumps(summary, indent=2) + '\n')
        adt = load_adt(raw_adt)
        (output / 'adt.txt').write_text(str(adt) + '\n')
        if args.ans_text:
            dram_base = adt['/chosen'].getprop('dram-base')
            dram_size = adt['/chosen'].getprop('dram-size')
            if not isinstance(dram_base, int) or not isinstance(dram_size, int):
                raise ValueError('Explicit ADT DRAM bounds are required for ANS capture')

            def read_dram(address, size):
                if not (0 < size <= 16 * 1024 * 1024 and
                        dram_base <= address < address + size <= dram_base + dram_size):
                    raise ValueError('ANS capture range is outside explicit ADT DRAM bounds')
                return iface.readmem(address, size)

            pointer = adt['/chosen/boot-object-manifests'].getprop('ansf')
            if pointer is None or len(pointer) != 2:
                raise ValueError('ANS manifest pointer is missing or malformed')
            manifest = read_dram(*pointer)
            manifest_hash = hashlib.sha384(manifest).digest()
            expected = adt['/chosen/secure-boot-hashes'].getprop('ansf')
            if manifest_hash != expected:
                raise ValueError('ANS manifest bytes do not match chosen manifest hash')
            (output / 'ansf-manifest.der').write_bytes(manifest)
            nub = adt['/arm-io/ans/iop-ans-nub']
            if nub.getprop('running') != 1 or nub.getprop('pre-loaded') != 1:
                raise ValueError('ANS is not marked running and pre-loaded in ADT')
            names = nub.getprop('segment-names').split(';')
            ranges = nub.getprop('segment-ranges')
            if not isinstance(ranges, bytes) or len(ranges) != 32 * len(names):
                raise ValueError('ANS segment table does not match segment names')
            text_index = names.index('__TEXT')
            phys, iova, remap, size, unknown = struct.unpack_from('<QQQII', ranges, text_index * 32)
            text = read_dram(phys, size)
            (output / 'ans-text.bin').write_bytes(text)
            summary['ans_manifest_sha384'] = manifest_hash.hex()
            summary['ans_text'] = {'phys': hex(phys), 'iova': hex(iova), 'remap': hex(remap),
                                   'bytes': size, 'unknown': unknown,
                                   'sha256': hashlib.sha256(text).hexdigest()}
            summary['operations'] += ['read ADT-identified ANS manifest DRAM',
                                      'read ADT-identified ANS __TEXT DRAM']
            (output / 'capture.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(f'LabOS metadata saved: {output}')
        print(f'ADT SHA-256: {summary["adt_sha256"]}')
        print('Proxy remains available; no Linux payload sent.')
    finally:
        iface.dev.close()


if __name__ == '__main__':
    main()
