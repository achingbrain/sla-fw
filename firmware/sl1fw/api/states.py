# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum, auto


class Printer0State(Enum):
    def _generate_next_value_(self, start, count, last_values):
        return self

    INITIALIZING = auto()
    IDLE = auto()
    UNBOXING = auto()
    WIZARD = auto()
    CALIBRATION = auto()
    DISPLAY_TEST = auto()
    PRINTING = auto()
    UPDATE = auto()
    ADMIN = auto()
    EXCEPTION = auto()
