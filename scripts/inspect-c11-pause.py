#!/usr/bin/env python3
"""Inspect an embedded C11 image over the proxy; optionally resume its scanner."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--proxyclient', type=Path,
                    default=Path('/home/btega/bootloader/proxyclient'))
    args = ap.parse_args()
    manifest = json.loads(args.manifest.read_text())
    image = Path(manifest['combined']['path']).read_bytes()
    if sha(image) != manifest['combined']['sha256']:
        raise ValueError('Changed host image')
    elf = Path(manifest['m1n1']['elf']).read_bytes()
    if sha(elf) != manifest['m1n1']['elf_sha256']:
        raise ValueError('Changed ELF')
    device = os.environ.get('M1N1DEVICE', '/dev/m1n1')
    if subprocess.run(['fuser', '-s', device]).returncode == 0:
        raise ValueError('Proxy already in use')
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.proxyclient))
    from m1n1.proxy import UartInterface, M1N1Proxy
    from m1n1.tgtypes import BootArgs_r1, BootArgs_r2, BootArgs_r3

    def deadline(signum, frame):
        raise TimeoutError('C11 inspection exceeded 30-second deadline')

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(30)
    iface = UartInterface(device)
    result = {'started_at': datetime.now().astimezone().isoformat(),
              'resumed': False, 'status': 'INSPECTING'}
    try:
        iface.nop()
        proxy = M1N1Proxy(iface, debug=False)
        base = proxy.get_base()
        phase = proxy.read64(base + manifest['symbols']['c11_boot_phase'])
        result.update(base=hex(base), phase=hex(phase))
        if phase != 0x43313101:
            raise ValueError('Target is not at the C11 pre-payload hold')
        ptr = proxy.get_bootargs()
        rev = int.from_bytes(iface.readmem(ptr, 2), 'little')
        layout = {0: BootArgs_r1, 1: BootArgs_r1, 2: BootArgs_r2, 3: BootArgs_r3}[rev]
        raw_args = iface.readmem(ptr, layout.sizeof())
        ba = layout.parse(raw_args)
        (args.output / 'bootargs.bin').write_bytes(raw_args)
        ram_end = ba.phys_base + (ba.mem_size_actual or ba.mem_size)
        offset = manifest['payload']['offset']
        size = manifest['payload']['bytes']
        start = base + offset
        if not (ba.phys_base <= base <= start < start + size <= ram_end):
            raise ValueError('Target payload outside reported DRAM')
        raw = iface.readmem(start, size)
        (args.output / 'payload.bin').write_bytes(raw)
        result.update(payload_start=hex(start), payload_end=hex(start + size),
                      payload_sha256=sha(raw),
                      payload_match=raw == image[offset:offset + size],
                      top_of_kernel_data=hex(ba.top_of_kernel_data),
                      image_end_below_top_of_kernel_data=base + len(image) <= ba.top_of_kernel_data)
        # The startup vectors contain no absolute relocations or mutable data.
        vectors = iface.readmem(base, 0x800)
        result['vectors_match'] = vectors == image[:0x800]
        result['phase_after_read'] = hex(proxy.read64(base + manifest['symbols']['c11_boot_phase']))
        if not result['payload_match'] or not result['vectors_match']:
            raise ValueError('Target image comparison failed; leaving hold active')
        result['status'] = 'HOLD_VERIFIED'
        (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2), flush=True)
        if args.resume:
            print('C11 sending P_EXIT to continue the embedded payload scanner', flush=True)
            proxy.exit()
            result['resumed'] = True
            signal.alarm(0)
            iface.dev.timeout = 0.25
            until = time.monotonic() + 20
            log = bytearray()
            try:
                while time.monotonic() < until:
                    block = iface.dev.read(4096)
                    if block:
                        log.extend(block)
                        print(block.decode('utf-8', errors='replace'), end='', flush=True)
            except Exception as exc:
                result['post_resume_transport_end'] = repr(exc)
            (args.output / 'resume-serial.bin').write_bytes(log)
            result['post_resume_log_sha256'] = sha(log)
            result['status'] = 'RESUMED_LINUX_RESULT_REQUIRES_SCREEN_OR_OPERATOR'
    except Exception as exc:
        result['status'] = 'FAILED'
        result['error'] = repr(exc)
        raise
    finally:
        signal.alarm(0)
        (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        iface.dev.close()


if __name__ == '__main__':
    main()
