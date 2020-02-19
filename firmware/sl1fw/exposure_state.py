# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from enum import Enum, unique
from typing import List

from sl1fw.project.project import ProjectState


@unique
class ExposureState(Enum):
    READING_DATA = 1
    CONFIRM = 2
    CHECKS = 3
    PRINTING = 5
    GOING_UP = 6
    GOING_DOWN = 7
    WAITING = 8
    COVER_OPEN = 9
    FEED_ME = 10
    FAILURE = 11
    STIRRING = 13
    PENDING_ACTION = 14
    FINISHED = 15
    STUCK = 16
    STUCK_RECOVERY = 17
    CHECK_WARNING = 22
    RESIN_WARNING = 23
    TILTING_DOWN = 24
    CANCELED = 26

    @staticmethod
    def FINISHED_STATES():
        return [ExposureState.FAILURE, ExposureState.CANCELED, ExposureState.FINISHED]

@unique
class ExposureWarningCode(Enum):
    NONE = -1
    UNKNOWN = 0
    AMBIENT_TOO_HOT = 1
    AMBIENT_TOO_COLD = 2
    PRINTING_DIRECTLY = 3
    PRINTER_MODEL_MISMATCH = 4
    RESIN_NOT_ENOUGH = 5


@dataclass
class ExposureWarning(Warning):
    CODE = ExposureWarningCode.UNKNOWN


@dataclass
class AmbientTemperatureWarning(ExposureWarning):
    ambient_temperature: float


class AmbientTooHot(AmbientTemperatureWarning):
    CODE = ExposureWarningCode.AMBIENT_TOO_HOT


class AmbientTooCold(AmbientTemperatureWarning):
    CODE = ExposureWarningCode.AMBIENT_TOO_COLD


class PrintingDirectlyWarning(ExposureWarning):
    CODE = ExposureWarningCode.PRINTING_DIRECTLY


@dataclass
class ModelMismatchWarning(ExposureWarning):
    CODE = ExposureWarningCode.PRINTING_DIRECTLY

    actual_model: str
    actual_variant: str
    project_model: str
    project_variant: str


@dataclass
class ResinNotEnoughWarning(ExposureWarning):
    CODE = ExposureWarningCode.RESIN_NOT_ENOUGH

    measured_resin_ml: float
    required_resin_ml: float


@unique
class ExposureExceptionCode(Enum):
    NONE = -1
    UNKNOWN = 0
    TILT_FAILURE = 1
    TOWER_FAILURE = 2
    TOWR_MOVE_FAILURE = 3
    PROJECT_FAILURE = 4
    TEMP_SENSOR_FAILURE = 5
    FAN_FAILURE = 6
    RESIN_SENSOR_FAILURE = 7
    RESIN_TOO_LOW = 8
    RESIN_TOO_HIGH = 9
    WARNING_ESCALATION = 10


@unique
class ExposureCheck(Enum):
    TEMPERATURE = 1
    PROJECT = 2
    HARDWARE = 3
    FAN = 4
    COVER = 5
    RESIN = 6
    START_POSITIONS = 7
    STIRRING = 8


@unique
class ExposureCheckResult(Enum):
    SCHEDULED = -1
    RUNNING = 0
    SUCCESS = 1
    FAILURE = 2
    WARNING = 3
    DISABLED = 4


@dataclass
class ExposureException(Exception):
    CODE = ExposureExceptionCode.UNKNOWN


class TiltFailure(ExposureException):
    CODE = ExposureExceptionCode.TILT_FAILURE


class TowerFailure(ExposureException):
    CODE = ExposureExceptionCode.TOWER_FAILURE


class TowerMoveFailure(ExposureException):
    CODE = ExposureExceptionCode.TOWR_MOVE_FAILURE


@dataclass
class ProjectFailure(ExposureException):
    CODE = ExposureExceptionCode.PROJECT_FAILURE

    project_state: ProjectState


@dataclass
class TempSensorFailure(ExposureException):
    CODE = ExposureExceptionCode.TEMP_SENSOR_FAILURE

    failed_sensors: List[int]


@dataclass
class FanFailure(ExposureException):
    CODE = ExposureExceptionCode.FAN_FAILURE
    failed_fans: List[int]


@dataclass
class ResinFailure(ExposureException):
    CODE = ExposureExceptionCode.RESIN_SENSOR_FAILURE

    volume: float


class ResinTooLow(ResinFailure):
    CODE = ExposureExceptionCode.RESIN_TOO_LOW


class ResinTooHigh(ResinFailure):
    CODE = ExposureExceptionCode.RESIN_TOO_HIGH


class WarningEscalation(ExposureException):
    CODE = ExposureExceptionCode.WARNING_ESCALATION
