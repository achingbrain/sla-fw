# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique, Enum


@unique
class PrinterState(Enum):
    INIT = 0
    RUNNING = 1
    PRINTING = 2
    UPDATING = 3
    EXIT = 4
    EXCEPTION = 5
