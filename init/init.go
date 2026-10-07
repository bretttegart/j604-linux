package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

func reboot() {
	syscall.Syscall(syscall.SYS_REBOOT, 0xfee1dead, 672274793, 0x01234567)
}

func drainKmsg() []string {
	fd, err := syscall.Open("/dev/kmsg", syscall.O_RDONLY|syscall.O_NONBLOCK, 0)
	if err != nil {
		return nil
	}
	defer syscall.Close(fd)
	buf := make([]byte, 16384)
	var msgs []string
	for nread := 0; nread < 20000; nread++ {
		n, err := syscall.Read(fd, buf)
		if n > 0 {
			rec := string(buf[:n])
			if i := strings.Index(rec, ";"); i >= 0 {
				msgs = append(msgs, rec[i+1:])
			}
		}
		if n <= 0 || err == syscall.EAGAIN || err == syscall.EWOULDBLOCK {
			break
		}
		if err != nil {
			break
		}
	}
	return msgs
}

func token(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexAny(s, " \t\r\n"); i >= 0 {
		s = s[:i]
	}
	return s
}

func field(s, key string) string {
	i := strings.Index(s, key)
	if i < 0 {
		return ""
	}
	return strings.TrimPrefix(strings.TrimPrefix(token(s[i+len(key):]), "0x"), "0X")
}


// nvmeReadTest validates block I/O on /dev/nvme0n1: reads LBA1 and
// checks for the GPT header signature "EFI PART". Read-only on
// purpose: every sector of this disk belongs to APFS containers,
// so no sector is safe to scratch-write until R5 carves one out.
func nvmeReadTest() string {
	var fd int
	var err error
	for i := 0; i < 20; i++ {
		fd, err = syscall.Open("/dev/nvme0n1", syscall.O_RDONLY, 0)
		if err == nil {
			break
		}
		time.Sleep(100 * time.Millisecond)
	}
	if err != nil {
		return "RDFAIL"
	}
	defer syscall.Close(fd)
	// Apple ANS presents 4Kn sectors, so the GPT header (LBA1) sits
	// at byte 4096, not 512. Scan both offsets.
	for _, off := range []int64{4096, 512} {
		buf := make([]byte, 512)
		if _, err := syscall.Pread(fd, buf, off); err != nil {
			return "RDFAIL"
		}
		if string(buf[:8]) == "EFI PART" {
			return "RDOK"
		}
	}
	return "RDNG"
}

func classify(msgs []string) (top, bot string) {
	var csts, status, snap, snap2 string
	var anskCPU, anskBST, anskBR string
	hasNS, hasANS, hasInit, hasRT := false, false, false, false
	for _, m := range msgs {
		if strings.Contains(m, "nvme0n1") {
			hasNS = true
		}
		if strings.Contains(m, "ANS did not boot") {
			hasANS = true
		}
		if strings.Contains(m, "ANS did not initialize") {
			hasInit = true
		}
		if strings.Contains(m, "RTKit crashed") {
			hasRT = true
		}
		if i := strings.Index(m, "CSTS="); i >= 0 {
			csts = token(m[i+5:])
		}
		if i := strings.Index(m, "Reset failure status:"); i >= 0 {
			status = token(m[i+len("Reset failure status:"):])
		}
		if i := strings.Index(m, "ANSCHK cpu="); i >= 0 {
			f := m[i:]
			anskCPU = field(f, "cpu=")
			anskBST = field(f, "bst=")
		}
		if strings.Contains(m, "ANSBR 2") {
			anskBR = "2"
		}
		if strings.Contains(m, "ANSBR 3") {
			anskBR = "3"
		}
		if i := strings.Index(m, "NVME-SNAP2"); i >= 0 {
			snap2 = m[i:]
		} else if i := strings.Index(m, "NVME-SNAP"); i >= 0 {
			snap = m[i:]
		}
	}
	if hasNS {
		return "NVME0N1", nvmeReadTest()
	}
	if snap2 != "" {
		cc2 := field(snap2, "cc=")
		cst2 := field(snap2, "csts=")
		if cc2 == "" {
			cc2 = "NA"
		}
		if cst2 == "" {
			cst2 = "NA"
		}
		return "CC2 " + cc2, "CSTS " + cst2
	}
	if anskCPU != "" {
		br := anskBR
		if br == "" {
			br = "0"
		}
		bst4 := anskBST
		if len(bst4) > 4 {
			bst4 = bst4[:4]
		}
		return "BR" + br + " B" + bst4, "C" + anskCPU
	}
	errn := strings.TrimPrefix(status, "-")
	if hasANS {
		if errn == "" {
			errn = "ETIME"
		}
		return "ANS BOOT", errn
	}
	if hasInit {
		if errn == "" {
			errn = "FAIL"
		}
		return "ANS INIT", errn
	}
	if hasRT {
		return "RTKIT", "CRASH"
	}
	if snap != "" {
		boot := field(snap, "boot=")
		if boot == "" {
			boot = "NA"
		}
		if cc := field(snap, "cc="); cc != "" {
			return "BOOT " + boot, "CC " + cc
		}
		sart := field(snap, "sart=")
		cst := field(snap, "csts=")
		if sart == "" {
			sart = "NA"
		}
		if cst == "" {
			cst = "NA"
		}
		return "BOOT " + boot, "SART " + sart + " CSTS " + cst
	}
	if csts != "" {
		hex := strings.TrimPrefix(strings.TrimPrefix(csts, "0x"), "0X")
		if errn == "" {
			errn = "NA"
		}
		return "CSTS " + hex, "ERR " + errn
	}
	return "NO NVME", "MISS"
}

// 5-wide glyphs. Bit 4 is the left pixel.
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
}

func paint(top, bot string) error {
	fd, err := syscall.Open("/dev/fb0", syscall.O_RDWR, 0)
	if err != nil {
		return err
	}
	defer syscall.Close(fd)

	var fix [128]byte
	var vinfo [256]byte
	_, _, errno := syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), 0x4602, uintptr(unsafe.Pointer(&fix[0])))
	if errno != 0 {
		return errno
	}
	_, _, errno = syscall.Syscall(syscall.SYS_IOCTL, uintptr(fd), 0x4600, uintptr(unsafe.Pointer(&vinfo[0])))
	if errno != 0 {
		return errno
	}
	xres := int(binary.LittleEndian.Uint32(vinfo[0:4]))
	yres := int(binary.LittleEndian.Uint32(vinfo[4:8]))
	bpp := int(binary.LittleEndian.Uint32(vinfo[24:28]))
	smemLen := int(binary.LittleEndian.Uint32(fix[24:28]))
	lineLen := int(binary.LittleEndian.Uint32(fix[48:52]))
	if xres < 100 || yres < 100 || lineLen < xres || smemLen < lineLen*yres {
		return fmt.Errorf("fb %dx%d bpp %d stride %d len %d", xres, yres, bpp, lineLen, smemLen)
	}
	pix := 4
	if bpp <= 16 {
		pix = 2
	}
	fb, err := syscall.Mmap(fd, 0, smemLen, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_SHARED)
	if err != nil {
		return err
	}
	defer syscall.Munmap(fb)
	for i := range fb {
		fb[i] = 0
	}

	draw := func(text string, y0, scale int) {
		text = strings.ToUpper(text)
		unit := 6 * scale
		width := len(text) * unit
		x0 := (xres - width) / 2
		if x0 < 0 {
			x0 = 0
		}
		for i, ch := range []byte(text) {
			g, ok := font[ch]
			if !ok {
				continue
			}
			for row := 0; row < 7; row++ {
				for col := 0; col < 5; col++ {
					if g[row]&(1<<(4-uint(col))) == 0 {
						continue
					}
					px := x0 + i*unit + col*scale
					py := y0 + row*scale
					for dy := 0; dy < scale; dy++ {
						for dx := 0; dx < scale; dx++ {
							x := px + dx
							y := py + dy
							if x < 0 || y < 0 || x >= xres || y >= yres {
								continue
							}
							off := y*lineLen + x*pix
							if off < 0 || off+pix > len(fb) {
								continue
							}
							for b := 0; b < pix; b++ {
								fb[off+b] = 0xff
							}
						}
					}
				}
			}
		}
	}

	scale := 64
	for _, s := range []string{top, bot} {
		if w := len(s) * 6 * scale; w > xres-80 && len(s) > 0 {
			scale = (xres - 80) / (len(s) * 6)
		}
	}
	if scale < 20 {
		scale = 20
	}
	block := 7 * scale
	gap := scale
	total := block*2 + gap
	y0 := (yres - total) / 2
	draw(top, y0, scale)
	draw(bot, y0+block+gap, scale)
	return nil
}

func holdConsole(line string) {
	deadline := time.Now().Add(18 * time.Second)
	for time.Now().Before(deadline) {
		fmt.Println(line)
		time.Sleep(2 * time.Second)
	}
}

func diagLines(msgs []string) []string {
	keys := []string{"RTKit", "rtkit", "ANS", "nvme", "NVMe", "sart", "SART", "mailbox", "apple-"}
	var out []string
	for _, m := range msgs {
		hit := false
		for _, k := range keys {
			if strings.Contains(m, k) {
				hit = true
				break
			}
		}
		if !hit {
			continue
		}
		if i := strings.Index(m, ";"); i >= 0 {
			m = m[i+1:]
		}
		if len(m) > 76 {
			m = m[:76]
		}
		out = append(out, m)
	}
	if len(out) > 45 {
		out = out[len(out)-45:]
	}
	return out
}

var pstoreStatus string

func pstoreDiag() bool {
	pstoreStatus = "STO ERR"
	_ = syscall.Mount("pstore", "/sys/fs/pstore", "pstore", 0, "")
	entries, err := os.ReadDir("/sys/fs/pstore")
	if err != nil {
		return false
	}
	nConsole := 0
	keys := []string{"RTKit", "ANS", "nvme", "sart", "crashlog", "SART", "mailbox"}
	var out []string
	failed := false
	for _, e := range entries {
		if !strings.HasPrefix(e.Name(), "console-ramoops") {
			continue
		}
		nConsole++
		data, err := os.ReadFile("/sys/fs/pstore/" + e.Name())
		if err != nil {
			continue
		}
		text := string(data)
		if strings.Contains(text, "RTKit crashed") ||
			strings.Contains(text, "ANS did not boot") ||
			strings.Contains(text, "Reset failure status:") {
			failed = true
		}
		for _, line := range strings.Split(text, "\n") {
			hit := false
			for _, k := range keys {
				if strings.Contains(line, k) {
					hit = true
					break
				}
			}
			if hit {
				out = append(out, line)
			}
		}
	}
	fInt := 0
	if failed {
		fInt = 1
	}
	pstoreStatus = fmt.Sprintf("STO %d C %d F %d", len(entries), nConsole, fInt)
	if !failed || len(out) == 0 {
		return false
	}
	if len(out) > 55 {
		out = out[len(out)-55:]
	}
	tty, err := syscall.Open("/dev/tty0", syscall.O_RDWR, 0)
	if err != nil {
		return false
	}
	_, _, _ = syscall.Syscall(syscall.SYS_IOCTL, uintptr(tty), 0x4B3A, 0)
	f := os.NewFile(uintptr(tty), "tty0")
	fmt.Fprintf(f, "\n===== PSTORE DIAG =====\n")
	for _, l := range out {
		fmt.Fprintln(f, l)
	}
	fmt.Fprintf(f, "===== END PSTORE =====\n")
	return true
}

func main() {
	_ = syscall.Mount("proc", "/proc", "proc", 0, "")
	_ = syscall.Mount("sysfs", "/sys", "sysfs", 0, "")
	_ = syscall.Mount("devtmpfs", "/dev", "devtmpfs", 0, "")

	if pstoreDiag() {
		select {}
	}

	msgs := drainKmsg()
	time.Sleep(3 * time.Second)
	msgs = append(msgs, drainKmsg()...)
	top, bot := classify(msgs)

	if strings.HasPrefix(top, "BR") {
		tty2, err2 := syscall.Open("/dev/tty0", syscall.O_RDWR, 0)
		if err2 == nil {
			_, _, _ = syscall.Syscall(syscall.SYS_IOCTL, uintptr(tty2), 0x4B3A, 0)
			f := os.NewFile(uintptr(tty2), "tty0")
			fmt.Fprintf(f, "\n===== KMSG DIAG =====\n")
			for _, l := range diagLines(msgs) {
				fmt.Fprintln(f, l)
			}
			fmt.Fprintf(f, "===== END KMSG =====\n")
		}
		select {}
	}
	if pstoreStatus != "" {
		bot = strings.TrimSpace(bot + " " + pstoreStatus)
	}

	tty, err := syscall.Open("/dev/tty0", syscall.O_RDWR, 0)
	if err == nil {
		_, _, _ = syscall.Syscall(syscall.SYS_IOCTL, uintptr(tty), 0x4B3A, 1)
	}

	if err := paint(top, bot); err != nil {
		if tty >= 0 {
			_, _, _ = syscall.Syscall(syscall.SYS_IOCTL, uintptr(tty), 0x4B3A, 0)
		}
		holdConsole("===== " + top + " / " + bot + " =====")
		reboot()
		return
	}
	time.Sleep(18 * time.Second)
	reboot()
}
