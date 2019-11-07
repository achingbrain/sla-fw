# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from enum import Enum, unique

from sl1fw.exposure_state import ExposureState


@unique
class Printer0State(Enum):
    INITIALIZING = 0
    IDLE = 1
    UNBOXING = 2
    WIZARD = 3
    CALIBRATION = 4
    DISPLAY_TEST = 5
    PRINTING = 6
    UPDATE = 7
    ADMIN = 8
    EXCEPTION = 9


@unique
class Exposure0State(Enum):
    INIT = 0
    PRINTING = 1
    GOING_UP = 2
    GOING_DOWN = 3
    WAITING = 4
    COVER_OPEN = 5
    FEED_ME = 6
    FAILURE = 7
    TILT_FAILURE = 8
    STIRRING = 9
    PENDING_ACTION = 10
    FINISHED = 11
    STUCK = 12
    STUCK_RECOVERY = 13

    @staticmethod
    def from_exposure(state: ExposureState) -> Exposure0State:
        return {
            ExposureState.INIT: Exposure0State.INIT,
            ExposureState.PRINTING: Exposure0State.PRINTING,
            ExposureState.GOING_UP: Exposure0State.GOING_UP,
            ExposureState.GOING_DOWN: Exposure0State.GOING_DOWN,
            ExposureState.WAITING: Exposure0State.WAITING,
            ExposureState.COVER_OPEN: Exposure0State.COVER_OPEN,
            ExposureState.FEED_ME: Exposure0State.FEED_ME,
            ExposureState.FAILURE: Exposure0State.FAILURE,
            ExposureState.TILT_FAILURE: Exposure0State.TILT_FAILURE,
            ExposureState.STIRRING: Exposure0State.STIRRING,
            ExposureState.PENDING_ACTION: Exposure0State.PENDING_ACTION,
            ExposureState.FINISHED: Exposure0State.FINISHED,
            ExposureState.STUCK: Exposure0State.STUCK,
            ExposureState.STUCK_RECOVERY: Exposure0State.STUCK_RECOVERY,
        }[state]

@unique
class DisplayTest0State(Enum):
    INIT = 0
    COVER_OPEN = 1
    DISPLAY = 2
    FINISHED = 3
