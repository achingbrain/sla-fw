#!/bin/bash

NEW=$1
OLD=`hostname`
hostnamectl set-hostname $NEW && sed -i.old -e "s:$OLD:$NEW:g" /etc/hosts && systemctl restart avahi-daemon.service && systemctl restart nmbd.service
