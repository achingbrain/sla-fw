# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique, Enum


class ExposureScreen:
    # pylint: disable=too-many-arguments
    def __init__(self, size_px: (), pixel_size_nm: int, referesh_delay_ms: int, monochromatic: bool, backwards: bool):
        self.size_px = size_px
        self.pixel_size_nm = pixel_size_nm
        self.referesh_delay_ms = referesh_delay_ms
        self.monochromatic = monochromatic
        self.backwards = backwards

    @property
    def width_px(self):
        return self.size_px[0]

    @property
    def height_px(self):
        return self.size_px[1]

    @property
    def detected_size_px(self):
        if self.monochromatic:
            return (self.size_px[0] // 3, self.size_px[1])
        return self.size_px

class Calibration:
    def __init__(self, pwms: (), intensity_error_threshold, param_p):
        self.pwms = pwms
        self.intensity_error_threshold = intensity_error_threshold
        self.param_p = param_p

    @property
    def min_pwm(self):
        return self.pwms[0]

    @property
    def max_pwm(self):
        return self.pwms[1]


@unique
class PrinterModel(Enum):
    NONE = 0
    SL1 = 1
    SL1S = 2

    @property
    def name(self) -> str:
        return {
                self.NONE: "NONE",
                self.SL1: "SL1",
                self.SL1S: "SL1S",
            }[self]

    @property
    def extensions(self) -> set:
        return {"." + self.name.lower()}

    @property
    def exposure_screen(self) -> ExposureScreen:
        return {
                self.NONE: ExposureScreen((1024, 768), 50000, 0, False, False),
                self.SL1: ExposureScreen((1440, 2560), 46875, 30, False, False),
                # TODO real delay value
                self.SL1S: ExposureScreen((1620, 2560), 51000, 0, True, False),
            }[self]

    def calibration(self, is500khz: bool) -> Calibration:
        return {
                self.NONE: Calibration((0, 250), 1, 0.75),
                self.SL1: Calibration((150, 250) if is500khz else (125, 218), 1, 0.75),
                self.SL1S: Calibration((150, 250), 1, 0.75),
            }[self]
