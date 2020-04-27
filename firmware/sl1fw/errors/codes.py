# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique, Enum


def ranged_enum(minimum: int, maximum: int):
    """
    Class decorator to force enum values in defined range

    :param minimum: Minimal allowed value
    :param maximum: Maximal allowed value
    :return: Ranged enum decorator
    """

    def decor(enumeration):
        for name, member in enumeration.__members__.items():
            if member.value < minimum or member.value > maximum:
                raise ValueError(f"{enumeration} value {name} is out of permitted range ({minimum} to {maximum}).")
        return enumeration

    return decor


@unique
class ErrorClass(Enum):
    # This mapping is taken from general Prusa guidelines on errors, do not modify.
    MECHANICAL = 1  # Mechanical failures, engines XYZ, tower
    TEMPERATURE = 2  # Temperature measurement, thermistors, heating
    ELECTRICAL = 3  # Electrical, MINDA, FINDA, Motion Controller, …
    CONNECTIVITY = 4  # Connectivity - Wi - Fi, LAN, Prusa Connect Cloud
    SYSTEM = 5  # System - BSOD, ...


def make_code(cls: ErrorClass, error_code: int) -> int:
    if error_code < 0 or error_code > 99:
        raise ValueError(f"Error code {error_code} out of range")
    return cls.value * 100 + error_code


@unique
@ranged_enum(0, 999)
class ErrorCode(Enum):
    """
    Error and exception identification codes

    TODO: @!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!
    TODO: WARNING, these codes are based on draft of the specification.
    TODO: Remove this warning once the source document is accepted.
    TODO: @!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!
    """

    # Basic error codes
    NONE = make_code(ErrorClass.SYSTEM, 0)
    UNKNOWN = make_code(ErrorClass.SYSTEM, 1)

    # General error codes
    GENERAL_TILT_HOME_FAILURE = make_code(ErrorClass.MECHANICAL, 1)
    GENERAL_TOWER_HOME_FAILURE = make_code(ErrorClass.MECHANICAL, 2)
    GENERAL_CONFIG_EXCEPTION = make_code(ErrorClass.SYSTEM, 5)
    GENERAL_MOTION_CONTROLLER_EXCEPTION = make_code(ErrorClass.ELECTRICAL, 6)
    GENERAL_NOT_AVAILABLE_IN_STATE = make_code(ErrorClass.SYSTEM, 6)
    GENERAL_DBUS_MAPPING_EXCEPTION = make_code(ErrorClass.SYSTEM, 7)
    GENERAL_REPRINT_WITHOUT_HISTORY = make_code(ErrorClass.SYSTEM, 8)
    GENERAL_MISSING_WIZARD_DATA = make_code(ErrorClass.SYSTEM, 9)
    GENERAL_MISSING_CALIBRATION_DATA = make_code(ErrorClass.SYSTEM, 10)
    GENERAL_MISSING_UVCALIBRATION_DATA = make_code(ErrorClass.SYSTEM, 11)
    GENERAL_MISSING_UVPWM_SETTINGS = make_code(ErrorClass.SYSTEM, 12)
    GENERAL_FAILED_TO_MQTT_SEND = make_code(ErrorClass.CONNECTIVITY, 1)
    GENERAL_FAILED_UPDATE_CHANNEL_SET = make_code(ErrorClass.SYSTEM, 13)
    GENERAL_FAILED_UPDATE_CHANNEL_GET = make_code(ErrorClass.SYSTEM, 14)
    GENERAL_NOT_CONNECTED_TO_NETWORK = make_code(ErrorClass.CONNECTIVITY, 2)
    GENERAL_CONNECTION_FAILED = make_code(ErrorClass.CONNECTIVITY, 3)
    GENERAL_DOWNLOAD_FAILED = make_code(ErrorClass.CONNECTIVITY, 4)
    GENERAL_NOT_ENOUGH_INTERNAL_SPACE = make_code(ErrorClass.SYSTEM, 16)
    GENERAL_ADMIN_NOT_AVAILABLE = make_code(ErrorClass.SYSTEM, 17)
    GENERAL_FILE_NOT_FOUND = make_code(ErrorClass.SYSTEM, 18)
    GENERAL_INVALID_EXTENSION = make_code(ErrorClass.SYSTEM, 19)
    GENERAL_FILE_ALREADY_EXISTS = make_code(ErrorClass.SYSTEM, 20)
    GENERAL_INVALID_PROJECT = make_code(ErrorClass.SYSTEM, 21)
    GENERAL_NOT_MECHANICALLY_CALIBRATED = make_code(ErrorClass.MECHANICAL, 13)
    GENERAL_NOT_UV_CALIBRATED = make_code(ErrorClass.ELECTRICAL, 8)

    # Exposure error codes
    EXPOSURE_TILT_FAILURE = make_code(ErrorClass.MECHANICAL, 10)
    EXPOSURE_TOWER_FAILURE = make_code(ErrorClass.MECHANICAL, 12)
    EXPOSURE_TOWER_MOVE_FAILURE = make_code(ErrorClass.MECHANICAL, 3)
    EXPOSURE_PROJECT_FAILURE = make_code(ErrorClass.SYSTEM, 4)
    EXPOSURE_TEMP_SENSOR_FAILURE = make_code(ErrorClass.TEMPERATURE, 5)
    EXPOSURE_FAN_FAILURE = make_code(ErrorClass.MECHANICAL, 6)
    EXPOSURE_RESIN_SENSOR_FAILURE = make_code(ErrorClass.ELECTRICAL, 7)
    EXPOSURE_RESIN_TOO_LOW = make_code(ErrorClass.MECHANICAL, 8)
    EXPOSURE_RESIN_TOO_HIGH = make_code(ErrorClass.MECHANICAL, 9)
    EXPOSURE_WARNING_ESCALATION = make_code(ErrorClass.SYSTEM, 15)


@unique
@ranged_enum(5000, 9999)
class WarningCode(Enum):
    """
    Warning identification codes

    TODO: @!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!
    TODO: Big fat WARNING, these codes are not finalized. Do not copy numbers, use these values.
    TODO: There are no guidelines for warnings, yet.
    TODO: @!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!
    """

    # Basic warning codes
    NONE = 5000
    UNKNOWN = 5001

    # Exposure warning codes
    EXPOSURE_AMBIENT_TOO_HOT = 6001
    EXPOSURE_AMBIENT_TOO_COLD = 6002
    EXPOSURE_PRINTING_DIRECTLY = 6003
    EXPOSURE_PRINTER_MODEL_MISMATCH = 6004
    EXPOSURE_RESIN_NOT_ENOUGH = 6005
    EXPOSURE_PROJECT_SETTINGS_MODIFIED = 6006
