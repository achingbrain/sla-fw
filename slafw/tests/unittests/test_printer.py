# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional
from unittest.mock import Mock, patch

from slafw.hardware.printer_model import PrinterModel
from slafw.tests.base import RefCheckTestCase, SlafwTestCaseDBus
from slafw.libPrinter import Printer


class TestPrinter(SlafwTestCaseDBus, RefCheckTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.printer: Optional[Printer] = None  # This is here to provide type hint on self.printer

    @patch("slafw.hardware.printer_model.PrinterModel.detect_model", Mock(return_value=PrinterModel.SL1))
    def setUp(self) -> None:
        super().setUp()

        self.printer = Printer()
        self.printer.hw.config.factory_reset()  # Ensure this tests does not depend on previous config
        self.printer.setup()

    def tearDown(self) -> None:
        self.printer.stop()
        self.printer = None

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
