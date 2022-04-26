# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2019-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock

from slafw.hardware.printer_model import PrinterModel
from slafw.hardware.sl1.exposure_screen import ExposureScreenSL1


class ExposureScreen:
    # pylint: disable = too-few-public-methods
    # pylint: disable = too-many-instance-attributes
    def __init__(self, printer_model: PrinterModel):
        self._real_expo_screen = ExposureScreenSL1(printer_model)

    start = Mock()
    exit = Mock()
    show = Mock()
    blank_screen = Mock()
    create_areas = Mock()
    blank_area = Mock()
    draw_pattern = Mock()

    @property
    def parameters(self):
        return self._real_expo_screen.parameters

    @property
    def transmittance(self):
        return self._real_expo_screen.transmittance

    @property
    def serial_number(self):
        return self._real_expo_screen.serial_number
