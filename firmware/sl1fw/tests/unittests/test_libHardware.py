# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=too-many-public-methods

import os
import unittest
from time import sleep
from typing import Optional

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw import defines
from sl1fw.libConfig import HwConfig
from sl1fw.libHardware import Hardware, MotConComState


class TestLibHardwareConnect(Sl1fwTestCase):
    def setUp(self) -> None:
        super().setUp()
        defines.cpuSNFile = str(self.SAMPLES_DIR / "nvmem")
        defines.cpuTempFile = str(self.SAMPLES_DIR / "cputemp")
        defines.reqMcVersion = "INVALID"
        self.hwConfig = HwConfig(file_path=self.SAMPLES_DIR / "hardware.cfg")
        self.hw = Hardware(self.hwConfig)
        self.hw.start()

    def tearDown(self) -> None:
        self.hw.exit()
        if os.path.isfile(self.EEPROM_FILE):
            os.remove(self.EEPROM_FILE)

    def test_mcc_connect_ok(self) -> None:
        self.assertEqual(MotConComState.OK, self.hw.mcc.connect(MCversionCheck=False))

    def test_mcc_connect_wrong_version(self) -> None:
        self.assertEqual(MotConComState.WRONG_FIRMWARE, self.hw.mcc.connect(MCversionCheck=True))

    def test_mcc_connect_fail(self) -> None:
        self.hw.mcc.getStateBits = lambda x: {'fatal': 1}
        self.hw.mcc.doGetInt = lambda x: 42
        self.assertEqual(MotConComState.UNKNOWN_ERROR, self.hw.mcc.connect(MCversionCheck=False))


class TestLibHardware(Sl1fwTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hwConfig = None
        self.config = None
        self.hw: Optional[Hardware] = None
        self.hw_state = None

    def setUp(self):
        super().setUp()
        defines.cpuSNFile = str(self.SAMPLES_DIR / "nvmem")
        defines.cpuTempFile = str(self.SAMPLES_DIR / "cputemp")
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory/factory.toml")

        self.hwConfig = HwConfig(file_path=self.SAMPLES_DIR / "hardware.cfg")
        self.hw = Hardware(self.hwConfig)

        try:
            self.hw.start()
            self.hw_state = self.hw.connectMC()
        except Exception as exception:
            self.tearDown()
            raise exception

    def tearDown(self):
        self.hw.exit()
        if self.EEPROM_FILE.exists():
            self.EEPROM_FILE.unlink()

    def test_connect(self):
        self.assertEqual(MotConComState.OK, self.hw_state)

    def test_cpu_read(self):
        self.assertEqual("CZPX0819X009XC00151", self.hw.cpuSerialNo)

    def test_info_read(self):
        self.assertRegex(self.hw.mcFwVersion, r"^\d+\.\d+\.\d+[a-zA-Z0-9-+.]*$")
        self.assertEqual("CZPX0619X678XC12345", self.hw.mcSerialNo)
        self.assertEqual(6, self.hw.mcFwRevision)
        self.assertEqual((4, 0), self.hw.mcBoardRevisionBin)
        self.assertEqual("4a", self.hw.mcBoardRevision)

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
        self.assertEqual(['homingFast',
                          'homingSlow',
                          'moveFast',
                          'moveSlow',
                          'layerMoveSlow',
                          'layerRelease',
                          'layerMoveFast',
                          '<reserved2>'],
                         self.hw.getTiltProfilesNames())

        profiles = self.hw.getTiltProfiles()
        self.assertEqual(type([]), type(profiles))

        tower_profiles = self.hw.getTowerProfiles()
        self.assertEqual(type([]), type(tower_profiles))

        tilt_profiles = self.hw.getTiltProfiles()
        self.assertEqual(type([]), type(tilt_profiles))

        # TODO: This just set the profiles, should be nice to set different value and check it is changed
        self.hw.setTiltProfiles(tilt_profiles)
        self.hw.setTowerProfiles(tower_profiles)
        self.hw.setTiltTempProfile(tilt_profiles[0])
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
        self.hw.saveUvStatistics()
        self.hw.clearUvStatistics()
        self.assertEqual([0], self.hw.getUvStatistics())

    def test_voltages(self):
        voltages = self.hw.getVoltages()
        self.assertEqual(4, len(voltages))
        for voltage in voltages:
            self.assertEqual(float, type(voltage))

    def test_camera_led(self):
        self.assertFalse(self.hw.getCameraLedState())
        self.hw.cameraLed(True)
        self.assertTrue(self.hw.getCameraLedState())

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
        self.assertFalse(self.hw.checkState('fans'))

        self.assertEqual({0: False, 1: False, 2: False}, self.hw.getFans())
        for key in range(3):
            self.assertEqual(False, self.hw.fans[key].enabled)
        self.hw.startFans()
        self.assertEqual({0: True, 1: True, 2: True}, self.hw.getFans())
        for key in range(3):
            self.assertEqual(True, self.hw.fans[key].enabled)

        fans = {0: True, 1: False, 2: True}
        self.hw.setFans(fans)
        self.assertEqual(fans, self.hw.getFans())
        for key in fans:
            self.assertEqual(fans[key], self.hw.fans[key].enabled)

        self.hw.stopFans()
        self.assertEqual({0: False, 1: False, 2: False}, self.hw.getFans())
        for key in range(3):
            self.assertEqual(False, self.hw.fans[key].enabled)
        # TODO: Unreliable
        # self.assertEqual({ 0:False, 1:False, 2:False }, self.hw.getFansError())

        # Check mask
        self.assertEqual({0: False, 1: False, 2: False}, self.hw.getFanCheckMask())
        for key in range(3):
            self.assertEqual(False, self.hw.fans[key].mask)

        # RPMs
        # FIXME RPMs are not simulated
        # rpms = { 0:1000, 1:500, 2:800 }
        # self.hw.setFansRpm(rpms)
        # self.assertEqual(rpms, self.hw.getFansRpm())

        # RPMs
        rpms = self.hw.getFansRpm()
        for key, rpm in enumerate(rpms):
            self.assertGreaterEqual(rpm, 0)
            self.assertGreaterEqual(self.hw.fans[key].realRpm, 0)
            # TODO: This is weak test, The simulated value seems random 0 - 20

        # Names
        self.assertEqual("UV LED fan", self.hw.fans[0].name)
        self.assertEqual("blower fan", self.hw.fans[1].name)
        self.assertEqual("rear fan", self.hw.fans[2].name)

    def test_temperatures(self):
        temps = self.hw.getMcTemperatures()
        for temp in temps:
            self.assertGreaterEqual(temp, 0)
        self.assertGreaterEqual(self.hw.getUvLedTemperature(), 0)
        self.assertEqual(53.5, self.hw.getCpuTemperature())

        # TODO: This is weak test, The simulated value seems random 0, 52, 58, 125

    def test_sensor_naming(self):
        self.assertEqual("UV LED temperature", self.hw.getSensorName(0))

    def test_tilt_sync(self):
        self.hw.tiltSync()
        for _ in range(1, 100):
            if self.hw.isTiltSynced():
                break
            sleep(0.1)
        self.assertTrue(self.hw.isTiltSynced())

    def test_tilt_sync_wait(self):
        self.hw.tiltSyncWait()
        self.assertTrue(self.hw.isTiltSynced())

    def test_tilt_move(self):
        position = 10000
        self.hw.tiltMoveAbsolute(position)
        while self.hw.isTiltMoving():
            sleep(0.1)
        self.assertFalse(self.hw.isTiltMoving())
        self.assertTrue(self.hw.isTiltOnPosition())
        self.assertEqual(position, self.hw.getTiltPosition())

    def test_tilt_home(self):
        self.hw.tiltHomeCalibrateWait()
        while self.hw.isTiltMoving():
            sleep(0.1)
        self.assertLess(self.hw.getTiltPosition(), 1000)

    def test_tilt_stop(self):
        position = 1000000
        self.hw.tiltMoveAbsolute(position)
        self.hw.tiltStop()
        self.assertFalse(self.hw.isTiltMoving())

    def test_tilt_up(self):
        self.hw.tiltUp()
        while self.hw.isTiltMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTiltUp())

    def test_tilt_up_wait(self):
        self.hw.tiltUpWait()
        self.assertTrue(self.hw.isTiltUp())

    def test_tilt_down(self):
        self.hw.tiltDown()
        while self.hw.isTiltMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTiltDown())

    def test_tilt_down_wait(self):
        self.hw.tiltDownWait()
        self.assertTrue(self.hw.isTiltDown())

    def test_tilt_max(self):
        self.hw.tiltToMax()
        while self.hw.isTiltMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTiltOnMax())

    def test_tilt_min(self):
        self.hw.tiltToMin()
        while self.hw.isTiltMoving():
            sleep(0.1)
        self.assertTrue(self.hw.isTiltOnMin())

    def test_tilt_set_position(self):
        position = 10000
        self.hw.setTiltPosition(position)
        self.assertEqual(position, self.hw.getTiltPosition())
        self.assertEqual(position, self.hw.getTiltPositionMicroSteps())

    def test_tilt_layer_up(self):
        self.hw.tiltLayerUpWait()

    def test_tilt_layer_down(self):
        self.hw.tiltLayerDownWait()

    def test_tilt_profile(self):
        self.hw.setTiltProfile('homingFast')

    def test_tilt_current(self):
        self.hw.setTiltCurrent(32)
        # TODO: test result

    def test_tower_hold_tilt_release(self):
        self.hw.towerHoldTiltRelease()
        # TODO: test result

    def test_tower_home_calibrate_wait(self):
        self.hw.towerHomeCalibrateWait()
        self.assertEqual(0, self.hw.getTiltPositionMicroSteps())

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

    def test_resin_stir(self):
        self.hw.stirResin()


if __name__ == '__main__':
    unittest.main()
