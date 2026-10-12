#!/bin/sh
# RAM-only development shell. Internal block devices start read-only.
BB=/bin/busybox
export PATH=/bin TERM=linux HOME=/root
export PS1='j604# '
$BB mount -t proc proc /proc
$BB mount -t sysfs sysfs /sys
$BB mount -t devtmpfs devtmpfs /dev
$BB --install -s /bin
$BB dmesg -n 2
[ ! -f /etc/console.psf ] || $BB setfont -C /dev/tty1 /etc/console.psf

count=0
while [ ! -b /dev/nvme0n1 ] && [ "$count" -lt 45 ]; do
    $BB sleep 1
    count=$((count + 1))
done
readonly_ok=yes
for disk in /dev/nvme*n*; do
    [ -b "$disk" ] || continue
    $BB blockdev --setro "$disk" || readonly_ok=no
    [ "$($BB blockdev --getro "$disk")" = 1 ] || readonly_ok=no
done
/bin/ans-check > /run/ans-check.txt 2>&1
check_status=$?
$BB dmesg > /run/boot-kmsg.txt
$BB clear
printf '\nJ604 C10 embedded Linux shell\n'
printf 'Boot ID: '; $BB cat /proc/sys/kernel/random/boot_id
printf 'NVMe read-only setup: %s\n' "$readonly_ok"
printf 'Storage check exit: %s\n\n' "$check_status"
$BB cat /run/ans-check.txt
printf '\nCommands: ans-check, dmesg, ls /dev/nvme*, cat /proc/meminfo\n'
printf 'Logs: /run/boot-kmsg.txt and /run/ans-check.txt (RAM)\n'
printf 'Internal partitions are not mounted. Exiting restarts the shell.\n\n'
while :; do
    $BB setsid -c /bin/sh -i </dev/tty1 >/dev/tty1 2>&1
    printf '\nRestarting shell...\n'
done
