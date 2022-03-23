# This file is part of the SLA firmware
# Copyright (C) 2021-2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock
from unittest.mock import patch

from slafw.errors.errors import UnknownPrinterModel
from slafw.hardware.printer_model import PrinterModel
from slafw.libPrinter import Printer
from slafw.states.printer import PrinterState
from slafw.tests.base import RefCheckTestCase, SlafwTestCaseDBus


class TestPrinterSetup(SlafwTestCaseDBus):
    printer: Printer

    def tearDown(self) -> None:
        self.printer.stop()
        del self.printer.exposure_image
        del self.printer

        super().tearDown()

    def test_setup_ok(self) -> None:
        self.printer = Printer()
        self.printer.setup()
        self.printer.hw.config.factory_reset()  # Ensure this tests does not depend on previous config

    @patch("slafw.hardware.hardware_sl1.SL1ExposureScreen.start", Mock(side_effect = UnknownPrinterModel()))
    def test_setup_fail(self) -> None:
        self.printer = Printer()
        observer = Mock(__name__="mock")
        self.printer.state_changed.connect(observer)
        self.printer.setup()
        self.printer.hw.config.factory_reset()  # Ensure this tests does not depend on previous config
        observer.assert_called()
        self.assertEqual(PrinterState.EXCEPTION, self.printer.state)
        self.assertIsInstance(self.printer.fatal_error, UnknownPrinterModel)


class TestPrinter(SlafwTestCaseDBus, RefCheckTestCase):
    printer: Printer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @patch("slafw.hardware.printer_model.PrinterModel.detect_model", Mock(return_value=PrinterModel.SL1))
    def setUp(self) -> None:
        super().setUp()

        self.printer = Printer()
        self.printer.setup()
        self.printer.hw.config.factory_reset()  # Ensure this tests does not depend on previous config

    def tearDown(self) -> None:
        self.printer.stop()
        del self.printer.exposure_image
        del self.printer

        super().tearDown()

    def test_print_readiness_properties(self):
        # Create mocks for registering callbacks being called. __name__ set to satisfy PySignal
        unboxed_callback = Mock(__name__="unboxed_callback")
        self_tested_callback = Mock(__name__="self_tested_callback")
        mechanically_calibrated_callback = Mock(__name__="mechanically_calibrated_callback")
        uv_calibrated_callback = Mock(__name__="uv_calibrated_callback")

        # Connect callbacks
        self.printer.unboxed_changed.connect(unboxed_callback)
        self.printer.self_tested_changed.connect(self_tested_callback)
        self.printer.mechanically_calibrated_changed.connect(mechanically_calibrated_callback)
        self.printer.uv_calibrated_changed.connect(uv_calibrated_callback)

        # Check initial state
        self.assertFalse(self.printer.unboxed)
        self.assertFalse(self.printer.self_tested)
        self.assertFalse(self.printer.mechanically_calibrated)
        self.assertFalse(self.printer.uv_calibrated)

        # Change state of all conditions
        self.printer.hw.config.showUnboxing = False
        self.printer.hw.config.showWizard = False
        self.printer.hw.config.calibrated = True
        self.printer.hw.config.uvPwm = 208

        # Check changed state
        self.assertTrue(self.printer.unboxed)
        self.assertTrue(self.printer.self_tested)
        self.assertTrue(self.printer.mechanically_calibrated)
        self.assertTrue(self.printer.uv_calibrated)

        unboxed_callback.assert_called_once()
        self_tested_callback.assert_called_once()
        mechanically_calibrated_callback.assert_called_once()
        uv_calibrated_callback.assert_called_once()
