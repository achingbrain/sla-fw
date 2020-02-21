# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum

from sl1fw.errors.codes import ErrorCode
from sl1fw.motion_controller.trace import Trace


def with_code(code: Enum):
    """
    Class decorator used to add CODE to an Exception

    :param code: Exception error code
    :return: Decorated class
    """
    def decor(cls):
        cls.CODE = code
        cls.__name__ = f"e{code.value}.{cls.__name__}"
        return cls

    return decor


@with_code(ErrorCode.UNKNOWN)
class PrinterException(Exception):
    """
    General exception for printers
    """
    CODE = ErrorCode.UNKNOWN


@with_code(ErrorCode.GENERAL_CONFIG_EXCEPTION)
class ConfigException(PrinterException):
    """
    Exception used to signal problems with configuration
    """


@with_code(ErrorCode.GENERAL_MOTION_CONTROLLER_EXCEPTION)
class MotionControllerException(PrinterException):
    def __init__(self, message: str, trace: Trace):
        self.__trace = trace
        super().__init__(f"{message}, trace: {trace}")


@with_code(ErrorCode.GENERAL_NOT_AVAILABLE_IN_STATE)
class NotAvailableInState(PrinterException):
    pass


@with_code(ErrorCode.GENERAL_DBUS_MAPPING_EXCEPTION)
class DBusMappingException(PrinterException):
    pass


@with_code(ErrorCode.GENERAL_REPRINT_WITHOUT_HISTORY)
class ReprintWithoutHistory(PrinterException):
    pass
