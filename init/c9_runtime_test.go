package main

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

func put(t *testing.T, path, value string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(value), 0600); err != nil {
		t.Fatal(err)
	}
}
func link(t *testing.T, target, path string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, path); err != nil {
		t.Fatal(err)
	}
}
func fixture(t *testing.T) (runtimeFS, runtimeTarget) {
	t.Helper()
	root := t.TempDir()
	fs := runtimeFS{filepath.Join(root, "sys"), filepath.Join(root, "dev"), filepath.Join(root, "proc")}
	physical := filepath.Join(fs.sys, "devices/platform", ansDevice)
	driver := filepath.Join(fs.sys, "bus/platform/drivers", ansDriver)
	if err := os.MkdirAll(driver, 0755); err != nil {
		t.Fatal(err)
	}
	put(t, filepath.Join(physical, "of_node/compatible"), "apple,t8132-nvme-ans2\x00")
	link(t, driver, filepath.Join(physical, "driver"))
	link(t, physical, filepath.Join(fs.sys, "bus/platform/devices", ansDevice))
	if err := os.MkdirAll(filepath.Join(fs.sys, "class/block"), 0755); err != nil {
		t.Fatal(err)
	}
	put(t, filepath.Join(fs.proc, "self/mountinfo"), "1 0 0:1 / / rw - rootfs rootfs rw\n")
	target, err := fs.identify()
	if err != nil {
		t.Fatal(err)
	}
	return fs, target
}
func addNamespace(t *testing.T, fs runtimeFS, target runtimeTarget, name, id string) string {
	t.Helper()
	controller := name[:strings.LastIndex(name, "n")]
	path := filepath.Join(target.physical, "nvme", controller, name)
	put(t, filepath.Join(path, "dev"), id)
	put(t, filepath.Join(path, "nsid"), name[strings.LastIndex(name, "n")+1:])
	put(t, filepath.Join(path, "queue/logical_block_size"), "4096")
	if err := os.MkdirAll(filepath.Join(path, "holders"), 0755); err != nil {
		t.Fatal(err)
	}
	link(t, path, filepath.Join(fs.sys, "class/block", name))
	link(t, filepath.Dir(path), filepath.Join(fs.sys, "class/nvme", controller))
	return path
}

func TestNamespaceIdentityAndRenumbering(t *testing.T) {
	fs, target := fixture(t)
	old := addNamespace(t, fs, target, "nvme0n1", "259:0")
	foreign := filepath.Join(fs.sys, "devices/foreign/nvme8n1")
	put(t, filepath.Join(foreign, "dev"), "259:8")
	link(t, foreign, filepath.Join(fs.sys, "class/block/nvme8n1"))
	found, err := fs.namespaces(target)
	if err != nil || len(found) != 1 || found[0].name != "nvme0n1" {
		t.Fatalf("namespace %v %v", found, err)
	}
	if err := os.Remove(filepath.Join(fs.sys, "class/block/nvme0n1")); err != nil {
		t.Fatal(err)
	}
	if err := os.RemoveAll(old); err != nil {
		t.Fatal(err)
	}
	addNamespace(t, fs, target, "nvme7n1", "259:7")
	found, err = fs.namespaces(target)
	if err != nil || len(found) != 1 || found[0].name != "nvme7n1" {
		t.Fatalf("renumbering %v %v", found, err)
	}
}

func TestMultipleNamespacesSelectID1Only(t *testing.T) {
	fs, target := fixture(t)
	addNamespace(t, fs, target, "nvme0n2", "259:2")
	if err := os.Remove(filepath.Join(fs.sys, "class/nvme/nvme0")); err != nil {
		t.Fatal(err)
	}
	addNamespace(t, fs, target, "nvme0n1", "259:1")
	found, err := fs.namespaces(target)
	if err != nil || len(found) != 2 {
		t.Fatalf("discovery %v %v", found, err)
	}
	selected, exists, err := selectNamespace(found)
	if err != nil || !exists || selected.name != "nvme0n1" || selected.id != "1" {
		t.Fatalf("selection %v %v %v", selected, exists, err)
	}
	put(t, filepath.Join(fs.proc, "self/mountinfo"), "1 0 259:2 / /mnt rw - ext4 /dev/nvme0n2 rw\n")
	if err := fs.validateIdle(target); err == nil || err.Error() != "ANS IS MOUNTED" {
		t.Fatalf("other namespace mount %v", err)
	}
	if _, exists, err := selectNamespace(nil); err != nil || exists {
		t.Fatal("empty selection accepted")
	}
	if _, exists, err := selectNamespace([]runtimeNamespace{{id: "2"}}); err != nil || exists {
		t.Fatal("other namespace substituted")
	}
	if _, _, err := selectNamespace([]runtimeNamespace{{id: "1"}, {id: "1"}}); err == nil {
		t.Fatal("duplicate NSID accepted")
	}
}

func TestMountHolderAndDriverGates(t *testing.T) {
	fs, target := fixture(t)
	node := addNamespace(t, fs, target, "nvme0n1", "259:0")
	if err := fs.validateIdle(target); err != nil {
		t.Fatal(err)
	}
	partition := filepath.Join(node, "nvme0n1p1")
	put(t, filepath.Join(partition, "dev"), "259:1")
	if err := os.MkdirAll(filepath.Join(partition, "holders"), 0755); err != nil {
		t.Fatal(err)
	}
	link(t, partition, filepath.Join(fs.sys, "class/block/nvme0n1p1"))
	put(t, filepath.Join(fs.proc, "self/mountinfo"), "1 0 259:1 / /mnt rw - ext4 /dev/nvme0n1p1 rw\n")
	if err := fs.validateIdle(target); err == nil || err.Error() != "ANS IS MOUNTED" {
		t.Fatalf("mount gate %v", err)
	}
	put(t, filepath.Join(fs.proc, "self/mountinfo"), "")
	put(t, filepath.Join(node, "holders/dm-0"), "")
	if err := fs.validateIdle(target); err == nil || err.Error() != "ANS HAS HOLDERS" {
		t.Fatalf("holder gate %v", err)
	}
	put(t, filepath.Join(target.physical, "of_node/compatible"), "apple,other\x00")
	if _, err := fs.identify(); err == nil {
		t.Fatal("wrong compatibility accepted")
	}
}

func TestUnboundMustLoseDriverAndNamespace(t *testing.T) {
	fs, target := fixture(t)
	addNamespace(t, fs, target, "nvme0n1", "259:0")
	if err := fs.checkUnbound(target); err == nil {
		t.Fatal("bound device accepted")
	}
	if err := os.Remove(filepath.Join(target.device, "driver")); err != nil {
		t.Fatal(err)
	}
	if err := fs.checkUnbound(target); err == nil || err.Error() != "OLD NAMESPACE REMAINS" {
		t.Fatalf("old namespace %v", err)
	}
	if err := os.Remove(filepath.Join(fs.sys, "class/block/nvme0n1")); err != nil {
		t.Fatal(err)
	}
	if err := fs.checkUnbound(target); err != nil {
		t.Fatal(err)
	}
}

func TestDynamicControllerAttribution(t *testing.T) {
	fs, target := fixture(t)
	addNamespace(t, fs, target, "nvme7n1", "259:7")
	mu.Lock()
	current = report{Runtime: true}
	parseRuntimeLog("nvme nvme7: Reset failure status: -62", &current)
	if current.ResetError != "" {
		t.Fatal("unproven controller attributed")
	}
	mu.Unlock()
	fs.controllers(target)
	mu.Lock()
	defer mu.Unlock()
	if current.ResetError != "-62" || !reflect.DeepEqual(current.Controllers, []string{"nvme7"}) {
		t.Fatalf("controller attribution %+v", current)
	}
}

func TestTimeoutNeverQueuesBindOrRetry(t *testing.T) {
	blocked := make(chan struct{})
	done := make(chan struct{})
	calls := []string{}
	err := executeRuntime([]runtimeStep{
		{"before", func() error { calls = append(calls, "before"); return nil }},
		{"unbind", func() error {
			calls = append(calls, "unbind")
			return boundedAction("UNBIND", 5*time.Millisecond, func() error { <-blocked; close(done); return nil }, func() {})
		}},
		{"bind", func() error { calls = append(calls, "bind"); return nil }},
	})
	if _, ok := err.(pendingTimeout); !ok || !reflect.DeepEqual(calls, []string{"before", "unbind"}) {
		t.Fatalf("timeout %v %v", calls, err)
	}
	close(blocked)
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("worker did not finish")
	}
}

func TestFirstFailureStopsRemainingSteps(t *testing.T) {
	for failed := 0; failed < 6; failed++ {
		calls := 0
		var steps []runtimeStep
		for i := 0; i < 6; i++ {
			index := i
			steps = append(steps, runtimeStep{fmt.Sprint(i), func() error {
				calls++
				if index == failed {
					return fmt.Errorf("failure")
				}
				return nil
			}})
		}
		if err := executeRuntime(steps); err == nil || calls != failed+1 {
			t.Fatalf("failure index %d calls %d err %v", failed, calls, err)
		}
	}
}

func TestDirectReadFixtureMismatchAndCancellation(t *testing.T) {
	f, err := os.CreateTemp(t.TempDir(), "blocks")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err = f.Truncate(4097 * 4096); err != nil {
		t.Fatal(err)
	}
	hashes := map[int64]string{}
	for _, lba := range []int64{0, 1, 2, 128, 4096} {
		b := make([]byte, 4096)
		for i := range b {
			b[i] = byte(i*17 + int(lba))
		}
		if _, err = f.WriteAt(b, lba*4096); err != nil {
			t.Fatal(err)
		}
		hashes[lba] = fmt.Sprintf("%x", sha256.Sum256(b))
	}
	if err = f.Sync(); err != nil {
		t.Fatal(err)
	}
	_, n, err := readBlocks(f.Name(), hashes, func(string) {}, nil)
	if err != nil || n != 5 {
		t.Fatalf("direct reads %d %v", n, err)
	}
	if _, err = f.WriteAt(make([]byte, 4096), 128*4096); err != nil {
		t.Fatal(err)
	}
	if err = f.Sync(); err != nil {
		t.Fatal(err)
	}
	_, n, err = readBlocks(f.Name(), hashes, func(string) {}, nil)
	if err == nil || n != 3 || !strings.Contains(err.Error(), "LBA 128") {
		t.Fatalf("mismatch %d %v", n, err)
	}
	cancel := make(chan struct{})
	close(cancel)
	_, n, err = readBlocks(f.Name(), hashes, func(string) {}, cancel)
	if err == nil || n != 0 {
		t.Fatalf("cancel %d %v", n, err)
	}
}

func TestLogDeviceAndMarkerAttribution(t *testing.T) {
	r := report{Runtime: true}
	last := int64(-1)
	parseLog("6,1,100,-;rtkit-helper 394600000.mtp: RTKit: co-processor has crashed", &r, &last)
	parseLog("6,2,101,-;nvme-apple 4c5cc0000.nvme: ANSBR 2", &r, &last)
	parseLog("6,3,102,-;nvme-apple 4c5cc0000.nvme: RTKit: co-processor has crashed", &r, &last)
	parseLog("6,5,103,-;C9-R-BARRIER test before", &r, &last)
	if !r.ANSCrash || r.Branch != "2" || r.KmsgGaps != 1 || r.Marker != "C9-R-BARRIER test before" || len(r.RuntimeLog) != 2 {
		t.Fatalf("log %+v", r)
	}
}

func TestControlWriteDoesNotCreateMissingPath(t *testing.T) {
	path := filepath.Join(t.TempDir(), "missing")
	if err := writeControl(path, ansDevice); err == nil {
		t.Fatal("missing path written")
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatal("missing path created")
	}
}

func TestBarrierWritesFinalizedRecordAndMatchesReadback(t *testing.T) {
	path := filepath.Join(t.TempDir(), "kmsg-fixture")
	put(t, path, "")
	payload := barrierPayload("boot-id", "before")
	if err := writeControl(path, payload); err != nil {
		t.Fatal(err)
	}
	bytes, err := os.ReadFile(path)
	if err != nil || string(bytes) != "C9-R-BARRIER boot-id before\n" {
		t.Fatalf("unterminated marker %q %v", bytes, err)
	}
	r := report{Runtime: true}
	last := int64(-1)
	parseLog("14,1,100,-;"+string(bytes)+" SUBSYSTEM=platform\n DEVICE=fixture\n", &r, &last)
	if r.Marker != strings.TrimSpace(payload) {
		t.Fatalf("readback %q", r.Marker)
	}
}
