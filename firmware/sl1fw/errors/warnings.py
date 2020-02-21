# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass

from sl1fw.errors.codes import WarningCode


@dataclass
class PrinterWarning(Warning):
    """
    Printer warning
    """

    CODE = WarningCode.UNKNOWN


@dataclass
class ExposureWarning(PrinterWarning):
    """
    Base for exposure warnings
    """


@dataclass
class AmbientTemperatureOutOfRange(ExposureWarning):
    ambient_temperature: float


class AmbientTooHot(AmbientTemperatureOutOfRange):
    CODE = WarningCode.EXPOSURE_AMBIENT_TOO_HOT


class AmbientTooCold(AmbientTemperatureOutOfRange):
    CODE = WarningCode.EXPOSURE_AMBIENT_TOO_COLD


class PrintingDirectlyFromMedia(ExposureWarning):
    CODE = WarningCode.EXPOSURE_PRINTING_DIRECTLY


@dataclass
class ModelMismatch(ExposureWarning):
    CODE = WarningCode.EXPOSURE_PRINTING_DIRECTLY

    actual_model: str
    actual_variant: str
    project_model: str
    project_variant: str


@dataclass
class ResinNotEnough(ExposureWarning):
    CODE = WarningCode.EXPOSURE_RESIN_NOT_ENOUGH

    measured_resin_ml: float
    required_resin_ml: float
