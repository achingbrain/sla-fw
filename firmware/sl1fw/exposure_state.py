# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum, auto


class ExposureState(Enum):
    def _generate_next_value_(self, start, count, last_values):
        return self

    INIT = auto()
    PRINTING = auto()
    GOING_UP = auto()
    GOING_DOWN = auto()
    WAITING = auto()
    COVER_OPEN = auto()
    FEED_ME = auto()
    FAILURE = auto()
    TILT_FAILURE = auto()
    STIRRING = auto()
    PENDING_ACTION = auto()
    FINISHED = auto()
    STUCK = auto()
    STUCK_RECOVERY = auto()
