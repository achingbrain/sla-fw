#!/bin/bash

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

DEV=$1
PORT=$2
BAUD=$3
socat "tcp-l:$PORT,reuseaddr,fork" "file:$DEV,nonblock,raw,echo=0,waitlock=/var/run/tty,b$BAUD"
