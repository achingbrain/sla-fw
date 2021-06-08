# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from sl1fw import defines
from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.hardware.printer_model import PrinterModel, ExposurePanel


class TestPrinterModel(Sl1fwTestCase):

    def test_name(self):
        model = PrinterModel.NONE
        self.assertEqual(model.name, "NONE")
        model = PrinterModel.SL1S
        self.assertEqual(model.name, "SL1S")

    def test_extensions(self):
        model = PrinterModel.NONE
        self.assertEqual(model.extensions, {""})
        model = PrinterModel.SL1S
        self.assertEqual(model.extensions, {".sl1s"})

    def test_exposure_screen(self):
        exposure_screen_parameters = PrinterModel.NONE.exposure_screen_parameters
        self.assertEqual(exposure_screen_parameters.size_px, (320, 200))
        self.assertEqual(exposure_screen_parameters.pixel_size_nm, 50000)
        self.assertEqual(exposure_screen_parameters.referesh_delay_ms, 0)
        self.assertEqual(exposure_screen_parameters.monochromatic, False)
        self.assertEqual(exposure_screen_parameters.backwards, False)
        self.assertEqual(exposure_screen_parameters.width_px, 320)
        self.assertEqual(exposure_screen_parameters.height_px, 200)
        self.assertEqual(exposure_screen_parameters.detected_size_px, (320, 200))
        exposure_screen_parameters = PrinterModel.SL1S.exposure_screen_parameters
        self.assertEqual(exposure_screen_parameters.size_px, (1620, 2560))
        self.assertEqual(exposure_screen_parameters.pixel_size_nm, 50000)
        self.assertEqual(exposure_screen_parameters.referesh_delay_ms, 20)
        self.assertEqual(exposure_screen_parameters.monochromatic, True)
        self.assertEqual(exposure_screen_parameters.backwards, False)
        self.assertEqual(exposure_screen_parameters.width_px, 1620)
        self.assertEqual(exposure_screen_parameters.height_px, 2560)
        self.assertEqual(exposure_screen_parameters.detected_size_px, (540, 2560))

    def test_calibration(self):
        calibration_parameters = PrinterModel.NONE.calibration_parameters(False)
        self.assertEqual(calibration_parameters.pwms, (0, 250, 0))
        self.assertEqual(calibration_parameters.intensity_error_threshold, 1)
        self.assertEqual(calibration_parameters.param_p, 0.75)
        self.assertEqual(calibration_parameters.min_pwm, 0)
        self.assertEqual(calibration_parameters.max_pwm, 250)
        self.assertEqual(calibration_parameters.safe_default_pwm, 0)
        calibration_parameters = PrinterModel.SL1.calibration_parameters(False) # MC revision < 6c
        self.assertEqual(calibration_parameters.pwms, (125, 218, 125))
        self.assertEqual(calibration_parameters.intensity_error_threshold, 1)
        self.assertEqual(calibration_parameters.param_p, 0.75)
        self.assertEqual(calibration_parameters.min_pwm, 125)
        self.assertEqual(calibration_parameters.max_pwm, 218)
        self.assertEqual(calibration_parameters.safe_default_pwm, 125)
        calibration_parameters = PrinterModel.SL1.calibration_parameters(True) # MC revision >= 6c
        self.assertEqual(calibration_parameters.pwms, (150, 250, 150))
        self.assertEqual(calibration_parameters.intensity_error_threshold, 1)
        self.assertEqual(calibration_parameters.param_p, 0.75)
        self.assertEqual(calibration_parameters.min_pwm, 150)
        self.assertEqual(calibration_parameters.max_pwm, 250)
        self.assertEqual(calibration_parameters.safe_default_pwm, 150)
        calibration_parameters = PrinterModel.SL1S.calibration_parameters(False)
        self.assertEqual(calibration_parameters.pwms, (30, 250, 208))
        self.assertEqual(calibration_parameters.intensity_error_threshold, 1)
        self.assertEqual(calibration_parameters.param_p, 0.75)
        self.assertEqual(calibration_parameters.min_pwm, 30)
        self.assertEqual(calibration_parameters.max_pwm, 250)
        self.assertEqual(calibration_parameters.safe_default_pwm, 208)


    def test_exposure_panel(self):
        defines.exposure_panel_of_node = self.SAMPLES_DIR / "of_node" / "sl1"
        self.assertEqual(ExposurePanel.printer_model(), PrinterModel.SL1)
        defines.exposure_panel_of_node = self.SAMPLES_DIR / "of_node" / "sl1s"
        self.assertEqual(ExposurePanel.printer_model(), PrinterModel.SL1S)
        self.assertEqual(ExposurePanel.transmittance(), 99.99)
        self.assertEqual(ExposurePanel.serial_number(), "CZPX0712X004X061939")
