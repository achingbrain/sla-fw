# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique, Enum

from .printer import Printer0State

@unique
class DisplayState(Enum):
    IDLE = 0
    CALIBRATION = 1
    WIZARD = 2
    FACTORY_RESET = 4
    ADMIN = 5
    DISPLAY_TEST = 6
    OVERHEATING = 7

    def to_state0(self):
        return {
            self.CALIBRATION: Printer0State.WIZARD,
            self.WIZARD: Printer0State.WIZARD,
            self.FACTORY_RESET: Printer0State.INITIALIZING,
            self.ADMIN: Printer0State.ADMIN,
            self.DISPLAY_TEST: Printer0State.WIZARD,
            self.OVERHEATING: Printer0State.OVERHEATING,
        }.get(self, None)
