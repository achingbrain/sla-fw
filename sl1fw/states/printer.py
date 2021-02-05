# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique, Enum


@unique
class Printer0State(Enum):
    """
    General printer state enumeration
    """

    INITIALIZING = 0
    IDLE = 1
    # Replaced by wizard, UNBOXING = 2
    WIZARD = 3
    CALIBRATION = 4
    DISPLAY_TEST = 5  # Will be replaced by wizard
    PRINTING = 6
    UPDATE = 7
    ADMIN = 8
    EXCEPTION = 9


@unique
class PrinterState(Enum):
    INIT = 0
    RUNNING = 1
    PRINTING = 2
    UPDATING = 3
    EXIT = 4
    EXCEPTION = 5
    # Used to be "UNBOXING = 6", now unboxing is a wizard
    # Used to be "DISPLAY_TEST = 7", now display test is a wizard
    WIZARD = 8

    def to_state0(self):
        state = None
        if self == self.INIT:
            state = Printer0State.INITIALIZING
        elif self == self.EXCEPTION:
            state = Printer0State.EXCEPTION
        elif self == self.UPDATING:
            state = Printer0State.UPDATE
        elif self == self.PRINTING:
            state = Printer0State.PRINTING
        elif self == self.WIZARD:
            state = Printer0State.WIZARD

        return state
