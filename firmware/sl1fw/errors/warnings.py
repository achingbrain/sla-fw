# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import Dict, Tuple, Any

from prusaerrors.sl1.codes import Sl1Codes

from sl1fw.errors.exceptions import with_code


@with_code(Sl1Codes.UNKNOWN)
@dataclass
class PrinterWarning(Warning):
    """
    Printer warning
    """


@dataclass
class ExposureWarning(PrinterWarning):
    """
    Base for exposure warnings
    """


@dataclass
class AmbientTemperatureOutOfRange(ExposureWarning):
    ambient_temperature: float


@with_code(Sl1Codes.EXPOSURE_AMBIENT_TOO_HOT_WARNING)
class AmbientTooHot(AmbientTemperatureOutOfRange):
    pass


@with_code(Sl1Codes.EXPOSURE_AMBIENT_TOO_COLD_WARNING)
class AmbientTooCold(AmbientTemperatureOutOfRange):
    pass


@with_code(Sl1Codes.EXPOSURE_PRINTING_DIRECTLY_WARNING)
class PrintingDirectlyFromMedia(ExposureWarning):
    pass


@with_code(Sl1Codes.EXPOSURE_PRINTER_MODEL_MISMATCH_WARNING)
@dataclass
class ModelMismatch(ExposureWarning):
    actual_model: str
    actual_variant: str
    project_model: str
    project_variant: str


@with_code(Sl1Codes.EXPOSURE_RESIN_NOT_ENOUGH_WARNING)
@dataclass
class ResinNotEnough(ExposureWarning):
    measured_resin_ml: float
    required_resin_ml: float


@with_code(Sl1Codes.EXPOSURE_PROJECT_SETTINGS_MODIFIED_WARNING)
@dataclass
class ProjectSettingsModified(ExposureWarning):
    changes: Dict[str, Tuple[Any, Any]]
