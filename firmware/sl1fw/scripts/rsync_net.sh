#!/bin/bash

UPDDIR="/usr/share/sl1fw/scripts"
SSHUSR="dwarfupdate"
SSHKEY="$UPDDIR/rsync-key"
EXC="$UPDDIR/exclude.txt"
SERVER="cloud.3dwarf.net"
MODULE="sl1fw"
SSH="ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -l $SSHUSR -i $SSHKEY"

rsync -aAHXS --del --exclude-from="$EXC" --info=progress2 -e "$SSH" "$SERVER::$MODULE" "/"
