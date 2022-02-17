# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2019-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from dataclasses import dataclass
from enum import unique, Enum, EnumMeta
from pathlib import Path

from slafw import defines
from slafw.errors.errors import UnknownPrinterModel


@dataclass(eq=False)
class Options:
    has_tilt: bool
    has_booster: bool
    vat_revision: int
    has_UV_calibration: bool
    has_UV_calculation: bool


class PrinterModelMeta(EnumMeta):
    def __call__(cls, *args, value=-1, **kwargs):
        if value == -1:
            value = PrinterModel.detect_model()
        return super().__call__(value, *args, **kwargs)


@unique
class PrinterModel(Enum, metaclass=PrinterModelMeta):
    # FORBIDDEN = -1
    NONE = 0
    SL1 = 1
    SL1S = 2
    M1 = 3

    @classmethod
    def detect_model(cls) -> int:
        model = None
        if len(os.listdir(defines.printer_model_run)) != 1:
            raise UnknownPrinterModel()
        for m in cls:
            if Path(defines.printer_model_run / m.name.lower()).exists():
                model = m
                break
        return model.value

    # TODO: remove code related to handling projects.
    # Filemanager should be the only one who takes care about files
    @property
    def extensions(self) -> set:
        return {
                self.NONE: {""},
                self.SL1: {".sl1"},
                self.SL1S: {".sl1s"},
                self.M1: {".m1"}
            }[self]

    @property
    def options(self) -> Options:
        return {
                self.NONE: Options(
                    has_tilt = False,
                    has_booster = False,
                    vat_revision = 0,
                    has_UV_calibration = False,
                    has_UV_calculation = False,
                    ),
                self.SL1: Options(
                    has_tilt = True,
                    has_booster = False,
                    vat_revision = 0,
                    has_UV_calibration = True,
                    has_UV_calculation = False,
                    ),
                self.SL1S: Options(
                    has_tilt = True,
                    has_booster = True,
                    vat_revision = 1,
                    has_UV_calibration = False,
                    has_UV_calculation = True,
                    ),
                # same as SL1S
                self.M1: Options(
                    has_tilt = True,
                    has_booster = True,
                    vat_revision = 1,
                    has_UV_calibration = False,
                    has_UV_calculation = True,
                    )
            }[self]
