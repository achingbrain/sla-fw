# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.screen.printer_model import PrinterModel


class TestPrinterModel(Sl1fwTestCase):

    def test_name(self):
        model = PrinterModel.NONE
        self.assertEqual(model.name, "NONE")
        model = PrinterModel.SL1S
        self.assertEqual(model.name, "SL1S")

    def test_extensions(self):
        model = PrinterModel.NONE
        self.assertEqual(model.extensions, {".none"})
        model = PrinterModel.SL1S
        self.assertEqual(model.extensions, {".sl1s"})

    def test_exposure_screen(self):
        exposure_screen = PrinterModel.NONE.exposure_screen
        self.assertEqual(exposure_screen.size_px, (1024, 768))
        self.assertEqual(exposure_screen.pixel_size_nm, 50000)
        self.assertEqual(exposure_screen.referesh_delay_ms, 0)
        self.assertEqual(exposure_screen.monochromatic, False)
        self.assertEqual(exposure_screen.backwards, False)
        self.assertEqual(exposure_screen.width_px, 1024)
        self.assertEqual(exposure_screen.height_px, 768)
        self.assertEqual(exposure_screen.detected_size_px, (1024, 768))
        exposure_screen = PrinterModel.SL1S.exposure_screen
        self.assertEqual(exposure_screen.size_px, (1620, 2560))
        self.assertEqual(exposure_screen.pixel_size_nm, 50000)
        self.assertEqual(exposure_screen.referesh_delay_ms, 20)
        self.assertEqual(exposure_screen.monochromatic, True)
        self.assertEqual(exposure_screen.backwards, False)
        self.assertEqual(exposure_screen.width_px, 1620)
        self.assertEqual(exposure_screen.height_px, 2560)
        self.assertEqual(exposure_screen.detected_size_px, (540, 2560))

    def test_calibration(self):
        calibration = PrinterModel.NONE.calibration(False)
        self.assertEqual(calibration.pwms, (0, 250))
        self.assertEqual(calibration.intensity_error_threshold, 1)
        self.assertEqual(calibration.param_p, 0.75)
        self.assertEqual(calibration.min_pwm, 0)
        self.assertEqual(calibration.max_pwm, 250)
        calibration = PrinterModel.SL1S.calibration(False)
        self.assertEqual(calibration.pwms, (150, 250))
        self.assertEqual(calibration.intensity_error_threshold, 1)
        self.assertEqual(calibration.param_p, 0.75)
        self.assertEqual(calibration.min_pwm, 150)
        self.assertEqual(calibration.max_pwm, 250)
