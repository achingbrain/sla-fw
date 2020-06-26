# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List

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


@with_code(Sl1Codes.GENERAL_TILT_HOME_FAILURE)
class TiltHomeFailure(GeneralError):
    pass


@with_code(Sl1Codes.GENERAL_TILT_HOME_FAILURE)
class TowerHomeFailure(GeneralError):
    pass


class ExposureError(PrinterError):
    """
    Exposure error base
    """


@with_code(Sl1Codes.EXPOSURE_TILT_FAILURE)
class TiltFailure(ExposureError):
    pass


@with_code(Sl1Codes.EXPOSURE_TOWER_FAILURE)
class TowerFailure(ExposureError):
    pass


@with_code(Sl1Codes.EXPOSURE_TOWER_MOVE_FAILURE)
class TowerMoveFailure(ExposureError):
    pass


@with_code(Sl1Codes.EXPOSURE_PROJECT_FAILURE)
@dataclass
class ProjectFailure(ExposureError):
    project_state: ProjectState


@with_code(Sl1Codes.EXPOSURE_TEMP_SENSOR_FAILURE)
@dataclass
class TempSensorFailure(ExposureError):
    failed_sensors: List[int]


@with_code(Sl1Codes.EXPOSURE_FAN_FAILURE)
@dataclass
class FanFailure(ExposureError):
    failed_fans: List[int]


@with_code(Sl1Codes.EXPOSURE_RESIN_SENSOR_FAILURE)
@dataclass
class ResinFailure(ExposureError):
    volume: float


@with_code(Sl1Codes.EXPOSURE_RESIN_TOO_LOW)
class ResinTooLow(ResinFailure):
    pass


@with_code(Sl1Codes.EXPOSURE_RESIN_TOO_HIGH)
class ResinTooHigh(ResinFailure):
    pass


@with_code(Sl1Codes.EXPOSURE_WARNING_ESCALATION)
class WarningEscalation(ExposureError):
    warning: Warning


class PrinterDataSendError(PrinterError):
    """
    Printer data send error base
    """


@with_code(Sl1Codes.GENERAL_MISSING_WIZARD_DATA)
class MissingWizardData(PrinterDataSendError):
    pass


@with_code(Sl1Codes.GENERAL_MISSING_CALIBRATION_DATA)
class MissingCalibrationData(PrinterDataSendError):
    pass


@with_code(Sl1Codes.GENERAL_MISSING_UVCALIBRATION_DATA)
class MissingUVCalibrationData(PrinterDataSendError):
    pass


@with_code(Sl1Codes.GENERAL_MISSING_UVPWM_SETTINGS)
class MissingUVPWM(PrinterDataSendError):
    pass


@with_code(Sl1Codes.GENERAL_FAILED_TO_MQTT_SEND)
class ErrorSendingDataToMQTT(PrinterDataSendError):
    pass


@with_code(Sl1Codes.GENERAL_FAILED_UPDATE_CHANNEL_SET)
class FailedUpdateChannelSet(PrinterError):
    pass


@with_code(Sl1Codes.GENERAL_FAILED_UPDATE_CHANNEL_GET)
class FailedUpdateChannelGet(PrinterError):
    pass


@with_code(Sl1Codes.GENERAL_NOT_CONNECTED_TO_NETWORK)
class NotConnected(PrinterError):
    pass


@with_code(Sl1Codes.GENERAL_CONNECTION_FAILED)
class ConnectionFailed(PrinterError):
    pass


@with_code(Sl1Codes.GENERAL_NOT_ENOUGH_INTERNAL_SPACE)
class NotEnoughInternalSpace(PrinterError):
    pass


@with_code(Sl1Codes.GENERAL_DOWNLOAD_FAILED)
@dataclass()
class DownloadFailed(PrinterError):
    url: str
    total_bytes: int
    completed_bytes: int


@with_code(Sl1Codes.GENERAL_NOT_MECHANICALLY_CALIBRATED)
class NotMechanicallyCalibrated(PrinterError):
    pass


@with_code(Sl1Codes.GENERAL_NOT_UV_CALIBRATED)
class NotUVCalibrated(PrinterError):
    pass
