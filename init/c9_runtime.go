package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const ansDevice = "4c5cc0000.nvme"
const ansDriver = "nvme-apple"

type resetObservation struct{ Controller, Error string }

var namespaceName = regexp.MustCompile(`^nvme[0-9]+n[0-9]+$`)
var controllerName = regexp.MustCompile(`^nvme[0-9]+$`)

func parseRuntimeLog(msg string, r *report) {
	// /dev/kmsg may append device metadata as continuation lines.
	msg = strings.TrimSpace(strings.SplitN(msg, "\n", 2)[0])
	if strings.HasPrefix(msg, "C9-R-BARRIER ") {
		r.Marker = msg
	}
	if strings.Contains(msg, "RTKDIAG mgmt tx type=") {
		fields := strings.Fields(msg)
		typ, request := "", ""
		for _, field := range fields {
			if strings.HasPrefix(field, "type=") {
				typ = strings.TrimPrefix(field, "type=")
			}
			if strings.HasPrefix(field, "msg=") {
				request = strings.TrimPrefix(field, "msg=")
			}
		}
		value, parseErr := strconv.ParseUint(request, 16, 64)
		r.MgmtSleepPending = typ == "6" && parseErr == nil && value&0xffff == 1
	}
	if strings.Contains(msg, "RTKDIAG mgmt tx ret=") && r.MgmtSleepPending {
		_, result, _ := strings.Cut(msg, "RTKDIAG mgmt tx ret=")
		if fields := strings.Fields(result); len(fields) != 0 {
			r.IOPSleepSend = fields[0]
		}
		r.MgmtSleepPending = false
	}
	if strings.Contains(msg, "nvme-apple "+ansDevice+":") && strings.Contains(msg, "ANSRM ") {
		if p := strings.Index(msg, "ANSRM "); p >= 0 {
			r.Teardown = strings.TrimSpace(msg[p+6:])
			switch {
			case strings.HasPrefix(r.Teardown, "shutdown prepare ret="):
				r.ShutdownPrepare = strings.TrimPrefix(r.Teardown, "shutdown prepare ret=")
			case strings.HasPrefix(r.Teardown, "cpu control="):
				var cpu, boot uint64
				if _, err := fmt.Sscanf(r.Teardown, "cpu control=%x boot=%x", &cpu, &boot); err == nil {
					r.CPUControl, r.BootStatus, r.CPUStateObserved = cpu, boot, true
				}
			case strings.HasPrefix(r.Teardown, "reinit ret="):
				r.ReinitResult = strings.TrimPrefix(r.Teardown, "reinit ret=")
			case r.Teardown == "genpd detach end":
				r.Teardown = "GENPD END"
			}
		}
	}
	if strings.Contains(msg, "RTKDIAG rx AP_PWR_ACK") {
		if parts := strings.SplitN(msg, "new_state=", 2); len(parts) == 2 {
			state, _, _ := strings.Cut(parts[1], " ")
			if state == "0x10" {
				r.APSleepAck = true
			}
		}
	}
	if strings.Contains(msg, "RTKDIAG rx IOP_PWR_ACK") {
		if parts := strings.SplitN(msg, "new_state=", 2); len(parts) == 2 {
			state, _, _ := strings.Cut(parts[1], " ")
			if state == "0x1" {
				r.IOPSleepAck = true
			}
			if state != "0x1" && r.BootIOPAck == "" {
				r.BootIOPAck = strings.ToUpper(state)
			}
		}
	}
	if strings.HasPrefix(msg, "nvme nvme") {
		prefix, body, ok := strings.Cut(msg, ":")
		name := strings.TrimPrefix(prefix, "nvme ")
		if ok && controllerName.MatchString(name) {
			if _, tail, found := strings.Cut(body, "Reset failure status: "); found {
				fields := strings.Fields(tail)
				if len(fields) > 0 {
					r.ResetObservations = append(r.ResetObservations, resetObservation{name, fields[0]})
					for _, known := range r.Controllers {
						if known == name {
							r.ResetError = fields[0]
						}
					}
				}
			}
		}
	}
	if strings.Contains(msg, "RTKTRACE begin") && strings.Contains(msg, "phase=teardown") {
		r.TraceSeen = true
		for _, field := range strings.Fields(msg) {
			if v, ok := strings.CutPrefix(field, "total="); ok {
				r.TraceTotal, _ = strconv.ParseInt(v, 10, 64)
			}
			if v, ok := strings.CutPrefix(field, "dropped="); ok {
				r.TraceDropped, _ = strconv.ParseInt(v, 10, 64)
			}
		}
	}
	if strings.Contains(msg, "RTKTRACE seq=") {
		var seq, ns int64
		var event, ep, msg0s string
		for _, field := range strings.Fields(msg) {
			switch {
			case strings.HasPrefix(field, "seq="):
				seq, _ = strconv.ParseInt(strings.TrimPrefix(field, "seq="), 10, 64)
			case strings.HasPrefix(field, "ns="):
				ns, _ = strconv.ParseInt(strings.TrimPrefix(field, "ns="), 10, 64)
			case strings.HasPrefix(field, "event="):
				event = strings.TrimPrefix(field, "event=")
			case strings.HasPrefix(field, "ep="):
				ep = strings.TrimPrefix(field, "ep=")
			case strings.HasPrefix(field, "msg0="):
				msg0s = strings.TrimPrefix(field, "msg0=")
			}
		}
		if value, perr := strconv.ParseUint(msg0s, 16, 64); perr == nil {
			mgmtType := (value >> 52) & 0xff
			switch {
			case event == "TX_BEGIN" && ep == "00" && mgmtType == 6 && value&0xffff == 1:
				r.SleepTxSeen = true
				r.SleepTxSeq = seq
				r.SleepTxNs = ns
			case event == "RX" && r.SleepTxSeen && seq > r.SleepTxSeq:
				r.PostSleepCount++
				token := "E" + strings.ToUpper(ep)
				if ep == "00" {
					token = fmt.Sprintf("E0T%d", mgmtType)
					if mgmtType == 7 && value&0xffff == 1 {
						r.SleepAckRing = true
					}
				}
				if ep == "01" && !r.CrashDeltaSeen {
					r.CrashDeltaSeen = true
					r.CrashDeltaMs = (ns - r.SleepTxNs) / 1000000
				}
				if len(r.PostSleepRx) < 6 {
					r.PostSleepRx = append(r.PostSleepRx, token)
				}
			}
		}
	}
	if !strings.Contains(msg, "nvme-apple "+ansDevice+":") {
		return
	}
	keep := false
	for _, tag := range []string{"ANSRST ", "ANSBR ", "ANSCHK ", "ANSRM ", "RTKDIAG ", "NVME-SNAP ", "co-processor has crashed", "RTKit crashed;"} {
		if strings.Contains(msg, tag) {
			keep = true
		}
	}
	if keep {
		if len(r.RuntimeLog) < 1024 {
			r.RuntimeLog = append(r.RuntimeLog, msg)
		} else {
			r.RuntimeLogDropped++
		}
	}
}

type runtimeFS struct{ sys, dev, proc string }
type runtimeTarget struct{ device, driver, physical string }
type runtimeNamespace struct{ name, path, id string }

func below(path, parent string) bool { return strings.HasPrefix(path, parent+string(os.PathSeparator)) }

func (fs runtimeFS) identify() (runtimeTarget, error) {
	device := filepath.Join(fs.sys, "bus/platform/devices", ansDevice)
	driver := filepath.Join(fs.sys, "bus/platform/drivers", ansDriver)
	physical, err := filepath.EvalSymlinks(device)
	if err != nil {
		return runtimeTarget{}, err
	}
	actual, err := filepath.EvalSymlinks(filepath.Join(device, "driver"))
	if err != nil {
		return runtimeTarget{}, err
	}
	want, err := filepath.EvalSymlinks(driver)
	if err != nil || actual != want {
		return runtimeTarget{}, fmt.Errorf("ANS DRIVER IDENTITY")
	}
	compatible, err := os.ReadFile(filepath.Join(device, "of_node/compatible"))
	if err != nil {
		return runtimeTarget{}, err
	}
	matched := false
	for _, s := range strings.Split(string(compatible), "\x00") {
		if s == "apple,t8132-nvme-ans2" {
			matched = true
		}
	}
	if !matched {
		return runtimeTarget{}, fmt.Errorf("ANS COMPATIBLE")
	}
	return runtimeTarget{device, driver, physical}, nil
}

func (fs runtimeFS) namespaces(target runtimeTarget) ([]runtimeNamespace, error) {
	entries, err := os.ReadDir(filepath.Join(fs.sys, "class/block"))
	if err != nil {
		return nil, err
	}
	var found []runtimeNamespace
	for _, entry := range entries {
		if !namespaceName.MatchString(entry.Name()) {
			continue
		}
		path, err := filepath.EvalSymlinks(filepath.Join(fs.sys, "class/block", entry.Name()))
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return nil, err
		}
		if below(path, target.physical) {
			found = append(found, runtimeNamespace{entry.Name(), filepath.Join(fs.dev, entry.Name()), readTrim(filepath.Join(fs.sys, "class/block", entry.Name(), "nsid"))})
		}
	}
	return found, nil
}

func selectNamespace(found []runtimeNamespace) (runtimeNamespace, bool, error) {
	var selected runtimeNamespace
	count := 0
	for _, ns := range found {
		if ns.id == "1" {
			selected = ns
			count++
		}
	}
	if count > 1 {
		return selected, false, fmt.Errorf("DUPLICATE NAMESPACE ID 1")
	}
	return selected, count == 1, nil
}

func (fs runtimeFS) controllers(target runtimeTarget) {
	entries, err := os.ReadDir(filepath.Join(fs.sys, "class/nvme"))
	if err != nil {
		return
	}
	for _, entry := range entries {
		if !controllerName.MatchString(entry.Name()) {
			continue
		}
		physical, err := filepath.EvalSymlinks(filepath.Join(fs.sys, "class/nvme", entry.Name()))
		if err != nil || !below(physical, target.physical) {
			continue
		}
		mu.Lock()
		exists := false
		for _, name := range current.Controllers {
			if name == entry.Name() {
				exists = true
			}
		}
		if !exists {
			current.Controllers = append(current.Controllers, entry.Name())
		}
		for _, observation := range current.ResetObservations {
			if observation.Controller == entry.Name() {
				current.ResetError = observation.Error
			}
		}
		mu.Unlock()
	}
}

func (fs runtimeFS) waitNamespace(target runtimeTarget, limit time.Duration) (runtimeNamespace, error) {
	deadline := time.Now().Add(limit)
	for {
		if time.Now().After(deadline) {
			return runtimeNamespace{}, fmt.Errorf("NO NAMESPACE")
		}
		fs.controllers(target)
		found, err := fs.namespaces(target)
		if err != nil {
			return runtimeNamespace{}, err
		}
		ns, exists, err := selectNamespace(found)
		if err != nil {
			return runtimeNamespace{}, err
		}
		if exists {
			size := readTrim(filepath.Join(fs.sys, "class/block", ns.name, "queue/logical_block_size"))
			if size == "" {
				time.Sleep(100 * time.Millisecond)
				continue
			}
			if size != "4096" {
				return ns, fmt.Errorf("BLOCK SIZE")
			}
			info, err := os.Stat(ns.path)
			if os.IsNotExist(err) {
				time.Sleep(100 * time.Millisecond)
				continue
			}
			if err != nil {
				return ns, err
			}
			if info.Mode()&os.ModeDevice == 0 || info.Mode()&os.ModeCharDevice != 0 {
				return ns, fmt.Errorf("NOT BLOCK DEVICE")
			}
			return ns, nil
		}
		time.Sleep(100 * time.Millisecond)
	}
}

func (fs runtimeFS) validateIdle(target runtimeTarget) error {
	entries, err := os.ReadDir(filepath.Join(fs.sys, "class/block"))
	if err != nil {
		return err
	}
	ids := map[string]bool{}
	for _, entry := range entries {
		base := filepath.Join(fs.sys, "class/block", entry.Name())
		path, err := filepath.EvalSymlinks(base)
		if err != nil {
			return err
		}
		if !below(path, target.physical) {
			continue
		}
		id := readTrim(filepath.Join(base, "dev"))
		if id == "" {
			return fmt.Errorf("BLOCK DEVICE ID")
		}
		ids[id] = true
		holders, err := os.ReadDir(filepath.Join(base, "holders"))
		if err != nil {
			return err
		}
		if len(holders) != 0 {
			return fmt.Errorf("ANS HAS HOLDERS")
		}
	}
	if len(ids) == 0 {
		return fmt.Errorf("NO ANS BLOCK DEVICES")
	}
	mounts, err := os.ReadFile(filepath.Join(fs.proc, "self/mountinfo"))
	if err != nil {
		return err
	}
	for _, line := range strings.Split(string(mounts), "\n") {
		fields := strings.Fields(line)
		if len(fields) > 2 && ids[fields[2]] {
			return fmt.Errorf("ANS IS MOUNTED")
		}
	}
	return nil
}

func (fs runtimeFS) checkUnbound(target runtimeTarget) error {
	_, err := os.Lstat(filepath.Join(target.device, "driver"))
	if !os.IsNotExist(err) {
		return fmt.Errorf("DRIVER STILL BOUND")
	}
	found, err := fs.namespaces(target)
	if err != nil {
		return err
	}
	if len(found) != 0 {
		return fmt.Errorf("OLD NAMESPACE REMAINS")
	}
	return nil
}

type pendingTimeout struct{ phase string }

func (e pendingTimeout) Error() string { return e.phase + " DEADLINE" }

// A deadline records uncertainty, not target cancellation. No later action is
// issued if the worker is still running.
func boundedAction(phase string, limit time.Duration, action func() error, observe func()) error {
	answer := make(chan error, 1)
	go func() { answer <- action() }()
	timer := time.NewTimer(limit)
	defer timer.Stop()
	tick := time.NewTicker(20 * time.Millisecond)
	defer tick.Stop()
	for {
		select {
		case err := <-answer:
			observe()
			return err
		case <-tick.C:
			observe()
		case <-timer.C:
			return pendingTimeout{phase}
		}
	}
}

func writeControl(path, value string) error {
	f, err := os.OpenFile(path, os.O_WRONLY, 0)
	if err != nil {
		return err
	}
	defer f.Close()
	n, err := f.WriteString(value)
	if err != nil {
		return err
	}
	if n != len(value) {
		return fmt.Errorf("SHORT CONTROL WRITE")
	}
	return nil
}

func barrierPayload(bootID, stage string) string {
	// Finalize the printk record immediately; an unfinished final record may
	// remain unreadable to /dev/kmsg until a later printk arrives.
	return "C9-R-BARRIER " + bootID + " " + stage + "\n"
}

func logBarrier(stage string) error {
	mu.Lock()
	payload := barrierPayload(current.BootID, stage)
	marker := strings.TrimSpace(payload)
	mu.Unlock()
	if err := boundedAction("LOG WRITE", 5*time.Second, func() error { return writeControl("/dev/kmsg", payload) }, func() {}); err != nil {
		return err
	}
	deadline := time.Now().Add(5 * time.Second)
	for {
		mu.Lock()
		seen, gap, dropped, failure := current.Marker == marker, current.KmsgGaps, current.RuntimeLogDropped, current.LogError
		mu.Unlock()
		if gap != 0 || dropped != 0 || failure != "" {
			return fmt.Errorf("LOG INCOMPLETE")
		}
		if seen {
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("LOG BARRIER DEADLINE")
		}
		time.Sleep(10 * time.Millisecond)
	}
}

func skipBeforeReads() bool {
	mu.Lock()
	defer mu.Unlock()
	return current.SkipReads
}

func runtimePhase(s string) { mu.Lock(); current.Phase = s; mu.Unlock() }

func directRuntime(ns runtimeNamespace, before bool) error {
	if before {
		runtimePhase("BEFORE READS")
	} else {
		runtimePhase("AFTER READS")
	}
	type answer struct {
		hashes  map[int64]string
		matched int
		err     error
	}
	ch := make(chan answer, 1)
	cancel := make(chan struct{})
	go func() { h, n, e := readBlocks(ns.path, expected, func(string) {}, cancel); ch <- answer{h, n, e} }()
	select {
	case result := <-ch:
		mu.Lock()
		if before {
			current.BeforeMatched, current.BeforeHashes = result.matched, result.hashes
		} else {
			current.Matched, current.Hashes = result.matched, result.hashes
		}
		mu.Unlock()
		return result.err
	case <-time.After(90 * time.Second):
		close(cancel)
		return pendingTimeout{"READ"}
	}
}

type runtimeStep struct {
	name   string
	action func() error
}

func executeRuntime(steps []runtimeStep) error {
	for _, step := range steps {
		runtimePhase(step.name)
		if err := step.action(); err != nil {
			return err
		}
	}
	return nil
}

func testRuntime() {
	fs := runtimeFS{"/sys", "/dev", "/proc"}
	var target runtimeTarget
	var before runtimeNamespace
	err := executeRuntime([]runtimeStep{
		{"IDENTIFY ANS", func() (err error) { target, err = fs.identify(); return }},
		{"WAIT BEFORE", func() (err error) {
			before, err = fs.waitNamespace(target, 45*time.Second)
			if err == nil {
				mu.Lock()
				current.Namespace = true
				current.BeforeNamespace = before.name
				mu.Unlock()
			}
			return
		}},
		{"BEFORE READS", func() error {
			if skipBeforeReads() {
				return nil
			}
			return directRuntime(before, true)
		}},
		{"CHECK BEFORE", func() error {
			if err := logBarrier("before"); err != nil {
				return err
			}
			mu.Lock()
			crashed, branch, reset := current.ANSCrash, current.Branch, current.ResetError
			mu.Unlock()
			if crashed || branch != "3" || reset != "" {
				return fmt.Errorf("WARM CONTROL FAILED")
			}
			return fs.validateIdle(target)
		}},
		{"UNBIND", func() error {
			err := boundedAction("UNBIND", 90*time.Second, func() error { return writeControl(filepath.Join(target.driver, "unbind"), ansDevice) }, func() { fs.controllers(target) })
			mu.Lock()
			if err == nil {
				current.UnbindResult = "OK"
			} else {
				current.UnbindResult = "ERR"
			}
			mu.Unlock()
			return err
		}},
		{"CHECK UNBOUND", func() error {
			if err := fs.checkUnbound(target); err != nil {
				return err
			}
			mu.Lock()
			current.Namespace = false
			mu.Unlock()
			if err := logBarrier("unbound"); err != nil {
				return err
			}
			mu.Lock()
			crashed := current.ANSCrash
			mu.Unlock()
			if crashed {
				return fmt.Errorf("CRASH DURING UNBIND")
			}
			return nil
		}},
		{"BIND", func() error {
			err := boundedAction("BIND", 90*time.Second, func() error { return writeControl(filepath.Join(target.driver, "bind"), ansDevice) }, func() { fs.controllers(target) })
			mu.Lock()
			if err == nil {
				current.BindResult = "OK"
			} else {
				current.BindResult = "ERR"
			}
			mu.Unlock()
			return err
		}},
		{"WAIT AFTER", func() error {
			after, err := fs.waitNamespace(target, 45*time.Second)
			if err != nil {
				return err
			}
			verified, err := fs.identify()
			if err != nil || verified.physical != target.physical {
				return fmt.Errorf("REBIND IDENTITY")
			}
			mu.Lock()
			current.Namespace = true
			current.AfterNamespace = after.name
			mu.Unlock()
			return directRuntime(after, false)
		}},
		{"CHECK AFTER", func() error {
			if err := logBarrier("after"); err != nil {
				return err
			}
			mu.Lock()
			crashed, reset := current.ANSCrash, current.ResetError
			mu.Unlock()
			if crashed || reset != "" {
				return fmt.Errorf("ANS RESTART ERROR")
			}
			return nil
		}},
	})
	mu.Lock()
	defer mu.Unlock()
	if err == nil {
		current.Status = "PASS"
		current.Phase = "READS MATCH"
		return
	}
	current.Status = "FAIL"
	current.Error = err.Error()
	if _, pending := err.(pendingTimeout); pending {
		current.Status = "INCONCLUSIVE"
	}
}
