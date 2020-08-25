# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List

from deprecation import deprecated

from prusaerrors.sl1.codes import Sl1Codes

from sl1fw.errors.exceptions import PrinterException, with_code
from sl1fw.states.project import ProjectState


class PrinterError(PrinterException):
    """
    Printer error
    """


class GeneralError(PrinterError):
    """
    General error base
    """


@with_code(Sl1Codes.TILT_HOME_FAILED)
class TiltHomeFailure(GeneralError):
    pass


@with_code(Sl1Codes.TILT_HOME_FAILED)
class TowerHomeFailure(GeneralError):
    pass


class ExposureError(PrinterError):
    """
    Exposure error base
    """


@deprecated("Use TiltHomeFailed")
@with_code(Sl1Codes.TILT_HOME_FAILED)
class TiltFailure(ExposureError):
    pass


@deprecated("Use TowerHomeFailed")
@with_code(Sl1Codes.TOWER_HOME_FAILED)
class TowerFailure(ExposureError):
    pass


@with_code(Sl1Codes.TOWER_MOVE_FAILED)
class TowerMoveFailure(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_FAILED)
@dataclass
class ProjectFailure(ExposureError):
    project_state: ProjectState


@with_code(Sl1Codes.TEMP_SENSOR_FAILED)
@dataclass
class TempSensorFailure(ExposureError):
    failed_sensors: List[int]


@with_code(Sl1Codes.FAN_FAILED)
@dataclass
class FanFailure(ExposureError):
    failed_fans: List[int]


@with_code(Sl1Codes.RESIN_SENSOR_FAILED)
@dataclass
class ResinFailure(ExposureError):
    volume: float


@with_code(Sl1Codes.RESIN_TOO_LOW)
class ResinTooLow(ResinFailure):
    pass


@with_code(Sl1Codes.RESIN_TOO_HIGH)
class ResinTooHigh(ResinFailure):
    pass


@with_code(Sl1Codes.WARNING_ESCALATION)
@dataclass
class WarningEscalation(ExposureError):
    warning: Warning


class PrinterDataSendError(PrinterError):
    """
    Printer data send error base
    """


@with_code(Sl1Codes.MISSING_WIZARD_DATA)
class MissingWizardData(PrinterDataSendError):
    pass


@with_code(Sl1Codes.MISSING_CALIBRATION_DATA)
class MissingCalibrationData(PrinterDataSendError):
    pass


@with_code(Sl1Codes.MISSING_UVCALIBRATION_DATA)
class MissingUVCalibrationData(PrinterDataSendError):
    pass


@with_code(Sl1Codes.MISSING_UVPWM_SETTINGS)
class MissingUVPWM(PrinterDataSendError):
    pass


@with_code(Sl1Codes.MQTT_SEND_FAILED)
class ErrorSendingDataToMQTT(PrinterDataSendError):
    pass


@with_code(Sl1Codes.FAILED_UPDATE_CHANNEL_SET)
class FailedUpdateChannelSet(PrinterError):
    pass


@with_code(Sl1Codes.FAILED_UPDATE_CHANNEL_GET)
class FailedUpdateChannelGet(PrinterError):
    pass


@with_code(Sl1Codes.NOT_CONNECTED_TO_NETWORK)
class NotConnected(PrinterError):
    pass


@with_code(Sl1Codes.CONNECTION_FAILED)
class ConnectionFailed(PrinterError):
    pass


@with_code(Sl1Codes.NOT_ENOUGH_INTERNAL_SPACE)
class NotEnoughInternalSpace(PrinterError):
    pass


@with_code(Sl1Codes.DOWNLOAD_FAILED)
@dataclass()
class DownloadFailed(PrinterError):
    url: str
    total_bytes: int
    completed_bytes: int


@with_code(Sl1Codes.NOT_MECHANICALLY_CALIBRATED)
class NotMechanicallyCalibrated(PrinterError):
    pass


@with_code(Sl1Codes.NOT_UV_CALIBRATED)
class NotUVCalibrated(PrinterError):
    pass
