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
@ranged_enum(0, 4999)
class ErrorCode(Enum):
    """
    Error and exception identification codes

    TODO: @!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!
    TODO: Big fat WARNING, these code are not finalized. Do not copy numbers, use these values.
    TODO: @!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!
    """

    # Basic error codes
    NONE = 0
    UNKNOWN = 1

    # General error codes
    GENERAL_TILT_HOME_FAILURE = 1001
    GENERAL_TOWER_HOME_FAILURE = 1002
    GENERAL_CONFIG_EXCEPTION = 1005
    GENERAL_MOTION_CONTROLLER_EXCEPTION = 1006
    GENERAL_NOT_AVAILABLE_IN_STATE = 1010
    GENERAL_DBUS_MAPPING_EXCEPTION = 1011
    GENERAL_REPRINT_WITHOUT_HISTORY = 1012
    GENERAL_MISSING_WIZARD_DATA = 1013
    GENERAL_MISSING_CALIBRATION_DATA = 1014
    GENERAL_MISSING_UVCALIBRATION_DATA = 1015
    GENERAL_MISSING_UVPWM_SETTINGS = 1016
    GENERAL_FAILED_TO_MQTT_SEND = 1017
    GENERAL_FAILED_UPDATE_CHANNEL_SET = 1018
    GENERAL_FAILED_UPDATE_CHANNEL_GET = 1019

    # Exposure error codes
    EXPOSURE_TILT_FAILURE = 2001
    EXPOSURE_TOWER_FAILURE = 2002
    EXPOSURE_TOWER_MOVE_FAILURE = 2003
    EXPOSURE_PROJECT_FAILURE = 2004
    EXPOSURE_TEMP_SENSOR_FAILURE = 2005
    EXPOSURE_FAN_FAILURE = 2006
    EXPOSURE_RESIN_SENSOR_FAILURE = 2007
    EXPOSURE_RESIN_TOO_LOW = 2008
    EXPOSURE_RESIN_TOO_HIGH = 2009
    EXPOSURE_WARNING_ESCALATION = 2010


@unique
@ranged_enum(5000, 9999)
class WarningCode(Enum):
    """
    Warning identification codes

    TODO: @!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!@!
    TODO: Big fat WARNING, these code are not finalized. Do not copy numbers, use these values.
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
