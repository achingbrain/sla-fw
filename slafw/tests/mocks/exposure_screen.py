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
        real_expo_screen = ExposureScreenSL1(printer_model)
        self.parameters = real_expo_screen.parameters

        self.start = Mock()
        self.exit = Mock()
        self.show = Mock()
        self.blank_screen = Mock()
        self.create_areas = Mock()
        self.blank_area = Mock()
        self.draw_pattern = Mock()
        self.serial_number = real_expo_screen.serial_number
        self.transmittance = real_expo_screen.transmittance
