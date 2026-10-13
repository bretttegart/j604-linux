#!/usr/bin/env python3
"""Read a padded installed proxy and confirm its end marker; no boot or ANS ops."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--proxyclient', type=Path,
                    default=Path('/home/btega/bootloader/proxyclient'))
    args = ap.parse_args()
    manifest = json.loads(args.manifest.read_text())
    image = Path(manifest['combined']['path']).read_bytes()
    if hashlib.sha256(image).hexdigest() != manifest['combined']['sha256']:
        raise ValueError('Changed host image')
    device = os.environ.get('M1N1DEVICE', '/dev/m1n1')
    if subprocess.run(['fuser', '-s', device]).returncode == 0:
        raise ValueError('Proxy already in use')
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.proxyclient))
    from m1n1.proxy import UartInterface, M1N1Proxy
    from m1n1.tgtypes import BootArgs_r1, BootArgs_r2, BootArgs_r3

    def deadline(signum, frame):
        raise TimeoutError('C12 capture exceeded 30-second deadline')

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(30)
    result = {'captured_at': datetime.now().astimezone().isoformat(),
              'status': 'CAPTURING', 'linux_payload_sent': False,
              'ans_commands_issued': False}
    iface = UartInterface(device)
    try:
        iface.nop()
        proxy = M1N1Proxy(iface, debug=False)
        base = proxy.get_base()
        ptr = proxy.get_bootargs()
        rev = int.from_bytes(iface.readmem(ptr, 2), 'little')
        layout = {0: BootArgs_r1, 1: BootArgs_r1, 2: BootArgs_r2, 3: BootArgs_r3}[rev]
        raw_args = iface.readmem(ptr, layout.sizeof())
        ba = layout.parse(raw_args)
        (args.output / 'bootargs.bin').write_bytes(raw_args)
        ram_end = ba.phys_base + (ba.mem_size_actual or ba.mem_size)
        if not (ba.phys_base <= base < base + len(image) <= ram_end):
            raise ValueError('Image range outside reported DRAM')
        offset = manifest['padding']['offset']
        padding = iface.readmem(base + offset, len(image) - offset)
        (args.output / 'padding.bin').write_bytes(padding)
        vectors = iface.readmem(base, 0x800)
        result.update(base=hex(base), image_bytes=len(image),
                      image_end=hex(base + len(image)),
                      top_of_kernel_data=hex(ba.top_of_kernel_data),
                      padding_sha256=hashlib.sha256(padding).hexdigest(),
                      padding_match=padding == image[offset:],
                      end_marker_match=padding[-64:] == bytes.fromhex(
                          manifest['padding']['end_marker_hex']),
                      vectors_match=vectors == image[:0x800])
        if not all(result[k] for k in ('padding_match', 'end_marker_match', 'vectors_match')):
            raise ValueError('Installed size-control readback does not match')
        result['status'] = 'PASS_INSTALLED_PROXY_AND_COMPLETE_PADDING_READBACK'
        print(json.dumps(result, indent=2))
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
