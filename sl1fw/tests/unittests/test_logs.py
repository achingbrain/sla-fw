# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import unittest
from functools import partial
from pathlib import Path
from threading import Event
from time import sleep
from unittest.mock import Mock

import pydbus
from pydbus import SystemBus

from sl1fw import defines
from sl1fw.tests import mocks
from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.api.logs0 import Logs0
from sl1fw.states.logs import LogsState, StoreType


class TestLogs0(Sl1fwTestCase):
    def setUp(self):
        super().setUp()

        defines.printer_summary = Path(defines.ramdiskPath) / "printer_summary"

        # Set path to test version of scripts (necessary for log export script to "work")
        scripts_path = Path(mocks.__file__).parent / "scripts"
        os.environ["PATH"] = os.environ["PATH"] + ":" + str(scripts_path.absolute())

        hw = Mock()
        self.waiter = Event()
        type(hw).cpuSerialNo = property(partial(self._get_serial, self.waiter))
        self.logs0_dbus = SystemBus().publish(Logs0.__INTERFACE__, Logs0(hw))
        self.logs0: Logs0 = pydbus.SystemBus().get("cz.prusa3d.sl1.logs0")

    def tearDown(self) -> None:
        self.logs0_dbus.unpublish()
        super().tearDown()

    def test_initial_state(self):
        self.assertEqual(LogsState.IDLE.value, self.logs0.state)
        self.assertEqual(StoreType.IDLE.value, self.logs0.type)
        self.assertEqual(0, self.logs0.export_progress)
        self.assertEqual(0, self.logs0.store_progress)

    def test_cancel(self):
        self.logs0.usb_save()
        for _ in range(50):
            sleep(0.1)
            if self.logs0.state != LogsState.IDLE:
                break
        self.logs0.cancel()
        self.waiter.set()
        for _ in range(100):
            sleep(0.1)
            if self.logs0.state in [LogsState.CANCELED.value, LogsState.FAILED.value, LogsState.FINISHED.value]:
                break
        self.assertEqual(LogsState.CANCELED.value, self.logs0.state)

    def test_usbsave(self):
        self.logs0.usb_save()
        self.waiter.set()
        for _ in range(300):
            sleep(0.1)
            if self.logs0.state in [LogsState.CANCELED.value, LogsState.FAILED.value, LogsState.FINISHED.value]:
                break
        self.assertEqual(StoreType.USB.value, self.logs0.type)
        self.assertEqual(LogsState.FINISHED.value, self.logs0.state)
        self.assertEqual(1, self.logs0.export_progress)
        self.assertEqual(1, self.logs0.store_progress)

    @staticmethod
    def _get_serial(waiter, _):
        waiter.wait()
        return "CZPX0819X009XC00151"


if __name__ == "__main__":
    unittest.main()
