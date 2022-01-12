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

rsync -av systemd/slafw.service root@${SL1}:/lib/systemd/system/slafw.service &&
rsync -av systemd/model-detect.service root@${SL1}:/lib/systemd/system/model-detect.service &&
rsync -av systemd/model-detect.path root@${SL1}:/lib/systemd/system/model-detect.path &&
rsync -av systemd/slafw-tmpfiles.conf root@${SL1}:/lib/tmpfiles.d/slafw-tmpfiles.conf &&
rsync -av slafw/scripts/ root@${SL1}:/usr/share/slafw/scripts/ &&
rsync -av --exclude scripts slafw/ root@${SL1}:/usr/lib/python3.9/site-packages/slafw/

ssh root@${SL1} "
set -o xtrace; \
systemctl daemon-reload; \
systemctl restart slafw; \
systemctl restart touch-ui model-detect.service model-detect.path
"
