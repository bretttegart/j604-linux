#!/usr/bin/env python3
"""Matched Linux preload; E5 retains a running m1n1 ANS after restart."""
import argparse
from datetime import datetime
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys


def sha(data):
    return hashlib.sha256(data).hexdigest()


def overlaps(a, length, b, size):
    return a < b + size and b < a + length


def symbols(elf):
    output = subprocess.check_output(["llvm-nm", "-P", str(elf)], text=True)
    result = {}
    for line in output.splitlines():
        fields = line.split()
        if fields and fields[0] in ("dt", "_base"):
            if fields[0] in result:
                raise ValueError("Ambiguous ELF symbol")
            result[fields[0]] = int(fields[2], 16)
    if result.get("_base") != 0 or "dt" not in result:
        raise ValueError("Expected relocatable raw ELF and dt pointer")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cell", choices=["L0", "L1", "P0", "P1", "R", "E1", "E3", "E5"], required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--proxyclient", type=Path, default=Path("/home/btega/bootloader/proxyclient"))
    args = ap.parse_args()
    cold = args.cell in ("L1", "P1")
    live = args.cell == "E5"
    manifest = json.loads(args.manifest.read_text())
    blobs = {name: Path(manifest[name]["path"]).read_bytes() for name in ("kernel", "dtb", "initramfs")}
    for name, raw in blobs.items():
        if sha(raw) != manifest[name]["sha256"]:
            raise ValueError(f"Changed input: {name}")
    image = gzip.decompress(blobs["kernel"])
    if image[0x38:0x3c] != b"ARM\x64" or len(image) >= 512*1024*1024:
        raise ValueError("Invalid/oversized ARM64 Image")
    elf = Path(manifest["m1n1"]["elf"])
    if sha(elf.read_bytes()) != manifest["m1n1"]["elf_sha256"]:
        raise ValueError("Changed m1n1 ELF")
    syms = symbols(elf)
    spec = importlib.util.spec_from_file_location("c9_restart", Path(__file__).with_name("run-c9-restart.py"))
    restart = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(restart)
    device = os.environ.get("M1N1DEVICE", "/dev/m1n1")
    if subprocess.run(["fuser", "-s", device]).returncode == 0:
        raise ValueError("Proxy already in use")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    sys.path.insert(0, str(args.proxyclient.resolve()))
    from m1n1.proxy import UartInterface, M1N1Proxy
    from m1n1.proxyutils import ProxyUtils, bootstrap_port
    from m1n1.sysreg import DAIF
    result = {"cell": args.cell, "started_at": datetime.now().astimezone().isoformat(),
              "status": "PREPARING", "disk_write_commands": 0, "regions": {}}
    phase = "connect"
    iface = None
    ram_start = ram_end = 0
    trace_pointer = 0

    def deadline(signum, frame):
        raise TimeoutError(f"Host deadline at {phase}; target code may still run")

    signal.signal(signal.SIGALRM, deadline)

    def call(label, fn, seconds=30):
        nonlocal phase
        phase=label
        (args.output/"phase.txt").write_text(label+"\n")
        print(f"C9 {args.cell} phase={label}", flush=True)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            return fn()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    def check_ram(address, size):
        if not (ram_start <= address < address+size <= ram_end):
            raise ValueError("Range outside DRAM")

    def save_trace(label):
        raw=call("trace-"+label, lambda: iface.readmem(trace_pointer,restart.STORE_BYTES))
        trace=restart.decode(raw)
        expected_variant = "C9-LOCAL-E5" if live else "C9-LOCAL"
        if trace["variant"]!=expected_variant or trace["event_dropped"] or trace["snapshot_dropped"]:
            raise ValueError("Wrong/overflowed capture")
        (args.output/f"trace-{label}.bin").write_bytes(raw)
        (args.output/f"trace-{label}.json").write_text(json.dumps(trace,indent=2)+"\n")
        return trace

    def fingerprint(label):
        hashes={}
        for name, region in result["regions"].items():
            data=call(f"{label}-{name}",lambda region=region:iface.readmem(region["address"],region["bytes"]),60)
            hashes[name]=sha(data)
        (args.output/f"payload-hashes-{label}.json").write_text(json.dumps(hashes,indent=2)+"\n")
        return hashes

    try:
        iface=call("connect", lambda:UartInterface(device))
        p=M1N1Proxy(iface,debug=False)
        call("bootstrap", lambda:bootstrap_port(iface,p))
        u=call("host-heap", lambda:ProxyUtils(p))
        ram_start=u.ba.phys_base;ram_end=ram_start+(u.ba.mem_size_actual or u.ba.mem_size)
        if u.adt["/arm-io/sart-ans"].getprop("sart-version")!=3 or u.adt["/arm-io/ans"].get_reg(0)[0]!=0x481600000:
            raise ValueError("Unexpected board resources")
        trace_pointer=call("trace-pointer",lambda:p.request(0xf04,0))
        check_ram(trace_pointer,restart.STORE_BYTES)
        trace=save_trace("preflight")
        if any(e["kind"]=="INIT_BEGIN" for e in trace["events"]):
            raise ValueError("NVMe already touched; fresh temporary image required")
        result["m1n1_base"]=hex(u.base)
        result["host_heap"]={"base":hex(u.heap_base),"end":hex(u.heap_top)}
        result["ans_manifest_hash_from_adt"]=u.adt["/chosen/secure-boot-hashes"].getprop("ansf").hex()
        cmdline=f"idle=nop nokaslr loglevel=8 console=tty0 fbcon=nodefer j604.test=C9-{args.cell}"
        result["cmdline"]=cmdline
        call("bootargs",lambda:p.kboot_set_chosen("bootargs",cmdline))
        compressed=u.malloc(len(blobs["kernel"]));check_ram(compressed,len(blobs["kernel"]))
        call("load-compressed-kernel",lambda:iface.writemem(compressed,blobs["kernel"],True),60)
        dtb=u.malloc(len(blobs["dtb"]));check_ram(dtb,len(blobs["dtb"]))
        call("load-dtb",lambda:iface.writemem(dtb,blobs["dtb"]))
        kernel=u.memalign(2*1024*1024,512*1024*1024);check_ram(kernel,512*1024*1024)
        initrd=u.memalign(65536,len(blobs["initramfs"]));check_ram(initrd,len(blobs["initramfs"]))
        call("load-initramfs",lambda:iface.writemem(initrd,blobs["initramfs"],True),60)
        call("initrd-pointer",lambda:p.kboot_set_initrd(initrd,len(blobs["initramfs"])))
        call("cpufreq",p.cpufreq_init)
        call("smp",p.smp_start_secondaries)
        if call("prepare-dt",lambda:p.kboot_prepare_dt(dtb))!=0:
            raise ValueError("DT preparation failed")
        length=call("decompress-kernel",lambda:p.gzdec(compressed,len(blobs["kernel"]),kernel,512*1024*1024),60)
        if length!=len(image):raise ValueError("Kernel decompression size mismatch")
        call("kernel-dcache",lambda:p.dc_cvau(kernel,length))
        call("kernel-icache",lambda:p.ic_ivau(kernel,length))
        dt_address=call("prepared-dt-pointer",lambda:p.read64(u.base+syms["dt"]))
        check_ram(dt_address,40)
        header=call("prepared-dt-header",lambda:iface.readmem(dt_address,40))
        if header[:4]!=b"\xd0\x0d\xfe\xed":raise ValueError("Invalid prepared FDT")
        dt_size=struct.unpack_from(">I",header,4)[0]
        if not (40<=dt_size<=1024*1024):raise ValueError("Invalid FDT length")
        check_ram(dt_address,dt_size)
        prepared=call("prepared-dt",lambda:iface.readmem(dt_address,dt_size))
        (args.output/"prepared.dtb").write_bytes(prepared)
        result["regions"]={"kernel":{"address":kernel,"bytes":length},
                           "initramfs":{"address":initrd,"bytes":len(blobs["initramfs"])},
                           "prepared-dtb":{"address":dt_address,"bytes":dt_size}}
        for name,a in result["regions"].items():
            for other,b in result["regions"].items():
                if name!=other and overlaps(a["address"],a["bytes"],b["address"],b["bytes"]):
                    raise ValueError("Overlapping payload components")
        buffer=call("dummy-read-buffer",lambda:p.memalign(16384,16384))
        check_ram(buffer,16384)
        # Identical allocation in both cells; only cold cells use the controller.
        result["read_buffer"]=hex(buffer)
        call("sart-before-cycle",lambda:p.request(0xf04,2,0))
        before=fingerprint("before-cycle")
        if before["kernel"]!=sha(image) or before["initramfs"]!=manifest["initramfs"]["sha256"]:
            raise ValueError("Payload readback differs from host inputs")
        if cold or live:
            ok=call("nvme-first-init",p.nvme_init,45)
            trace=save_trace("nvme-init")
            if ok!=1 or any(e["kind"]=="CRASH" for e in trace["events"]):
                raise ValueError("Pre-handoff NVMe init failed")
            for e in trace["events"]:
                if e["kind"] in ("QUEUE","MAP"):
                    for region in result["regions"].values():
                        if overlaps(e["a"],e["b"],region["address"],region["bytes"]):
                            raise ValueError("NVMe allocation overlaps a preloaded component")
            result["m1n1_reads"]={}
            for lba in (0,1,2,128,4096):
                sentinel=bytes([0xa5^(lba&255)])*4096
                call(f"sentinel-{lba}",lambda:iface.writemem(buffer,sentinel))
                if call(f"nvme-read-{lba}",lambda:p.nvme_read(1,lba,buffer))!=1:
                    raise ValueError("Pre-handoff NVMe read failed")
                block=call(f"readback-{lba}",lambda:iface.readmem(buffer,4096))
                digest=sha(block)
                if digest!=manifest["expected_read_hashes"][str(lba)]:raise ValueError("Pre-handoff block hash mismatch")
                result["m1n1_reads"][str(lba)]=digest
            call("nvme-shutdown",p.nvme_shutdown,45)
            trace=save_trace("nvme-shutdown")
            findings=restart.shutdown_findings(trace);result["shutdown"]=findings
            if not findings["pass"]:raise ValueError("Pre-handoff shutdown not proven")
            if live:
                if call("nvme-second-init",p.nvme_init,45)!=1:
                    raise ValueError("E5 restart init failed")
                trace=save_trace("nvme-second-init")
                if any(e["kind"]=="CRASH" for e in trace["events"]):
                    raise ValueError("E5 m1n1 restart crashed")
                retained=restart.buffer_ranges(trace)
                begin=max(i for i,e in enumerate(trace["events"]) if e["kind"]=="INIT_BEGIN")
                queue_events=[e for e in trace["events"][begin:] if e["kind"]=="QUEUE"]
                if len(queue_events)!=6:raise ValueError("E5 queue capture incomplete")
                retained += [(e["a"], (e["b"]+16383)&~16383) for e in queue_events]
                for a,n in retained:
                    check_ram(a,n)
                    if any(overlaps(a,n,r["address"],r["bytes"]) for r in result["regions"].values()):
                        raise ValueError("Retained ANS buffer overlaps payload")
                result["m1n1_restart_reads"]={}
                for lba in (0,1,2,128,4096):
                    call(f"restart-sentinel-{lba}",lambda:iface.writemem(buffer,bytes([0x5a^(lba&255)])*4096))
                    if call(f"restart-read-{lba}",lambda:p.nvme_read(1,lba,buffer))!=1:
                        raise ValueError("E5 restart read failed")
                    block=call(f"restart-readback-{lba}",lambda:iface.readmem(buffer,4096))
                    digest=sha(block)
                    if digest!=manifest["expected_read_hashes"][str(lba)]:
                        raise ValueError("E5 restart block hash mismatch")
                    result["m1n1_restart_reads"][str(lba)]=digest
                if call("nvme-live-quiesce",lambda:p.request(0xf05),45)!=1:
                    raise ValueError("E5 live quiesce rejected")
                trace=save_trace("live-quiesced")
                tail=trace["events"][begin:]
                if any(e["kind"] in ("CRASH","CPU_STOP","UNMAP","PMGR_BEFORE") for e in tail):
                    raise ValueError("E5 session was stopped, released, reset or crashed")
                for msgtype in (7,11):
                    if not any(e["kind"]=="RX" and e.get("endpoint")==0 and e.get("management_type")==msgtype and e.get("power_state")==0x10 for e in tail):
                        raise ValueError("Missing E5 QUIESCED ACK")
                if not any(e["kind"]=="LIVE_ARM" and e["result"]==1 for e in tail):
                    raise ValueError("E5 retention not armed")
                # Reprepare the FDT only after the current allocations exist.
                # Kernel/initrd must remain byte-identical; FDT gains reservations.
                intact=fingerprint("before-live-dt")
                if intact!=before:raise ValueError("E5 storage cycle altered payload")
                if call("prepare-live-dt",lambda:p.kboot_prepare_dt(dtb))!=0:
                    raise ValueError("E5 live DT preparation failed")
                dt_address=call("live-dt-pointer",lambda:p.read64(u.base+syms["dt"]))
                check_ram(dt_address,40)
                header=call("live-dt-header",lambda:iface.readmem(dt_address,40))
                if header[:4]!=b"\xd0\x0d\xfe\xed":raise ValueError("Invalid E5 FDT")
                dt_size=struct.unpack_from(">I",header,4)[0]
                if not (40<=dt_size<=1024*1024):raise ValueError("Invalid E5 FDT size")
                check_ram(dt_address,dt_size)
                prepared=call("live-dt-readback",lambda:iface.readmem(dt_address,dt_size))
                reserve_offset=struct.unpack_from(">I",prepared,16)[0]
                reservations=[]
                while reserve_offset+16<=len(prepared):
                    address,size=struct.unpack_from(">QQ",prepared,reserve_offset)
                    reserve_offset+=16
                    if address==size==0:break
                    reservations.append((address,size))
                else:raise ValueError("Unterminated E5 FDT reservations")
                if any(not any(b<=a and a+n<=b+m for b,m in reservations) for a,n in retained):
                    raise ValueError("E5 retained memory lacks FDT reservation")
                if any(overlaps(a,n,dt_address,dt_size) for a,n in retained):
                    raise ValueError("E5 retained buffer overlaps new FDT")
                (args.output/"prepared-before-live.dtb").write_bytes((args.output/"prepared.dtb").read_bytes())
                (args.output/"prepared.dtb").write_bytes(prepared)
                result["regions"]["prepared-dtb"]={"address":dt_address,"bytes":dt_size}
                result["retained_ranges"]=[{"address":hex(a),"bytes":n} for a,n in retained]
                result["retained_ranges_reserved"]=True
                trace=save_trace("live-reserved")
        else:
            trace=save_trace("no-storage-cycle")
            if any(e["kind"]=="INIT_BEGIN" for e in trace["events"]):raise ValueError("Warm control unexpectedly used NVMe")
        after=fingerprint("after-cycle")
        compared=("kernel","initramfs") if live else before.keys()
        if any(before[name]!=after[name] for name in compared):raise ValueError("Storage cycle changed a preloaded component")
        result["payload_readback_unchanged"]=True
        # Verify and document the final ANS decision state, outside reset.
        result["ans_cpu_control"]=call("ans-cpu-control",lambda:p.read32(0x481600044))
        result["ans_boot_status"]=call("ans-boot-status",lambda:p.read32(0x4c5cc1300))
        if not cold and (not(result["ans_cpu_control"]&0x10) or result["ans_boot_status"]!=0xde71ce55):raise ValueError("Warm control is not in the expected iBoot RUN/BOOT_STATUS state")
        if cold and result["ans_cpu_control"]&0x10:raise ValueError("Cold comparison CPU is running")
        (args.output/"pre-handoff.json").write_text(json.dumps(result,indent=2)+"\n")
        call("mask-interrupts",lambda:u.msr(DAIF,0xc0))
        result["status"]="HANDOFF_REQUESTED"
        (args.output/"host-result.json").write_text(json.dumps(result,indent=2)+"\n")
        try:
            # The convenience kboot_boot wrapper discards its request return.
            # Use the exact opcode to retain the acknowledged integer result.
            result["kboot_return"]=call("boot-linux",lambda:p.request(p.P_KBOOT_BOOT,kernel),45)
            result["status"]="BOOT_REQUEST_ACKNOWLEDGED" if result["kboot_return"]==0 else "HANDOFF_REJECTED"
        except Exception as error:
            result["host_handoff_note"]=f"{type(error).__name__}: {error}"
            # USB teardown is not a Linux outcome. Observe the Mac status frame.
        print("C9 handoff sent. Linux result must come from the fixed status screen.",flush=True)
    except Exception as error:
        result.update(status="HOST_PREPARATION_FAILED",phase=phase,error=f"{type(error).__name__}: {error}")
        print(result["error"],flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        if iface is not None:iface.dev.close()
        result["finished_at"]=datetime.now().astimezone().isoformat()
        (args.output/"host-result.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result,indent=2),flush=True)
    return 0 if result["status"] in ("HANDOFF_REQUESTED", "BOOT_REQUEST_ACKNOWLEDGED") else 1


if __name__=="__main__":
    raise SystemExit(main())
