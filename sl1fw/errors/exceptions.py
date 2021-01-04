# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from enum import Enum
from functools import partial
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


@with_code(Sl1Codes.MOTION_CONTROLLER_WRONG_REVISION)
class MotionControllerWrongRevision(PrinterException):
    """
    Used when MC does not have correct revision
    """


@with_code(Sl1Codes.MOTION_CONTROLLER_EXCEPTION)
class MotionControllerException(PrinterException):
    def __init__(self, message: str, trace: Trace):
        self.__trace = trace
        super().__init__(f"{message}, trace: {trace}")


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
