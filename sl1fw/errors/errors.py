# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List, Dict, Optional

from prusaerrors.sl1.codes import Sl1Codes

from sl1fw.errors.exceptions import PrinterException, with_code
from sl1fw.states.project import ProjectErrors


class PrinterError(PrinterException):
    """
    Printer error
    """


class GeneralError(PrinterError):
    """
    General error base
    """


@with_code(Sl1Codes.TILT_HOME_FAILED)
class TiltHomeFailed(GeneralError):
    pass


@with_code(Sl1Codes.TOWER_HOME_FAILED)
class TowerHomeFailed(GeneralError):
    pass


@with_code(Sl1Codes.TOWER_ENDSTOP_NOT_REACHED)
class TowerEndstopNotReached(GeneralError):
    pass


@with_code(Sl1Codes.TILT_ENDSTOP_NOT_REACHED)
class TiltEndstopNotReached(GeneralError):
    pass


@with_code(Sl1Codes.TOWER_HOME_FAILED)
class TowerHomeCheckFailed(GeneralError):
    pass


@with_code(Sl1Codes.TILT_HOME_FAILED)
class TiltHomeCheckFailed(GeneralError):
    pass


@with_code(Sl1Codes.TOWER_AXIS_CHECK_FAILED)
@dataclass()
class TowerAxisCheckFailed(GeneralError):
    position_nm: int


@with_code(Sl1Codes.TILT_AXIS_CHECK_FAILED)
@dataclass()
class TiltAxisCheckFailed(GeneralError):
    position: int


@with_code(Sl1Codes.UVLED_VOLTAGE_DIFFER_TOO_MUCH)
class UVLEDsVoltagesDifferTooMuch(GeneralError):
    pass


@with_code(Sl1Codes.DISPLAY_TEST_FAILED)
class DisplayTestFailed(GeneralError):
    pass


@with_code(Sl1Codes.UVLED_HEAT_SINK_FAILED)
@dataclass()
class UVLEDHeatsinkFailed(GeneralError):
    uv_temp_deg_c: float


@with_code(Sl1Codes.INVALID_TILT_ALIGN_POSITION)
@dataclass()
class InvalidTiltAlignPosition(GeneralError):
    tilt_position: Optional[int]


@with_code(Sl1Codes.FAN_RPM_OUT_OF_TEST_RANGE)
@dataclass()
class FanRPMOutOfTestRange(GeneralError):
    name: str
    rpm: Optional[int]
    avg: Optional[int]
    fanError: Dict[int, bool]


@with_code(Sl1Codes.WIZARD_NOT_CANCELABLE)
class WizardNotCancelable(GeneralError):
    pass


@with_code(Sl1Codes.TOWER_BELOW_SURFACE)
@dataclass()
class TowerBelowSurface(GeneralError):
    tower_position_nm: int


@with_code(Sl1Codes.SOUND_TEST_FAILED)
class SoundTestFailed(GeneralError):
    pass


class ExposureError(PrinterError):
    """
    Exposure error base
    """


# TODO: deprecated("Use TiltHomeFailed")
@with_code(Sl1Codes.TILT_HOME_FAILED)
class TiltFailed(ExposureError):
    pass


# TODO: deprecated("Use TowerHomeFailed")
@with_code(Sl1Codes.TOWER_HOME_FAILED)
class TowerFailed(ExposureError):
    pass


@with_code(Sl1Codes.TOWER_MOVE_FAILED)
class TowerMoveFailed(ExposureError):
    pass


@with_code(Sl1Codes.PRELOAD_FAILED)
class PreloadFailed(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_FAILED)
@dataclass
class ProjectFailed(ExposureError):
    project_error: ProjectErrors


@with_code(Sl1Codes.TEMP_SENSOR_FAILED)
@dataclass
class TempSensorFailed(ExposureError):
    failed_sensors: List[int]
    failed_sensor_names: List[str]


@with_code(Sl1Codes.FAN_FAILED)
@dataclass
class FanFailed(ExposureError):
    failed_fans: List[int]
    failed_fan_names: List[str]
    failed_fans_text: str


@with_code(Sl1Codes.RESIN_SENSOR_FAILED)
@dataclass
class ResinFailed(ExposureError):
    volume_ml: float


@with_code(Sl1Codes.RESIN_TOO_LOW)
@dataclass
class ResinTooLow(ResinFailed):
    min_resin_ml: float


@with_code(Sl1Codes.RESIN_TOO_HIGH)
class ResinTooHigh(ResinFailed):
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


@with_code(Sl1Codes.MISSING_UV_CALIBRATION_DATA)
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


@with_code(Sl1Codes.FAILED_TO_SET_LOGLEVEL)
class FailedToSetLogLevel(PrinterError):
    pass
