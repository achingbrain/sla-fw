# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, field
from enum import unique, Enum

from sl1fw import defines


@dataclass(eq=False)
class ExposureScreenParameters:
    #pylint: disable=too-many-instance-attributes
    size_px: tuple
    thumbnail_factor: int
    pixel_size_nm: int
    referesh_delay_ms: int
    monochromatic: bool
    backwards: bool
    width_px: int = field(init=False)
    height_px: int = field(init=False)
    bytes_per_pixel: int = field(init=False)
    apparent_width_px: int = field(init=False)
    detected_size_px: tuple = field(init=False)
    display_usage_size_px: tuple = field(init=False)
    live_preview_size_px: tuple = field(init=False)
    surface_area_px: tuple = field(init=False)

    def __post_init__(self):
        self.width_px = self.size_px[0]
        self.height_px = self.size_px[1]
        self.bytes_per_pixel = 3 if self.monochromatic else 1
        self.apparent_width_px = self.size_px[0] // self.bytes_per_pixel
        self.detected_size_px = (self.size_px[0] // self.bytes_per_pixel, self.size_px[1])
        # numpy uses reversed axis indexing
        self.display_usage_size_px = (self.size_px[1] // self.thumbnail_factor, self.size_px[0] // self.thumbnail_factor)
        self.live_preview_size_px = (self.size_px[0] // self.thumbnail_factor, self.size_px[1] // self.thumbnail_factor)
        self.surface_area_px = (0, 0, self.apparent_width_px, self.height_px)


@dataclass(eq=False)
class CalibrationParameters:
    pwms: tuple
    intensity_error_threshold: int
    param_p: float
    min_pwm: int = field(init=False)
    max_pwm: int = field(init=False)
    safe_default_pwm: int = field(init=False)

    def __post_init__(self):
        self.min_pwm = self.pwms[0]
        self.max_pwm = self.pwms[1]
        self.safe_default_pwm = self.pwms[2]


@unique
class PrinterModel(Enum):
    NONE = 0
    SL1 = 1
    SL1S = 2

    @property
    def extensions(self) -> set:
        return {
                self.NONE: {""},
                self.SL1: {".sl1"},
                self.SL1S: {".sl1s"},
            }[self]

    @property
    def exposure_screen_parameters(self) -> ExposureScreenParameters:
        return {
                self.NONE: ExposureScreenParameters((320, 200), 1, 50000, 0, False, False),
                self.SL1: ExposureScreenParameters((1440, 2560), 5, 46875, 30, False, False),
                self.SL1S: ExposureScreenParameters((1620, 2560), 5, 50000, 20, True, False),
            }[self]

    def calibration_parameters(self, is500khz: bool) -> CalibrationParameters:
        return {
                self.NONE: CalibrationParameters((0, 250, 0), 1, 0.75),
                self.SL1: CalibrationParameters((150, 250, 150) if is500khz else (125, 218, 125), 1, 0.75),
                self.SL1S: CalibrationParameters((30, 250, 208), 1, 0.75),
            }[self]

    def default_uvpwm(self) -> int:
        return {
            self.NONE: 0,
            self.SL1: 0,
            self.SL1S: 208,
        }[self]


class ExposurePanel:
    @staticmethod
    def _of_node():
        return defines.exposure_panel_of_node

    @classmethod
    def panel_name(cls):
        path = cls._of_node() / "panel-name"
        return path.read_text()[:-1] if path.exists() else None

    @classmethod
    def serial_number(cls):
        path = cls._of_node() / "serial-number"
        return path.read_text()[:-1] if path.exists() else None

    @classmethod
    def transmittance(cls):
        path = cls._of_node() / "transmittance"
        return int.from_bytes(path.read_bytes(), byteorder='big') / 10000.0 \
            if path.exists() else 1.0

    @classmethod
    def printer_model(cls):
        return {
            "ls055r1sx04": PrinterModel.SL1,
            "rv059fbb": PrinterModel.SL1S
        }.get(cls.panel_name(), PrinterModel.NONE)
