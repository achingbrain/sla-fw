#!/bin/bash

BOOT="/mnt/usb/"
SYS="/mnt/rootfs/"
EXC="/usr/share/sl1fw/scripts/exclude.txt"

PT1="/mnt/pt1"
PT2="/mnt/pt2"

die() {
	echo "$0[$$] ERROR: $@ failed" >&2
	exit 1
}

mkdir -p "$PT1" "$PT2" || die "mkdir"
mount -o bind "/boot" "$PT1" || die "mount boot"
mount -o bind "/" "$PT2" || die "mount root"
rsync -aAHXS --del --info=progress2 "$BOOT" "$PT1" || die "rsync boot"
rsync -aAHXS --del --exclude-from="$EXC" --info=progress2 "$SYS" "$PT2" || die "rsync root"
umount "$PT2" || die "umont root"
umount "$PT1" || die "umount boot"
rmdir "$PT1" "$PT2" || die "rmdir"
