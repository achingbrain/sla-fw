# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from slafw import defines
from slafw.hardware.exposure_screen import ExposureScreen
from slafw.hardware.uv_led import UvLed
from slafw.tests.base import SlafwTestCase
from slafw.hardware.printer_model import PrinterModel


class TestPrinterModel(SlafwTestCase):

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

    def test_exposure_screen_parameters(self):
        screen = ExposureScreen(PrinterModel.NONE)
        self.assertEqual(screen.parameters.size_px, (0, 0))
        self.assertEqual(screen.parameters.pixel_size_nm, 0)
        self.assertEqual(screen.parameters.refresh_delay_ms, 0)
        self.assertEqual(screen.parameters.monochromatic, False)
        self.assertEqual(screen.parameters.bgr_pixels, False)
        self.assertEqual(screen.parameters.width_px, 0)
        self.assertEqual(screen.parameters.height_px, 0)
        self.assertEqual(screen.parameters.detected_size_px, (0, 0))
        screen = ExposureScreen(PrinterModel.SL1S)
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

    def test_uv_led_parameters(self):
        # pylint: disable = too-many-function-args
        uv_led = UvLed(PrinterModel.NONE, False)
        self.assertEqual(uv_led.parameters.pwms, (0, 250, 0))
        self.assertEqual(uv_led.parameters.intensity_error_threshold, 1)
        self.assertEqual(uv_led.parameters.param_p, 0.75)
        self.assertEqual(uv_led.parameters.min_pwm, 0)
        self.assertEqual(uv_led.parameters.max_pwm, 250)
        self.assertEqual(uv_led.parameters.safe_default_pwm, 0)
        uv_led = UvLed(PrinterModel.SL1, False) # MC revision < 6c
        self.assertEqual(uv_led.parameters.pwms, (125, 218, 125))
        self.assertEqual(uv_led.parameters.intensity_error_threshold, 1)
        self.assertEqual(uv_led.parameters.param_p, 0.75)
        self.assertEqual(uv_led.parameters.min_pwm, 125)
        self.assertEqual(uv_led.parameters.max_pwm, 218)
        self.assertEqual(uv_led.parameters.safe_default_pwm, 125)
        uv_led = UvLed(PrinterModel.SL1, True) # MC revision >= 6c
        self.assertEqual(uv_led.parameters.pwms, (150, 250, 150))
        self.assertEqual(uv_led.parameters.intensity_error_threshold, 1)
        self.assertEqual(uv_led.parameters.param_p, 0.75)
        self.assertEqual(uv_led.parameters.min_pwm, 150)
        self.assertEqual(uv_led.parameters.max_pwm, 250)
        self.assertEqual(uv_led.parameters.safe_default_pwm, 150)
        uv_led = UvLed(PrinterModel.SL1S, True)
        self.assertEqual(uv_led.parameters.pwms, (30, 250, 208))
        self.assertEqual(uv_led.parameters.intensity_error_threshold, 1)
        self.assertEqual(uv_led.parameters.param_p, 0.75)
        self.assertEqual(uv_led.parameters.min_pwm, 30)
        self.assertEqual(uv_led.parameters.max_pwm, 250)
        self.assertEqual(uv_led.parameters.safe_default_pwm, 208)

    def test_exposure_screen_sn_transmittance(self):
        # TODO: test M1
        defines.exposure_panel_of_node = self.SAMPLES_DIR / "of_node" / "sl1s"
        screen = ExposureScreen(PrinterModel.SL1S)
        self.assertEqual(screen.transmittance, 99.99)
        self.assertEqual(screen.serial_number, "CZPX0712X004X061939")
