#!/bin/bash

BOOT="/mnt/usb/"
SYS="/mnt/rootfs/"
EXC="/usr/share/sl1fw/scripts/exclude.txt"

mount -o bind "$BOOT" "$SYS/boot" && \
rsync -aAHXS --del --exclude-from="$EXC" --info=progress2 "$SYS" "/" && \
umount "$SYS/boot"
#fake-hwclock load
