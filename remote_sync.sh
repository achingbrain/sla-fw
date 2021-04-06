#!/bin/sh

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

SL1=$1

if [ -z ${SL1} ]; then
	echo "Pass target as the only argument";
	exit -1;
fi;

rsync -av systemd/sl1fw.service root@${SL1}:/lib/systemd/system/sl1fw.service &&
rsync -av systemd/sl1fw-tmpfiles.conf root@${SL1}:/lib/tmpfiles.d/sl1fw-tmpfiles.conf &&
rsync -av sl1fw/scripts/ root@${SL1}:/usr/share/sl1fw/scripts/ &&
rsync -av sl1fw/multimedia/ root@${SL1}:/usr/share/sl1fw/multimedia/ &&
rsync -av --exclude scripts --exclude multimedia sl1fw/ root@${SL1}:/usr/lib/python3.8/site-packages/sl1fw/

ssh root@${SL1} "
set -o xtrace; \
systemctl daemon-reload; \
systemctl restart sl1fw; \
systemctl restart touch-ui
"
