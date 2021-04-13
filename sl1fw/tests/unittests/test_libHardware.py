# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=too-many-public-methods

import os
import unittest
from time import sleep
from typing import Optional
from unittest.mock import Mock

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw import defines
from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.errors.exceptions import MotionControllerException, MotionControllerWrongRevision, MotionControllerWrongFw


class TestLibHardwareConnect(Sl1fwTestCase):
    def setUp(self) -> None:
        super().setUp()
        defines.cpuSNFile = str(self.SAMPLES_DIR / "nvmem")
        defines.cpuTempFile = str(self.SAMPLES_DIR / "cputemp")
        self.hw_config = HwConfig(file_path=self.SAMPLES_DIR / "hardware.cfg")
        self.hw = Hardware(self.hw_config)

        try:
            self.hw.connect()
            self.hw.start()
        except Exception as exception:
            self.tearDown()
            raise exception

    def tearDown(self) -> None:
        self.hw.exit()
        if os.path.isfile(self.EEPROM_FILE):
            os.remove(self.EEPROM_FILE)
        super().tearDown()

    def test_mcc_connect_ok(self) -> None:
        self.assertIsNone(self.hw.mcc.connect(mc_version_check=False))

    def test_mcc_connect_wrong_version(self) -> None:
        defines.reqMcVersion = "INVALID"
        with self.assertRaises(MotionControllerWrongFw):
            self.hw.mcc.connect(mc_version_check=True)

    def test_mcc_connect_fatal_fail(self) -> None:
        self.hw.mcc.getStateBits = Mock(return_value={'fatal': 1})
        with self.assertRaises(MotionControllerException):
            self.hw.mcc.connect(mc_version_check=False)

    def test_mcc_connect_rev_fail(self) -> None:
        self.hw.mcc.doGetIntList = lambda x: [5 ,5] # fw rev 5, board rev 5a
        with self.assertRaises(MotionControllerWrongRevision):
            self.hw.mcc.connect(mc_version_check=False)

    def test_mcc_connect_board_rev_fail(self) -> None:
        self.hw.mcc.doGetIntList = lambda x: [5 ,70] # fw rev 5, board rev 6c
        with self.assertRaises(MotionControllerWrongFw):
            self.hw.mcc.connect(mc_version_check=False)


class TestLibHardware(Sl1fwTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hw_config = None
        self.config = None
        self.hw: Optional[Hardware] = None

    def setUp(self):
        super().setUp()
        defines.cpuSNFile = str(self.SAMPLES_DIR / "nvmem")
        defines.cpuTempFile = str(self.SAMPLES_DIR / "cputemp")
        defines.factoryConfigPath = str(self.SL1FW_DIR / ".." / "factory/factory.toml")
        defines.counterLog = str(self.TEMP_DIR / "uvcounter-log.json")

        self.hw_config = HwConfig(file_path=self.SAMPLES_DIR / "hardware.cfg", is_master=True)
        self.hw = Hardware(self.hw_config)

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

    def test_cpu_read(self):
        self.assertEqual("CZPX0819X009XC00151", self.hw.cpuSerialNo)

    def test_info_read(self):
        self.assertRegex(self.hw.mcFwVersion, r"^\d+\.\d+\.\d+[a-zA-Z0-9-+.]*$")
        self.assertEqual("CZPX0619X678XC12345", self.hw.mcSerialNo)
        self.assertEqual(6, self.hw.mcFwRevision)
        self.assertEqual("6c", self.hw.mcBoardRevision)

    def test_uv_led(self):
        # Default state
        self.assertEqual([0, 0], self.hw.getUvLedState())
        sleep(1)

        # Active state
        self.hw.uvLed(1, 10000)
        state = self.hw.getUvLedState()
        self.assertEqual(1, state[0])
        self.assertGreater(state[1], 5000)

        # Current settings
        pwm = 233
        self.hw.uvLedPwm = pwm
        self.assertEqual(pwm, self.hw.uvLedPwm)

    # TODO: Fix test / functionality
    def test_mcc_debug(self):
        pass

    def test_erase(self):
        self.hw.eraseEeprom()

    def test_profiles(self):
        tower_profiles = self.hw.getTowerProfiles()
        self.assertEqual(type([]), type(tower_profiles))

        # TODO: This just set the profiles, should be nice to set different value and check it is changed
        self.hw.setTowerProfiles(tower_profiles)
        self.hw.setTowerTempProfile(tower_profiles[0])

    def test_stallguard_buffer(self):
        self.assertEqual([], self.hw.getStallguardBuffer())

    def test_beeps(self):
        self.hw.beep(1024, 3)
        self.hw.beepEcho()
        self.hw.beepRepeat(3)
        self.hw.beepAlarm(3)

    def test_power_led(self):
        power_led_mode = 1
        self.hw.powerLedMode = power_led_mode
        self.assertEqual(power_led_mode, self.hw.powerLedMode)

        power_led_speed = 8
        self.hw.powerLedSpeed = power_led_speed
        self.assertEqual(power_led_speed, self.hw.powerLedSpeed)

        power_led_pwm = 100
        self.hw.powerLedPwm = power_led_pwm
        self.assertEqual(power_led_pwm, self.hw.powerLedPwm)

        self.hw.powerLed("warn")
        self.assertEqual(2, self.hw.powerLedMode)
        self.assertEqual(10, self.hw.powerLedSpeed)

    def test_uv_statistics(self):
        # TODO: getUvStatistics simulator seems to return random garbage 4294967295
        # self.assertEqual([0], self.hw.getUvStatistics())
        # clear any garbage
        self.hw.clearUvStatistics()
        self.hw.clearDisplayStatistics()
        self.assertEqual([0, 0], self.hw.getUvStatistics())

    def test_voltages(self):
        voltages = self.hw.getVoltages()
        self.assertEqual(4, len(voltages))
        for voltage in voltages:
            self.assertEqual(float, type(voltage))

    def test_resin_sensor(self):
        self.assertFalse(self.hw.getResinSensorState())
        self.hw.resinSensor(True)
        self.assertTrue(self.hw.getResinSensor())

        self.assertFalse(self.hw.getResinSensorState())

        # self.assertEqual(42, self.hw.getResinVolume())

        self.assertEqual(80, self.hw.calcPercVolume(150))

    def test_cover_closed(self):
        self.assertFalse(self.hw.isCoverClosed())

    def test_power_switch(self):
        self.assertFalse(self.hw.getPowerswitchState())

    def test_fans(self):
        self.assertFalse(self.hw.mcc.checkState('fans'))

        self.assertEqual({0: False, 1: False, 2: False}, self.hw.getFans())

        self.hw.startFans()
        self.assertEqual({0: True, 1: True, 2: True}, self.hw.getFans())

        fans = {0: True, 1: False, 2: True}
        self.hw.setFans(fans)
        self.assertEqual({0: True, 1: False, 2: True}, self.hw.getFans())

        self.hw.stopFans()
        self.assertEqual({0: False, 1: False, 2: False}, self.hw.getFans())
        # TODO: Unreliable
        # self.assertEqual({ 0:False, 1:False, 2:False }, self.hw.getFansError())

        # RPMs
        rpms = [0, 0, 0]
        self.assertEqual(rpms, self.hw.getFansRpm())
        fans = {0: True, 1: True, 2: True}
        self.hw.setFans(fans)
        rpms = [self.hw.config.fan1Rpm, self.hw.config.fan2Rpm, self.hw.config.fan3Rpm]
        self.assertLessEqual(rpms, self.hw.getFansRpm()) # due to rounding

        # setters
        self.assertEqual(len(fans), len(self.hw.fans))
        for key in fans:
            # max RPM
            self.hw.fans[key].targetRpm = defines.fanMaxRPM[key]
            self.assertEqual(defines.fanMaxRPM[key], self.hw.fans[key].targetRpm)
            self.assertEqual(True, self.hw.fans[key].enabled)

            # min RPM
            self.hw.fans[key].targetRpm = defines.fanMinRPM
            self.assertEqual(defines.fanMinRPM, self.hw.fans[key].targetRpm)
            self.assertEqual(True, self.hw.fans[key].enabled)

            # below min RPM (disabled)
            self.hw.fans[key].targetRpm = defines.fanMinRPM - 1
            self.assertEqual(defines.fanMinRPM, self.hw.fans[key].targetRpm)
            self.assertEqual(False, self.hw.fans[key].enabled)

        # override start by enabled
        for key in fans:
            self.hw.fans[key].targetRpm = defines.fanMaxRPM[key]
        self.hw.startFans()
        self.assertEqual({0: True, 1: True, 2: True}, self.hw.getFans())

        for key in fans:
            self.hw.fans[key].targetRpm = defines.fanMinRPM - 1
        self.hw.startFans()
        self.assertEqual({0: False, 1: False, 2: False}, self.hw.getFans())

        # Names
        self.assertEqual("UV LED fan", self.hw.fans[0].name)
        self.assertEqual("blower fan", self.hw.fans[1].name)
        self.assertEqual("rear fan", self.hw.fans[2].name)

    def test_uv_fan_rpm_control(self):
        fans = {0: True, 1: True, 2: True}
        self.hw.setFans(fans)
        rpms = self.hw.getFansRpm()
        self.hw_config.rpmControlOverride = True
        self.hw.uvFanRpmControl()
        self.assertEqual(rpms, self.hw.getFansRpm())
        self.hw_config.rpmControlOverride = False
        self.hw.getUvLedTemperature = Mock(return_value=self.hw_config.rpmControlUvLedMinTemp)
        self.hw.uvFanRpmControl()
        rpms = self.hw.getFansRpm()
        self.assertLessEqual(self.hw_config.rpmControlUvFanMinRpm , rpms[0])
        self.hw.getUvLedTemperature = Mock(return_value=self.hw_config.rpmControlUvLedMaxTemp) #due to rounding in MC
        self.hw.uvFanRpmControl()
        rpms = self.hw.getFansRpm()
        self.assertLessEqual(self.hw_config.rpmControlUvFanMaxRpm , rpms[0])  #due to rounding in MC

    def test_temperatures(self):
        temps = self.hw.getMcTemperatures()
        for temp in temps:
            self.assertGreaterEqual(temp, 0)
        self.assertGreaterEqual(self.hw.getUvLedTemperature(), 0)
        self.assertEqual(53.5, self.hw.getCpuTemperature())

        # TODO: This is weak test, The simulated value seems random 0, 52, 58, 125

    def test_sensor_naming(self):
        self.assertEqual("UV LED temperature", self.hw.getSensorName(0))

    def test_tower_hold_tilt_release(self):
        self.hw.towerHoldTiltRelease()
        # TODO: test result

    def test_tower_home_calibrate_wait(self):
        self.hw.towerHomeCalibrateWait()
        # TODO: test result

    def test_tower_sync(self):
        self.hw.towerSync()
        self.assertFalse(self.hw.isTowerSynced())
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTowerSynced())

    def test_tower_sync_wait(self):
        self.hw.towerSyncWait()
        self.assertTrue(self.hw.isTowerSynced())

    def test_tower_printstart(self):
        self.hw.setTowerProfile('homingFast')
        self.hw.towerToPosition(0.25)
        while not self.hw.isTowerOnPosition(retries=2):
            sleep(0.25)
        self.assertFalse(self.hw.towerPositonFailed())

    def test_tower_move(self):
        position = 100000
        self.hw.towerMoveAbsolute(position)
        self.assertTrue(self.hw.isTowerMoving())
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertFalse(self.hw.isTowerMoving())
        self.assertEqual(position, self.hw.getTowerPositionMicroSteps())

    def test_tower_move_wait(self):
        position = 100000
        self.hw.towerMoveAbsoluteWait(position)
        self.assertFalse(self.hw.isTowerMoving())
        self.assertEqual(position, self.hw.getTowerPositionMicroSteps())
        self.assertTrue(self.hw.isTowerOnPosition(retries=5))

    def test_tower_to_position(self):
        position_mm = 10
        self.hw.towerToPosition(position_mm)
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertEqual("%.3f mm" % position_mm, self.hw.getTowerPosition())

    def test_tower_stop(self):
        position = 100000
        self.hw.towerMoveAbsolute(position)
        self.assertTrue(self.hw.isTowerMoving())
        self.hw.towerStop()
        self.assertFalse(self.hw.isTowerMoving())

    def test_tower_max(self):
        self.hw.towerToMax()
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTowerOnMax())

    def test_tower_min(self):
        self.hw.towerToMin()
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTowerOnMin())

    def test_tower_zero(self):
        self.hw.towerToZero()
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTowerOnZero())

    def test_tower_top(self):
        self.hw.towerToTop()
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTowerOnTop())

    def test_tower_position(self):
        position = 1000000
        self.hw.setTowerPosition(position)
        self.assertEqual("%.3f mm" % (position / 800), self.hw.getTowerPosition())

    def test_tower_profile(self):
        self.hw.setTowerProfile("homingFast")
        # TODO: test result

    def test_tower_current(self):
        current = 32
        self.hw.setTowerCurrent(current)
        # TODO: test result

if __name__ == '__main__':
    unittest.main()
