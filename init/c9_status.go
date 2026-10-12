package main

// C9 L0/L1: fixed framebuffer summary, aligned O_DIRECT reads, no disk writes.
import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

var expected = map[int64]string{
	0:    "2cc900b9134c8356277c7769603665459756fd13b4689e9efa4aaf427859d27f",
	1:    "7640546f91198e6828ed26fa01125f31d1b248cdedf07367745a1562b6401c92",
	2:    "8116d3799fec8e660c834b28302606d160308566a8169cfde5c3d223db7e357e",
	128:  "dcaef21864d55891725ab4985799fe231d960d882b1c0accfc91f5dda4daf4a2",
	4096: "d62b62a7ee8a9ab183ff7a9b838f0c28de1560671d67cc8b5af22805b7c712ad",
}

type report struct {
	Cell        string
	BootID      string
	Status      string
	Phase       string
	Namespace   bool
	Matched     int
	Hashes      map[int64]string
	Error       string
	Branch      string
	ANSCrash    bool
	ResetError  string
	KmsgRecords int
	KmsgGaps    int
	LogError    string
}

var mu sync.Mutex
var current report

func readTrim(path string) string {
	b, _ := os.ReadFile(path)
	return strings.TrimSpace(string(b))
}

func readBlocks(path string, hashes map[int64]string, progress func(string), cancelled <-chan struct{}) (map[int64]string, int, error) {
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_DIRECT, 0)
	if err != nil {
		return nil, 0, err
	}
	defer syscall.Close(fd)
	// Anonymous mmap is page aligned on the actual kernel (16 KiB on J604).
	buf, err := syscall.Mmap(-1, 0, 16384, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_PRIVATE|syscall.MAP_ANON)
	if err != nil {
		return nil, 0, err
	}
	defer syscall.Munmap(buf)
	if uintptr(unsafe.Pointer(&buf[0]))%4096 != 0 {
		return nil, 0, fmt.Errorf("unaligned buffer")
	}
	read := make(map[int64]string)
	matched := 0
	for _, lba := range []int64{0, 1, 2, 128, 4096} {
		select {
		case <-cancelled:
			return read, matched, fmt.Errorf("cancelled")
		default:
		}
		progress(fmt.Sprintf("READ LBA %d", lba))
		for i := range buf[:4096] {
			buf[i] = byte(i) ^ byte(lba) ^ 0xa5
		}
		n, err := syscall.Pread(fd, buf[:4096], lba*4096)
		if err != nil {
			return read, matched, err
		}
		if n != 4096 {
			return read, matched, fmt.Errorf("short direct read %d", n)
		}
		digest := fmt.Sprintf("%x", sha256.Sum256(buf[:4096]))
		read[lba] = digest
		if digest != hashes[lba] {
			return read, matched, fmt.Errorf("hash mismatch LBA %d", lba)
		}
		matched++
	}
	return read, matched, nil
}

func parseLog(rec string, r *report, last *int64) {
	i := strings.Index(rec, ";")
	if i < 0 {
		return
	}
	fields := strings.Split(rec[:i], ",")
	if len(fields) < 2 {
		return
	}
	seq, err := strconv.ParseInt(fields[1], 10, 64)
	if err != nil {
		return
	}
	if *last >= 0 && seq > *last+1 {
		r.KmsgGaps++
	}
	*last = seq
	r.KmsgRecords++
	msg := rec[i+1:]
	// ACK/crash attribution is explicit: MTP cannot set ANSCrash or Branch.
	if strings.Contains(msg, "nvme-apple 4c5cc0000.nvme:") {
		if strings.Contains(msg, "co-processor has crashed") {
			r.ANSCrash = true
		}
		if p := strings.Index(msg, "ANSBR "); p >= 0 {
			words := strings.Fields(msg[p+6:])
			if len(words) > 0 {
				r.Branch = words[0]
			}
		}
	}
	if strings.Contains(msg, "nvme nvme0:") {
		if p := strings.Index(msg, "Reset failure status: "); p >= 0 {
			words := strings.Fields(msg[p+22:])
			if len(words) > 0 {
				r.ResetError = words[0]
			}
		}
	}
}

func captureLog() {
	fd, err := syscall.Open("/dev/kmsg", syscall.O_RDONLY, 0)
	if err != nil {
		mu.Lock()
		current.LogError = err.Error()
		mu.Unlock()
		return
	}
	defer syscall.Close(fd)
	buf := make([]byte, 32768)
	last := int64(-1)
	for {
		n, err := syscall.Read(fd, buf)
		if n > 0 {
			mu.Lock()
			parseLog(string(buf[:n]), &current, &last)
			mu.Unlock()
		}
		if err == syscall.EPIPE {
			mu.Lock()
			current.KmsgGaps++
			mu.Unlock()
			continue
		}
		if err != nil {
			mu.Lock()
			current.LogError = err.Error()
			mu.Unlock()
			return
		}
	}
}

func testStorage() {
	deadline := time.Now().Add(45 * time.Second)
	for {
		if _, err := os.Stat("/dev/nvme0n1"); err == nil {
			break
		}
		if time.Now().After(deadline) {
			mu.Lock()
			current.Status = "FAIL"
			current.Phase = "NO NAMESPACE"
			current.Error = "NO NVME"
			mu.Unlock()
			return
		}
		time.Sleep(200 * time.Millisecond)
	}
	mu.Lock()
	current.Namespace = true
	current.Phase = "DIRECT READS"
	mu.Unlock()
	if readTrim("/sys/block/nvme0n1/queue/logical_block_size") != "4096" {
		mu.Lock()
		current.Status = "FAIL"
		current.Error = "BLOCK SIZE"
		mu.Unlock()
		return
	}
	type answer struct {
		hashes  map[int64]string
		matched int
		err     error
	}
	ch := make(chan answer, 1)
	cancel := make(chan struct{})
	go func() {
		h, n, e := readBlocks("/dev/nvme0n1", expected, func(p string) { mu.Lock(); current.Phase = p; mu.Unlock() }, cancel)
		ch <- answer{h, n, e}
	}()
	select {
	case a := <-ch:
		mu.Lock()
		current.Hashes = a.hashes
		current.Matched = a.matched
		if a.err != nil {
			current.Status = "FAIL"
			current.Error = a.err.Error()
		} else {
			current.Status = "PASS"
			current.Phase = "READS MATCH"
		}
		mu.Unlock()
	case <-time.After(90 * time.Second):
		close(cancel)
		mu.Lock()
		current.Status = "INCONCLUSIVE"
		current.Error = "READ DEADLINE"
		mu.Unlock()
	}
}

type framebuffer struct {
	memory                       []byte
	width, height, stride, pixel int
}

func openFramebuffer() (*framebuffer, error) {
	fd, err := syscall.Open("/dev/fb0", syscall.O_RDWR, 0)
	if err != nil {
		return nil, err
	}
	defer syscall.Close(fd)
	var fix [128]byte
	var variable [256]byte
	_, _, e := syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), 0x4602, uintptr(unsafe.Pointer(&fix[0])))
	if e != 0 {
		return nil, e
	}
	_, _, e = syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), 0x4600, uintptr(unsafe.Pointer(&variable[0])))
	if e != 0 {
		return nil, e
	}
	w := int(binary.LittleEndian.Uint32(variable[0:4]))
	h := int(binary.LittleEndian.Uint32(variable[4:8]))
	bpp := int(binary.LittleEndian.Uint32(variable[24:28]))
	length := int(binary.LittleEndian.Uint32(fix[24:28]))
	stride := int(binary.LittleEndian.Uint32(fix[48:52]))
	pixel := bpp / 8
	if w < 100 || h < 100 || w > 8192 || h > 8192 || (pixel != 2 && pixel != 4) || stride < w*pixel || length < stride*h || length > 256*1024*1024 {
		return nil, fmt.Errorf("invalid framebuffer")
	}
	mem, err := syscall.Mmap(fd, 0, length, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_SHARED)
	if err != nil {
		return nil, err
	}
	return &framebuffer{mem, w, h, stride, pixel}, nil
}

func (fb *framebuffer) paint(lines []string) {
	for i := range fb.memory {
		fb.memory[i] = 0
	}
	scale := (fb.height - 120) / (len(lines) * 10)
	for _, line := range lines {
		if n := (fb.width - 120) / (len(line) * 6); n < scale {
			scale = n
		}
	}
	if scale < 1 {
		scale = 1
	}
	for line, text := range lines {
		for column, ch := range []byte(strings.ToUpper(text)) {
			glyph := font[ch]
			for row := 0; row < 7; row++ {
				for col := 0; col < 5; col++ {
					if glyph[row]&(1<<uint(4-col)) == 0 {
						continue
					}
					for dy := 0; dy < scale; dy++ {
						for dx := 0; dx < scale; dx++ {
							x := 60 + column*6*scale + col*scale + dx
							y := 60 + line*10*scale + row*scale + dy
							if x >= fb.width || y >= fb.height {
								continue
							}
							off := y*fb.stride + x*fb.pixel
							for b := 0; b < fb.pixel; b++ {
								fb.memory[off+b] = 0xff
							}
						}
					}
				}
			}
		}
	}
}

func lines(r report) []string {
	status := r.Status
	if r.ANSCrash && status == "PASS" {
		status = "FAIL LATE ANS CRASH"
	}
	branch := r.Branch
	if branch == "" {
		branch = "NA"
	}
	crash := "NO"
	if r.ANSCrash {
		crash = "YES"
	}
	err := r.Error
	if err == "" {
		err = "NONE"
	}
	if len(err) > 40 {
		err = err[:40]
	}
	boot := r.BootID
	if len(boot) > 8 {
		boot = boot[:8]
	}
	ns := "NO"
	if r.Namespace {
		ns = "YES"
	}
	reset := r.ResetError
	if reset == "" {
		reset = "NONE"
	}
	return []string{r.Cell, status, fmt.Sprintf("DIRECT MATCH %d OF 5", r.Matched), "NAMESPACE " + ns, "ANS BR " + branch, "ANS CRASH " + crash, "RESET " + reset, "BOOT " + boot, "PHASE " + r.Phase, "ERROR " + err}
}

func main() {
	for _, path := range []string{"/proc", "/sys", "/dev", "/run"} {
		_ = os.MkdirAll(path, 0755)
	}
	for _, m := range [][3]string{{"proc", "/proc", "proc"}, {"sysfs", "/sys", "sysfs"}, {"devtmpfs", "/dev", "devtmpfs"}, {"tmpfs", "/run", "tmpfs"}} {
		_ = syscall.Mount(m[0], m[1], m[2], 0, "")
	}
	cell := "C9 UNLABELED"
	for _, word := range strings.Fields(readTrim("/proc/cmdline")) {
		if value, ok := strings.CutPrefix(word, "j604.test="); ok {
			cell = strings.ReplaceAll(value, "-", " ")
		}
	}
	current = report{Cell: cell, BootID: readTrim("/proc/sys/kernel/random/boot_id"), Status: "WAIT", Phase: "WAIT NAMESPACE"}
	go captureLog()
	go testStorage()
	tty, _ := syscall.Open("/dev/tty0", syscall.O_RDWR, 0)
	if tty >= 0 {
		_, _, _ = syscall.Syscall(syscall.SYS_IOCTL, uintptr(tty), 0x4b3a, 1)
	}
	fb, fbErr := openFramebuffer()
	if fbErr != nil && tty >= 0 {
		_, _, _ = syscall.Syscall(syscall.SYS_IOCTL, uintptr(tty), 0x4b3a, 0)
	}
	for {
		mu.Lock()
		r := current
		mu.Unlock()
		if r.ANSCrash && r.Status == "PASS" {
			r.Status = "FAIL LATE ANS CRASH"
		}
		// JSON is on initramfs/tmpfs only. No internal partition is mounted.
		b, _ := json.MarshalIndent(r, "", "  ")
		_ = os.WriteFile("/run/c9-result.json", b, 0600)
		if fbErr == nil {
			fb.paint(lines(r))
		} else {
			fmt.Println(strings.Join(lines(r), " | "))
		}
		time.Sleep(2 * time.Second)
	}
}

var font = map[byte][7]uint8{
	' ': {0, 0, 0, 0, 0, 0, 0},
	'0': {0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110},
	'1': {0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110},
	'2': {0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111},
	'3': {0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110},
	'4': {0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010},
	'5': {0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110},
	'6': {0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110},
	'7': {0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000},
	'8': {0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110},
	'9': {0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100},
	'A': {0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001},
	'B': {0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110},
	'C': {0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110},
	'D': {0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110},
	'E': {0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111},
	'F': {0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000},
	'G': {0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110},
	'I': {0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110},
	'K': {0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001},
	'L': {0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111},
	'M': {0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001},
	'N': {0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001},
	'O': {0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110},
	'R': {0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001},
	'S': {0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110},
	'T': {0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100},
	'V': {0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b01010, 0b00100},

	'H': {0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001},
	'P': {0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000},
	'Q': {0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101},
	'U': {0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110},
	'W': {0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010},
	'X': {0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001},
	'Y': {0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100},
	'Z': {0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111},
	'-': {0, 0, 0, 0b11111, 0, 0, 0},
	'/': {0b00001, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b10000},
}
