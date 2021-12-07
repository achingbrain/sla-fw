# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import gc
import unittest
import weakref
from pathlib import Path
from time import sleep
from typing import Type

import pydbus

from sl1fw.tests.integration.base import Sl1FwIntegrationTestCaseBase
from sl1fw.exposure.exposure import Exposure
from sl1fw.api.exposure0 import Exposure0
from sl1fw.state_actions.manager import ActionManager
from sl1fw.api.printer0 import Printer0State, Printer0


class TestIntegrationPrinter0(Sl1FwIntegrationTestCaseBase):
    def setUp(self):
        super().setUp()
        self.printer0: Printer0 = pydbus.SystemBus().get("cz.prusa3d.sl1.printer0")

    def test_initial_state(self):
        self.assertEqual(Printer0State.IDLE.value, self.printer0.state)

    def test_homing(self):
        self.printer0.tower_home()
        self.printer0.tilt_home()
        self.printer0.disable_motors()

    def test_control_moves(self):
        self.printer0.tower_move(2)
        sleep(0.1)
        self.printer0.tower_move(0)
        sleep(0.1)
        self.printer0.tower_move(1)
        sleep(0.1)
        self.printer0.tower_move(0)
        sleep(0.1)
        self.printer0.tower_move(-1)
        sleep(0.1)
        self.printer0.tower_move(0)
        sleep(0.1)
        self.printer0.tower_move(-2)
        sleep(0.1)
        self.printer0.tower_move(0)

        self.printer0.tilt_move(2)
        sleep(0.1)
        self.printer0.tilt_move(0)
        sleep(0.1)
        self.printer0.tilt_move(1)
        sleep(0.1)
        self.printer0.tilt_move(0)
        sleep(0.1)
        self.printer0.tilt_move(-1)
        sleep(0.1)
        self.printer0.tilt_move(0)
        sleep(0.1)
        self.printer0.tilt_move(-2)
        sleep(0.1)
        self.printer0.tilt_move(0)

    def test_absolute_moves(self):
        self.printer0.tower_home()
        initial = self.printer0.tower_position_nm
        offset = 12500
        self.printer0.tower_position_nm += offset
        for _ in range(1, 30):
            sleep(0.1)
            if self.printer0.tower_position_nm == initial + offset:
                break
        self.assertAlmostEqual(self.printer0.tower_position_nm, initial + offset, 12500)

        self.printer0.tilt_home()
        initial = self.printer0.tilt_position
        offset = 12500
        self.printer0.tilt_position += offset
        for _ in range(1, 30):
            sleep(0.1)
            if self.printer0.tilt_position == initial + offset:
                break
        self.assertAlmostEqual(self.printer0.tilt_position, initial + offset, 12500)

        # self.printer0.get_projects()
        # self.printer0.get_firmwares()

    def test_info_read(self):
        self.assertEqual(self.printer0.serial_number, "CZPX0819X009XC00151")
        self.assertGreater(len(self.printer0.system_name), 3)
        self.assertEqual(type(self.printer0.system_name), str)
        self.assertEqual(type(self.printer0.system_version), str)
        self.assertEqual(
            {
                "fan0": {"rpm": 0, "error": False},
                "fan1": {"rpm": 0, "error": False},
                "fan2": {"rpm": 0, "error": False},
            },
            self.printer0.fans
        )
        self.assertEqual(
            {"temp0_celsius": 46.7, "temp1_celsius": 26.1, "temp2_celsius": 0.0, "temp3_celsius": 0.0},
            self.printer0.temps
        )
        self.assertEqual(type(self.printer0.cpu_temp), float)
        self.assertEqual(
            self.printer0.leds,
            {"led0_voltage_volt": 0.0, "led1_voltage_volt": 0.0, "led2_voltage_volt": 0.0, "led3_voltage_volt": 17.8},
        )
        # TODO: Chained dbus call ends in deadlock
        # self.assertEqual(self.printer0.devlist, {})
        # TODO: Statistics report out of range integer
        # self.assertTrue('uv_stat0' in self.printer0.uv_statistics)
        self.assertRegex(self.printer0.controller_sw_version, ".*\\..*\\..*")
        self.assertEqual(self.printer0.controller_serial, "CZPX0619X678XC12345")
        self.assertEqual(self.printer0.controller_revision, "6c")
        self.assertEqual(self.printer0.http_digest, True)
        self.assertEqual(self.printer0.api_key, "32LF9aXN")
        self.assertEqual(self.printer0.tilt_fast_time_sec, 5.5)
        self.assertEqual(self.printer0.tilt_slow_time_sec, 8.0)
        self.printer0.enable_resin_sensor(True)
        self.printer0.enable_resin_sensor(False)
        self.assertEqual(self.printer0.cover_state, False)
        self.assertEqual(self.printer0.power_switch_state, False)
        self.assertTrue(self.printer0.factory_mode)
        self.assertTrue(self.printer0.admin_enabled)

        # self.printer0.display_test()
        # self.printer0.wizard()
        # self.printer0.update_firmware()
        # self.printer0.factory_reset()
        # self.printer0.print()

    def test_project_list_raw(self):
        project_list = self.printer0.list_projects_raw()
        self.assertTrue(project_list)
        for project in project_list:
            self.assertTrue(Path(project).is_file())
            self.assertRegex(Path(project).name, r".*\.sl1")

    def test_print_start(self):
        # Fake calibration
        self.printer.hw.config.calibrated = True

        # Test print start
        path = self.printer0.print(str(self.SAMPLES_DIR / "numbers.sl1"), False)
        self.assertNotEqual(path, "/")
        self.assertEqual(Printer0State.PRINTING, Printer0State(self.printer0.state))

    def test_exposure_gc(self):
        # Fake calibration
        self.printer.hw.config.calibrated = True

        initial_exposure0 = self._get_num_instances(Exposure0)
        initial_exposure = self._get_num_instances(Exposure)

        # Start and cancel more than max exposures -> force exposure gc
        for _ in range(ActionManager.MAX_EXPOSURES + 1):
            path = self.printer0.print(str(self.SAMPLES_DIR / "numbers.sl1"), False)
            exposure0 = pydbus.SystemBus().get("cz.prusa3d.sl1.exposure0", path)
            exposure0.cancel()

        # Make sure we are not keeping extra exposure objects
        self.assertEqual(self._get_num_instances(Exposure0) - initial_exposure0, ActionManager.MAX_EXPOSURES)
        self.assertEqual(self._get_num_instances(Exposure) - initial_exposure, ActionManager.MAX_EXPOSURES)

    @staticmethod
    def _get_num_instances(instance_type: Type) -> int:
        gc.collect()
        counter = 0
        for obj in gc.get_objects():
            try:
                if isinstance(obj, instance_type) and not isinstance(obj, weakref.ProxyTypes):
                    counter += 1
            except ReferenceError:
                # Weak reference target just disappeared, does not count
                pass
        return counter


if __name__ == "__main__":
    unittest.main()
