# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import patch

from slafw.hardware.sl1.exposure_screen import ExposureScreenSL1
from slafw.tests.base import SlafwTestCase
from slafw.hardware.printer_model import PrinterModel
from slafw.hardware.sl1.uv_led import UvLedSL1
from slafw.tests.mocks.motion_controller import MotionControllerMock


class TestPrinterModel(SlafwTestCase):

    def test_name(self):
        model = PrinterModel.NONE
        self.assertEqual(model.name, "NONE")
        model = PrinterModel.SL1S
        self.assertEqual(model.name, "SL1S")

    def test_value(self):
        self.assertEqual(0, PrinterModel.NONE.value)
        self.assertEqual(1, PrinterModel.SL1.value)
        self.assertEqual(2, PrinterModel.SL1S.value)
        self.assertEqual(3, PrinterModel.M1.value)

    def test_extensions(self):
        model = PrinterModel.NONE
        self.assertEqual(model.extensions, {""})
        model = PrinterModel.SL1S
        self.assertEqual(model.extensions, {".sl1s"})

    def test_exposure_screen_parameters(self):
        screen = ExposureScreenSL1(PrinterModel.NONE)
        self.assertEqual(screen.parameters.size_px, (0, 0))
        self.assertEqual(screen.parameters.pixel_size_nm, 0)
        self.assertEqual(screen.parameters.refresh_delay_ms, 0)
        self.assertEqual(screen.parameters.monochromatic, False)
        self.assertEqual(screen.parameters.bgr_pixels, False)
        self.assertEqual(screen.parameters.width_px, 0)
        self.assertEqual(screen.parameters.height_px, 0)
        self.assertEqual(screen.parameters.detected_size_px, (0, 0))
        screen = ExposureScreenSL1(PrinterModel.SL1S)
        self.assertEqual(screen.parameters.size_px, (1620, 2560))
        self.assertEqual(screen.parameters.pixel_size_nm, 50000)
        self.assertEqual(screen.parameters.refresh_delay_ms, 0)
        self.assertEqual(screen.parameters.monochromatic, True)
        self.assertEqual(screen.parameters.bgr_pixels, True)
        self.assertEqual(screen.parameters.width_px, 1620)
        self.assertEqual(screen.parameters.height_px, 2560)
        self.assertEqual(screen.parameters.detected_size_px, (540, 2560))

    def test_options(self):
        options = PrinterModel.NONE.options
        self.assertEqual(options.has_tilt, False)
        self.assertEqual(options.has_booster, False)
        self.assertEqual(options.vat_revision, 0)
        self.assertEqual(options.has_UV_calibration, False)
        self.assertEqual(options.has_UV_calculation, False)

    def test_uv_led_parameters_none(self):
        uv_led = UvLedSL1(MotionControllerMock.get_5a(), PrinterModel.NONE)
        self.assertEqual(uv_led.parameters.pwms, (0, 250, 0))
        self.assertEqual(uv_led.parameters.intensity_error_threshold, 1)
        self.assertEqual(uv_led.parameters.param_p, 0.75)
        self.assertEqual(uv_led.parameters.min_pwm, 0)
        self.assertEqual(uv_led.parameters.max_pwm, 250)
        self.assertEqual(uv_led.parameters.safe_default_pwm, 0)

    def test_uv_led_parameters_sl1(self):
        uv_led = UvLedSL1(MotionControllerMock.get_5a(), PrinterModel.SL1)  # MC revision < 6c
        self.assertEqual(uv_led.parameters.pwms, (125, 218, 125))
        self.assertEqual(uv_led.parameters.intensity_error_threshold, 1)
        self.assertEqual(uv_led.parameters.param_p, 0.75)
        self.assertEqual(uv_led.parameters.min_pwm, 125)
        self.assertEqual(uv_led.parameters.max_pwm, 218)
        self.assertEqual(uv_led.parameters.safe_default_pwm, 125)

    def test_uv_led_parameters_sl1_500khz(self):
        uv_led = UvLedSL1(MotionControllerMock.get_6c(), PrinterModel.SL1)  # MC revision >= 6c
        self.assertEqual(uv_led.parameters.pwms, (150, 250, 150))
        self.assertEqual(uv_led.parameters.intensity_error_threshold, 1)
        self.assertEqual(uv_led.parameters.param_p, 0.75)
        self.assertEqual(uv_led.parameters.min_pwm, 150)
        self.assertEqual(uv_led.parameters.max_pwm, 250)
        self.assertEqual(uv_led.parameters.safe_default_pwm, 150)

    def test_uv_led_parameters_sl1s(self):
        uv_led = UvLedSL1(MotionControllerMock.get_6c(), PrinterModel.SL1S)
        self.assertEqual(uv_led.parameters.pwms, (30, 250, 208))
        self.assertEqual(uv_led.parameters.intensity_error_threshold, 1)
        self.assertEqual(uv_led.parameters.param_p, 0.75)
        self.assertEqual(uv_led.parameters.min_pwm, 30)
        self.assertEqual(uv_led.parameters.max_pwm, 250)
        self.assertEqual(uv_led.parameters.safe_default_pwm, 208)

    def test_exposure_screen_sn_transmittance_sl1s(self):
        self.exposure_screen_sn_transmittance(PrinterModel.SL1S)

    def test_exposure_screen_sn_transmittance_m1(self):
        self.exposure_screen_sn_transmittance(PrinterModel.M1)

    def exposure_screen_sn_transmittance(self, model: PrinterModel):
        hw_node = self.SAMPLES_DIR / "of_node" / model.name.lower()
        with patch("slafw.defines.exposure_panel_of_node", hw_node):
            screen = ExposureScreenSL1(model)
            self.assertEqual(4.17, screen.transmittance)
            self.assertEqual("CZPX0712X004X061939", screen.serial_number)
