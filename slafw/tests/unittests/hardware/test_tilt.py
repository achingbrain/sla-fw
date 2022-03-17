# This file is part of the SLA firmware
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import unittest
from time import sleep
from typing import List
from unittest.mock import patch

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.errors.errors import TiltPositionFailed
from slafw.hardware.axis import AxisId
from slafw.hardware.hardware_sl1 import HardwareSL1
from slafw.hardware.printer_model import PrinterModel
from slafw.hardware.tilt import TiltProfile
from slafw.tests.base import SlafwTestCase


class TestTilt(SlafwTestCase):
    # pylint: disable=too-many-public-methods

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hw_config = None
        self.config = None
        self.hw: HardwareSL1 = None

    def patches(self) -> List[patch]:
        return super().patches() + [
            patch("slafw.hardware.a64.temp_sensor.A64CPUTempSensor.CPU_TEMP_PATH", self.SAMPLES_DIR / "cputemp"),
            patch("slafw.defines.cpuSNFile", str(self.SAMPLES_DIR / "nvmem")),
            patch("slafw.defines.counterLog", self.TEMP_DIR / defines.counterLogFilename),
        ]

    def setUp(self):
        super().setUp()

        self.hw_config = HwConfig(file_path=self.SAMPLES_DIR / "hardware.cfg")
        self.hw = HardwareSL1(self.hw_config, PrinterModel.SL1)

        try:
            self.hw.connect()
            self.hw.start()
        except Exception as exception:
            self.tearDown()
            raise exception

    def tearDown(self):
        self.hw.exit()
        if self.EEPROM_FILE.exists():
            self.EEPROM_FILE.unlink()
        super().tearDown()

    def test_limits(self):
        self.assertEqual(self.hw_config.tiltMax, self.hw.tilt.max)
        self.assertEqual(self.hw_config.tiltMin, self.hw.tilt.min)

    def test_position(self):
        positions = [10000, 0]
        for position in positions:
            self.hw.tilt.position = position
            self.assertEqual(position, self.hw.tilt.position)
        self.hw.tilt.move_absolute(self.hw.tilt.max)
        with self.assertRaises(TiltPositionFailed):
            self.hw.tilt.position = position

    def test_movement(self):
        self.assertFalse(self.hw.tilt.moving)
        self.hw.tilt.move_absolute(self.hw.tilt.max)
        self.assertTrue(self.hw.tilt.moving)
        while self.hw.tilt.moving:
            sleep(0.1)
        self.assertFalse(self.hw.tilt.moving)
        self.assertTrue(self.hw.tilt.on_target_position)
        self.assertEqual(self.hw.tilt.max, self.hw.tilt.position)

    # TODO: test all possible scenarios
    def test_move(self):
        # nothing
        self.hw.tilt.position = 0
        self.hw.tilt.profile_id = TiltProfile.temp
        self.hw.tilt.move(speed=0, set_profiles=False, fullstep=False)
        self.assertFalse(self.hw.tilt.moving)
        self.assertEqual(0, self.hw.tilt.position)
        self.assertEqual(TiltProfile.temp, self.hw.tilt.profile_id)
        self.hw.tilt.stop()

        # move up without profile change
        self.hw.tilt.position = 0
        self.hw.tilt.profile_id = TiltProfile.temp
        self.hw.tilt.move(speed=1, set_profiles=False, fullstep=False)
        self.assertTrue(self.hw.tilt.moving)
        self.assertLess(0, self.hw.tilt.position)
        self.assertEqual(TiltProfile.temp, self.hw.tilt.profile_id)
        self.hw.tilt.stop()

        # move up slow with profile change
        self.hw.tilt.position = 0
        self.hw.tilt.profile_id = TiltProfile.temp
        self.hw.tilt.move(speed=1, set_profiles=True, fullstep=False)
        self.assertTrue(self.hw.tilt.moving)
        self.assertLess(0, self.hw.tilt.position)
        self.assertEqual(TiltProfile.moveSlow, self.hw.tilt.profile_id)
        self.hw.tilt.stop()

        # move up fast with profile change
        self.hw.tilt.position = 0
        self.hw.tilt.profile_id = TiltProfile.temp
        self.hw.tilt.move(speed=2, set_profiles=True, fullstep=False)
        self.assertTrue(self.hw.tilt.moving)
        self.assertLess(0, self.hw.tilt.position)
        self.assertEqual(TiltProfile.homingFast, self.hw.tilt.profile_id)
        self.hw.tilt.stop()

        # move up, stop and go to fullstep
        self.hw.tilt.position = 0
        self.hw.tilt.move(speed=1, set_profiles=True, fullstep=False)
        sleep(0.3)
        self.assertTrue(self.hw.tilt.moving)
        self.assertLess(0, self.hw.tilt.position)
        self.hw.tilt.stop()
        position = self.hw.tilt.position
        self.hw.tilt.move(speed=0, set_profiles=True, fullstep=True)
        while self.hw.tilt.moving:
            sleep(0.1)
        self.assertLessEqual(position, self.hw.tilt.position)
        self.assertTrue(self.hw.tilt.position - position, 31)

        # move only between valid limits
        self.hw.tilt.position = 0
        self.hw.tilt.move(speed=-2, set_profiles=True, fullstep=False)
        while self.hw.tilt.moving:
            sleep(0.1)
        self.assertEqual(self.hw.tilt.position, 0)  # tilt not going below 0
        self.hw.tilt.position = self.hw.config.tiltMax
        self.hw.tilt.move(speed=2, set_profiles=True, fullstep=False)
        while self.hw.tilt.moving:
            sleep(0.1)
        self.assertEqual(self.hw.tilt.position, self.hw.config.tiltMax)  # tilt not going above tiltMax

    def test_sensitivity(self):
        with self.assertRaises(ValueError):
            self.hw.updateMotorSensitivity(AxisId.TILT, -3)
        with self.assertRaises(ValueError):
            self.hw.updateMotorSensitivity(AxisId.TILT, 3)
        sensitivities = [-2, -1, 0, 1, 2]
        with open(os.path.join(defines.dataPath, PrinterModel.SL1.name, "default.tilt"), "r") as f:
            original_profiles = json.loads(f.read())
        for sensitivity in sensitivities:
            adjusted_profiles = self.hw.get_profiles_with_sensitivity(original_profiles, AxisId.TILT, sensitivity)
            self.hw.updateMotorSensitivity(AxisId.TILT, sensitivity)
            self.assertEqual(self.hw.tilt.profiles, adjusted_profiles)

    # FIXME: test go_to_fullstep. Simulator behaves differently from real HW ()

    def test_stir_resin(self):
        self.hw.tilt.stir_resin()
        self.assertTrue(self.hw.tilt.synced)
        self.assertEqual(0, self.hw.tilt.position)

    def test_sync(self):
        self.hw.tilt.sync()
        self.assertLess(0, self.hw.tilt.homing_status)
        for _ in range(1, 100):
            if self.hw.tilt.synced:
                break
            sleep(0.1)
        self.assertEqual(0, self.hw.tilt.homing_status)
        self.assertTrue(self.hw.tilt.synced)
        self.hw.motorsRelease()
        self.assertFalse(self.hw.tilt.synced)

    def test_sync_wait(self):
        self.hw.tilt.sync_wait()
        self.assertTrue(self.hw.tilt.synced)
        self.assertEqual(0, self.hw.tilt.position)
        self.assertTrue(self.hw.tilt.on_target_position)

    def test_profile_names(self):
        self.assertEqual(
            [
                "temp",
                "homingFast",
                "homingSlow",
                "moveFast",
                "moveSlow",
                "layerMoveSlow",
                "layerRelease",
                "layerMoveFast",
                "reserved2",
            ],
            self.hw.tilt.profile_names,
        )

    def test_profile_id(self):
        profiles = [TiltProfile.layerMoveFast, TiltProfile.layerMoveSlow]
        for profile in profiles:
            self.hw.tilt.profile_id = profile
            self.assertEqual(profile, self.hw.tilt.profile_id)

    def test_profile(self):
        testProfile = [12345, 23456, 234, 345, 28, 8, 1234]
        self.hw.tilt.profile_id = TiltProfile.reserved2
        self.assertNotEqual(testProfile, self.hw.tilt.profile)
        self.hw.tilt.profile = testProfile
        self.assertEqual(testProfile, self.hw.tilt.profile)

    def test_profiles(self):
        profiles = self.hw.tilt.profiles
        self.assertEqual(type([]), type(profiles))
        self.assertEqual(8, len(profiles))  # all except temp
        for profile in profiles:
            self.assertEqual(7, len(profile))
            self.assertEqual(type([int]), type(profile))
        for profile_id, data in enumerate(profiles):
            self.hw.tilt.profile_id = TiltProfile(profile_id)
            self.assertEqual(TiltProfile(profile_id), self.hw.tilt.profile_id)
            self.assertEqual(data, self.hw.tilt.profile)

    def test_home(self):
        self.hw.tilt.home_calibrate_wait()
        while self.hw.tilt.moving:
            sleep(0.1)
        self.assertEqual(0, self.hw.tilt.position)
        self.assertTrue(self.hw.tilt.synced)

    def test_stop(self):
        self.hw.tilt.position = 0
        self.hw.tilt.move_absolute(self.hw_config.tiltMax)
        self.hw.tilt.stop()
        self.assertFalse(self.hw.tilt.moving)
        self.assertLess(0, self.hw.tilt.position)
        self.assertGreater(self.hw_config.tiltMax, self.hw.tilt.position)
        self.assertFalse(self.hw.tilt.on_target_position)

    def test_up(self):
        self.hw.tilt.move_up()
        while self.hw.tilt.moving:
            sleep(0.1)
        self.assertTrue(self.hw.tilt.on_target_position)

    def test_up_wait(self):
        self.hw.tilt.move_up_wait()
        self.assertTrue(self.hw.tilt.on_target_position)

    def test_down(self):
        self.hw.tilt.move_down()
        while self.hw.tilt.moving:
            sleep(0.1)
        self.assertTrue(self.hw.tilt.on_target_position)

    def test_down_wait(self):
        self.hw.tilt.move_down_wait()
        self.assertTrue(self.hw.tilt.on_target_position)

    def test_layer_up(self):
        self.hw.tilt.layer_up_wait()

    def test_layer_down(self):
        self.hw.tilt.layer_down_wait()


if __name__ == "__main__":
    unittest.main()
