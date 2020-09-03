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

    def to_state0(self):
        state = None
        if self == self.CALIBRATION:
            state = Printer0State.CALIBRATION
        elif self == self.WIZARD:
            state = Printer0State.WIZARD
        elif self == self.FACTORY_RESET:
            state = Printer0State.INITIALIZING
        elif self == self.ADMIN:
            state = Printer0State.ADMIN
        elif self == self.DISPLAY_TEST:
            state = Printer0State.DISPLAY_TEST

        return state
