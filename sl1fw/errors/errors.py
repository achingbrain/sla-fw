# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Dict, Optional
from typing import List

from prusaerrors.shared.codes import Code
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw.motion_controller.trace import Trace


def with_code(code: str):
    """
    Class decorator used to add CODE to an Exception

    :param code: Exception error code
    :return: Decorated class
    """

    def decor(cls):
        cls.CODE = code
        cls.MESSAGE = code.message
        if not isinstance(code, Code):
            raise ValueError(f'with_code requires valid error code string i.e "#10108", got: "{code}"')
        cls.__name__ = f"e{code.raw_code}.{cls.__name__}"
        return cls

    return decor


def get_exception_code(exception: Exception) -> Code:
    return getattr(exception, "CODE") if hasattr(exception, "CODE") else Sl1Codes.UNKNOWN


exception_dataclass = partial(dataclass, frozen=True, eq=True)


@with_code(Sl1Codes.UNKNOWN)
class PrinterException(Exception):
    """
    General exception for printers
    """

    CODE = Sl1Codes.UNKNOWN


@with_code(Sl1Codes.CONFIG_EXCEPTION)
class ConfigException(PrinterException):
    """
    Exception used to signal problems with configuration
    """


@with_code(Sl1Codes.MOTION_CONTROLLER_EXCEPTION)
class MotionControllerException(PrinterException):
    def __init__(self, message: str = "", trace: Trace = None):
        self.__trace = trace
        super().__init__(f"{message}, trace: {trace}")


@with_code(Sl1Codes.MOTION_CONTROLLER_WRONG_REVISION)
class MotionControllerWrongRevision(MotionControllerException):
    """
    Used when MC does not have correct revision
    """


class MotionControllerNotResponding(MotionControllerException):
    """
    Cannot read data from motion controller UART. Motion controller dead?
    """


class MotionControllerWrongResponse(MotionControllerException):
    """
    Cannot parse data from motion controller UART. Motion controller corrupted?
    """


class MotionControllerWrongFw(MotionControllerException):
    """Used to signal that MC has wrong FW and needs to be updated"""


@with_code(Sl1Codes.NOT_AVAILABLE_IN_STATE)
class NotAvailableInState(PrinterException):
    def __init__(self, current_state: Enum, allowed_states: List[Enum]):
        super().__init__(f"Only available in {allowed_states}, currently in {current_state}")


@with_code(Sl1Codes.DBUS_MAPPING_ERROR)
class DBusMappingException(PrinterException):
    pass


@with_code(Sl1Codes.REPRINT_WITHOUT_HISTORY)
class ReprintWithoutHistory(PrinterException):
    pass


@with_code(Sl1Codes.ADMIN_NOT_AVAILABLE)
class AdminNotAvailable(PrinterException):
    pass


class ExposureCheckDisabled(PrinterException):
    """Used to signal that exposure check is being skipped"""


@with_code(Sl1Codes.BOOSTER_ERROR)
class BoosterError(PrinterException):
    def __init__(self, message: str):
        super().__init__(f"{message}")


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


class TiltPositionFailed(GeneralError):
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
    fan: str
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


@with_code(Sl1Codes.FILE_NOT_FOUND)
class ProjectErrorNotFound(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_ERROR_CANT_READ)
class ProjectErrorCantRead(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_ERROR_NOT_ENOUGH_LAYERS)
class ProjectErrorNotEnoughLayers(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_ERROR_CORRUPTED)
class ProjectErrorCorrupted(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_ERROR_ANALYSIS_FAILED)
class ProjectErrorAnalysisFailed(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_ERROR_CALIBRATION_INVALID)
class ProjectErrorCalibrationInvalid(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_ERROR_WRONG_PRINTER_MODEL)
class ProjectErrorWrongPrinterModel(ExposureError):
    pass


@with_code(Sl1Codes.PROJECT_ERROR_CANT_REMOVE)
class ProjectErrorCantRemove(ExposureError):
    pass


@with_code(Sl1Codes.TEMP_SENSOR_FAILED)
@dataclass
class TempSensorFailed(ExposureError):
    sensor: str


@with_code(Sl1Codes.TEMPERATURE_OUT_OF_RANGE)
@dataclass()
class TempSensorNotInRange(GeneralError):
    sensor: str
    temperature: float


@with_code(Sl1Codes.A64_OVERHEAT)
@dataclass()
class A64Overheat(GeneralError):
    temperature: float


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


@with_code(Sl1Codes.FAILED_TO_SAVE_WIZARD_DATA)
class FailedToSaveWizardData(PrinterError):
    pass


@with_code(Sl1Codes.FAILED_TO_SERIALIZE_WIZARD_DATA)
class FailedToSerializeWizardData(PrinterError):
    pass


@with_code(Sl1Codes.UV_LED_METER_NOT_DETECTED)
class FailedToDetectUVMeter(PrinterError):
    pass


@with_code(Sl1Codes.UV_LED_METER_NOT_RESPONDING)
class UVMeterFailedToRespond(PrinterError):
    pass


@with_code(code=Sl1Codes.UV_LED_METER_COMMUNICATION_ERROR)
class UVMeterCommunicationFailed(PrinterError):
    pass


@with_code(Sl1Codes.DISPLAY_TRANSLUCENT)
class ScreenTranslucent(PrinterError):
    pass


@with_code(Sl1Codes.UNEXPECTED_UV_INTENSITY)
class UnexpectedUVIntensity(PrinterError):
    pass


@with_code(Sl1Codes.UNKNOWN_UV_MEASUREMENT_ERROR)
@dataclass()
class UnknownUVMeasurementFailure(PrinterError):
    code: int


class UVCalibrationError(PrinterError):
    pass


@with_code(Sl1Codes.UV_TOO_BRIGHT)
@dataclass()
class UVTooBright(UVCalibrationError):
    intensity: float
    threshold: float


@with_code(Sl1Codes.UV_TOO_DIMM)
class UVTooDimm(UVCalibrationError):
    intensity: float
    threshold: float


@with_code(Sl1Codes.UV_INTENSITY_DEVIATION_TOO_HIGH)
@dataclass()
class UVDeviationTooHigh(UVCalibrationError):
    found: float
    allowed: float


@with_code(Sl1Codes.FAILED_TO_SAVE_FACTORY_DEFAULTS)
class FailedToSaveFactoryConfig(PrinterError):
    pass


@with_code(Sl1Codes.ALTERNATIVE_SLOT_BOOT)
class BootedInAlternativeSlot(PrinterError):
    pass


@with_code(Sl1Codes.MISSING_EXAMPLES)
class MissingExamples(PrinterError):
    pass


@with_code(Sl1Codes.FAILED_TO_LOAD_FACTORY_LEDS_CALIBRATION)
class NoFactoryUvCalib(PrinterError):
    pass


@with_code(Sl1Codes.UV_LEDS_DISCONNECTED)
class UVLEDsDisconnected(PrinterError):
    pass


@with_code(Sl1Codes.UV_LEDS_ROW_FAILED)
class UVLEDsRowFailed(PrinterError):
    pass


@with_code(Sl1Codes.UNKNOWN_PRINTER_MODEL)
class UnknownPrinterModel(PrinterError):
    pass

@with_code(Sl1Codes.UV_TEMP_SENSOR_FAILED)
class UvTempSensorFailed(PrinterError):
    pass
