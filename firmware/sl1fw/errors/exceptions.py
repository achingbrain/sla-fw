# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum
from typing import List, Union

from sl1codes.codes import Code
from sl1codes.errors import Errors

from sl1fw.motion_controller.trace import Trace


def with_code(code: Union[Code, Enum]):
    """
    Class decorator used to add CODE to an Exception

    :param code: Exception error code
    :return: Decorated class
    """

    def decor(cls):
        cls.CODE = code
        if isinstance(code, Code):
            value = code.code
        elif isinstance(code, Enum):
            value = code.value
        else:
            raise ValueError("with_code requires Code er Enum instance")
        cls.__name__ = f"e{value}.{cls.__name__}"
        return cls

    return decor


@with_code(Errors.UNKNOWN)
class PrinterException(Exception):
    """
    General exception for printers
    """

    CODE = Errors.UNKNOWN


@with_code(Errors.GENERAL_CONFIG_EXCEPTION)
class ConfigException(PrinterException):
    """
    Exception used to signal problems with configuration
    """


@with_code(Errors.GENERAL_MOTION_CONTROLLER_EXCEPTION)
class MotionControllerException(PrinterException):
    def __init__(self, message: str, trace: Trace):
        self.__trace = trace
        super().__init__(f"{message}, trace: {trace}")


@with_code(Errors.GENERAL_NOT_AVAILABLE_IN_STATE)
class NotAvailableInState(PrinterException):
    def __init__(self, current_state: Enum, allowed_states: List[Enum]):
        super().__init__(f"Only available in {allowed_states}, currently in {current_state}")


@with_code(Errors.GENERAL_DBUS_MAPPING_EXCEPTION)
class DBusMappingException(PrinterException):
    pass


@with_code(Errors.GENERAL_REPRINT_WITHOUT_HISTORY)
class ReprintWithoutHistory(PrinterException):
    pass


@with_code(Errors.GENERAL_ADMIN_NOT_AVAILABLE)
class AdminNotAvailable(PrinterException):
    pass
