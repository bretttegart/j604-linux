package main

import (
	"encoding/binary"
	"fmt"
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

func classify(msgs []string) (top, bot string) {
	var csts, status, snap string
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
		if i := strings.Index(m, "NVME-SNAP"); i >= 0 {
			snap = m[i:]
		}
	}
	if hasNS {
		return "NVME0N1", "OK"
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

func main() {
	go func() {
		time.Sleep(45 * time.Second)
		reboot()
	}()

	_ = syscall.Mount("proc", "/proc", "proc", 0, "")
	_ = syscall.Mount("sysfs", "/sys", "sysfs", 0, "")
	_ = syscall.Mount("devtmpfs", "/dev", "devtmpfs", 0, "")

	msgs := drainKmsg()
	time.Sleep(3 * time.Second)
	msgs = append(msgs, drainKmsg()...)
	top, bot := classify(msgs)

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
