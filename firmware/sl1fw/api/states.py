# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from enum import unique, Enum

from sl1fw.exposure_state import ExposureState
from sl1fw.project.project import ProjectState


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
    # INIT = 0
    PRINTING = 1
    GOING_UP = 2
    GOING_DOWN = 3
    WAITING = 4
    COVER_OPEN = 5
    FEED_ME = 6
    FAILURE = 7
    STIRRING = 9
    PENDING_ACTION = 10
    FINISHED = 11
    STUCK = 12
    STUCK_RECOVERY = 13
    READING_DATA = 14
    CONFIRM = 15
    CHECKS = 16
    TILTING_DOWN = 19
    CANCELED = 20
    CHECK_WARNING = 23

    @staticmethod
    def from_exposure(state: ExposureState) -> Exposure0State:
        return {
            ExposureState.PRINTING: Exposure0State.PRINTING,
            ExposureState.GOING_UP: Exposure0State.GOING_UP,
            ExposureState.GOING_DOWN: Exposure0State.GOING_DOWN,
            ExposureState.WAITING: Exposure0State.WAITING,
            ExposureState.COVER_OPEN: Exposure0State.COVER_OPEN,
            ExposureState.FEED_ME: Exposure0State.FEED_ME,
            ExposureState.FAILURE: Exposure0State.FAILURE,
            ExposureState.STIRRING: Exposure0State.STIRRING,
            ExposureState.PENDING_ACTION: Exposure0State.PENDING_ACTION,
            ExposureState.FINISHED: Exposure0State.FINISHED,
            ExposureState.STUCK: Exposure0State.STUCK,
            ExposureState.STUCK_RECOVERY: Exposure0State.STUCK_RECOVERY,
            ExposureState.READING_DATA: Exposure0State.READING_DATA,
            ExposureState.CONFIRM: Exposure0State.CONFIRM,
            ExposureState.CHECKS: Exposure0State.CHECKS,
            ExposureState.TILTING_DOWN: Exposure0State.TILTING_DOWN,
            ExposureState.CANCELED: Exposure0State.CANCELED,
            ExposureState.CHECK_WARNING: Exposure0State.CHECK_WARNING,
        }[state]


@unique
class Exposure0ProjectState(Enum):
    UNINITIALIZED = -1
    OK = 0
    NOT_FOUND = 1
    CANT_READ = 2
    NOT_ENOUGH_LAYERS = 3
    CORRUPTED = 4
    PRINT_DIRECTLY = 5

    @staticmethod
    def from_project(state: ProjectState) -> Exposure0ProjectState:
        return {
            ProjectState.UNINITIALIZED: Exposure0ProjectState.UNINITIALIZED,
            ProjectState.OK: Exposure0ProjectState.OK,
            ProjectState.NOT_FOUND: Exposure0ProjectState.NOT_FOUND,
            ProjectState.CANT_READ: Exposure0ProjectState.CANT_READ,
            ProjectState.NOT_ENOUGH_LAYERS: Exposure0ProjectState.NOT_ENOUGH_LAYERS,
            ProjectState.CORRUPTED: Exposure0ProjectState.CORRUPTED,
            ProjectState.PRINT_DIRECTLY: Exposure0ProjectState.PRINT_DIRECTLY,
        }[state]


@unique
class DisplayTest0State(Enum):
    INIT = 0
    COVER_OPEN = 1
    DISPLAY = 2
    FINISHED = 3
