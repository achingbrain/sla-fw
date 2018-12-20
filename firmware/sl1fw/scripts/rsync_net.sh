#!/bin/bash

UPDDIR="/usr/share/sl1fw/scripts"
SSHUSR="sl1update"
SSHKEY="$UPDDIR/rsync-key"
EXC="$UPDDIR/exclude.txt"
SERVER="futur3d.net"
MODULE="sl1"
SSH="ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -l $SSHUSR -i $SSHKEY"

PT1="/mnt/pt1"
PT2="/mnt/pt2"

die() {
	echo "$0[$$] ERROR: $@ failed" >&2
	exit 1
}

mkdir -p "$PT1" "$PT2" || die "mkdir"
mount -o bind "/boot" "$PT1" || die "mount boot"
mount -o bind "/" "$PT2" || die "mount root"
rsync -aAHXS --del --info=progress2 -e "$SSH" "$SERVER::$MODULE/pt1/" "$PT1" || die "rsync boot"
rsync -aAHXS --del --exclude-from="$EXC" --info=progress2 -e "$SSH" "$SERVER::$MODULE/pt2/" "$PT2" || "rsync root"
umount "$PT2" || die "umont root"
umount "$PT1" || die "umount boot"
rmdir "$PT1" "$PT2" || die "rmdir"
