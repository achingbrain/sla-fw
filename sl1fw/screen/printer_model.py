# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique, Enum


class PrinterModelParams:
    def __init__(self, name, screen_size_px, screen_pixel_size_nm, referesh_delay_ms):
        self.name = name
        self.screen_size_px = screen_size_px
        self.screen_pixel_size_nm = screen_pixel_size_nm
        self.referesh_delay_ms = referesh_delay_ms

    @property
    def screen_width_px(self):
        return self.screen_size_px[0]

    @property
    def screen_height_px(self):
        return self.screen_size_px[1]


@unique
class PrinterModel(Enum):
    SL1 = 0

    def parameters(self):
        params = None
        if self == self.SL1:
            params = PrinterModelParams("SL1", (1440, 2560), 46875, 30)
        return params
