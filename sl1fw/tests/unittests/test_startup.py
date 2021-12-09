# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from datetime import datetime, timedelta
from shutil import copyfile
from time import sleep
from typing import Optional
from unittest.mock import Mock

from sl1fw import defines
from sl1fw.errors.errors import OldExpoPanel
from sl1fw.hardware.printer_model import PrinterModel
from sl1fw.states.wizard import WizardId
from sl1fw.states.printer import PrinterState
from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.libPrinter import Printer


class TestStartup(Sl1fwTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.printer: Optional[Printer] = None  # This is here to provide type hint on self.printer

    def setUp(self) -> None:
        super().setUp()
        defines.sl1_model_file.unlink()
        defines.sl1s_model_file.touch()   # Set SL1S as the current model

        self.printer = Printer()

        # Init state
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

        # Default setup
        self.printer.hw.config.factory_reset()  # Ensure this tests does not depend on previous config
        self.printer.hw.exposure_screen.start = Mock(return_value=PrinterModel.SL1S)
        self.printer.hw.sl1s_booster = Mock()
        self.printer.hw.config.showUnboxing = False
        self.printer.hw.config.showWizard = False
        self.printer.hw.config.calibrated = True
        self.printer.hw.config.uvPwm = 208

    def tearDown(self) -> None:
        self.printer.stop()
        del self.printer
        super().tearDown()

    def test_expo_panel_log_first_record(self):
        self._run_printer()
        self.assertEqual(self.printer.state, PrinterState.RUNNING)      # no wizard is running, no error is raised
        with open(defines.expoPanelLogPath, "r") as f:
            log = json.load(f)
        self.assertEqual(1, len(log))                                   # log holds only one record
        last_key = list(log)[-1]
        self.assertTrue(abs(datetime.strptime(last_key, "%Y-%m-%d %H:%M:%S") - datetime.now().replace(
            microsecond=0)) < timedelta(seconds=5))
        self.assertEqual(self.printer.hw.exposure_screen.panel.serial_number(), log[last_key]["panel_sn"])
        self.assertRaises(KeyError, lambda: log[last_key]["counter_s"])

    def test_expo_panel_log_sl1(self):
        self.printer.hw.exposure_screen.start = Mock(return_value=PrinterModel.SL1)
        defines.sl1s_model_file.unlink()
        defines.sl1_model_file.touch()  # Set SL1 as the current model

        self._run_printer()
        self.assertEqual(self.printer.state, PrinterState.RUNNING)  # no wizard is running, no error is raised
        with self.assertRaises(FileNotFoundError):
            _ = open(defines.expoPanelLogPath, "r")

    def test_expo_panel_log_new_record(self):
        copyfile(self.SAMPLES_DIR / defines.expoPanelLogFileName, defines.expoPanelLogPath)

        self._run_printer()
        self.printer.run_make_ready_to_print()
        for _ in range(100):
            if self.printer.state == PrinterState.WIZARD:
                break
            sleep(0.1)
        self.assertEqual(self.printer.state, PrinterState.WIZARD)  # wizard is running, no error is raised
        self.assertEqual(
            self.printer.action_manager._wizard.identifier, WizardId.NEW_EXPO_PANEL)  # pylint: disable=protected-access
        with open(defines.expoPanelLogPath, "r") as f:
            log = json.load(f)
        self.assertEqual(3, len(log))  # log holds records from sample file

        last_key = list(log)[-1]  # last record has to be newly added
        self.assertNotEqual(
            self.printer.hw.exposure_screen.panel.serial_number(),
            log[last_key]["panel_sn"])  # wizard is not done, so new panel is not recorded

    def test_expo_panel_log_old_panel(self):
        copyfile(self.SAMPLES_DIR / defines.expoPanelLogFileName, defines.expoPanelLogPath)
        self.printer.hw.exposure_screen.panel.serial_number = Mock(return_value="CZPX2921X021X000262")
        observer = Mock(__name__ = "MockObserver")
        self.printer.exception_occurred.connect(observer)
        self._run_printer()
        self.printer.run_make_ready_to_print()
        for _ in range(100):
            if self.printer.state == PrinterState.WIZARD:
                break
            sleep(0.1)
        with open(defines.expoPanelLogPath, "r") as f:
            log = json.load(f)
        next_to_last_key = list(log)[-2]    # get counter_s from sample file
        observer.assert_called_with(OldExpoPanel(counter_h=round(log[next_to_last_key]["counter_s"] / 3600)))
        self.assertEqual(self.printer.state, PrinterState.WIZARD)       # wizard is running

    def _run_printer(self):
        self.printer.setup()
