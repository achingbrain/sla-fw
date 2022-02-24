# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2019-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from slafw import defines
from slafw.errors.errors import UnknownPrinterModel
from slafw.hardware.base.printer_model import PrinterModelBase
from slafw.hardware.printer_options import PrinterOptions


class PrinterModelMeta(type):
    def __getattr__(cls, item):
        if item in cls.MODELS:
            return cls.MODELS[item]
        return super().__getattribute__(item)

    def __iter__(cls):
        return cls.MODELS.values().__iter__()


class PrinterModel(metaclass=PrinterModelMeta):
    # TODO: This mimics existing PrinterModel behaviour defined by enum. Maybe this is not the best way to handle
    # TODO: dynamic registration of models. Maybe a class factory method on base model would be more readable.
    MODELS = {}

    def __new__(cls):
        return cls.detect_model()

    @classmethod
    def register_model(cls, model: PrinterModelBase):
        cls.MODELS[model.name.upper()] = model

    @classmethod
    def detect_model(cls) -> PrinterModel:
        for model in cls.MODELS.values():
            if (defines.printer_model_run / model.name.lower()).exists():
                return model
        raise UnknownPrinterModel


class PrinterModelNone(PrinterModelBase):
    @property
    def name(self) -> str:
        return "NONE"

    @property
    def value(self) -> int:
        return 0

    @property
    def extension(self) -> str:
        return ""

    @property
    def options(self) -> PrinterOptions:
        return PrinterOptions(
            has_tilt=False,
            has_booster=False,
            vat_revision=0,
            has_UV_calibration=False,
            has_UV_calculation=False,
        )


PrinterModel.register_model(PrinterModelNone())
