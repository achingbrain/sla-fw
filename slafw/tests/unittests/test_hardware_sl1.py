# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=too-many-public-methods

import unittest
from time import sleep
from typing import Optional, List
from unittest.mock import Mock, PropertyMock, patch

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.hardware.a64.temp_sensor import A64CPUTempSensor
from slafw.hardware.hardware_sl1 import HardwareSL1
from slafw.hardware.power_led import PowerLedActions
from slafw.hardware.printer_model import PrinterModel
from slafw.hardware.sl1.uv_led import SL1UVLED
from slafw.tests.base import SlafwTestCase


class TestSL1Hardware(SlafwTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hw_config: Optional[HwConfig] = None
        self.hw: Optional[HardwareSL1] = None

    def setUp(self):
        super().setUp()

        A64CPUTempSensor.CPU_TEMP_PATH.write_text("53500")
        self.hw_config = HwConfig(file_path=self.SAMPLES_DIR / "hardware.cfg", is_master=True)
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

    def patches(self) -> List[patch]:
        return super().patches() + [
            patch("slafw.hardware.base.fan.Fan.AUTO_CONTROL_INTERVAL_S", 1),
            patch("slafw.defines.cpuSNFile", str(self.SAMPLES_DIR / "nvmem")),
            patch("slafw.hardware.a64.temp_sensor.A64CPUTempSensor.CPU_TEMP_PATH", self.TEMP_DIR / "cputemp"),
            patch("slafw.defines.counterLog", str(self.TEMP_DIR / "uvcounter-log.json")),
        ]

    def test_cpu_read(self):
        self.assertEqual("CZPX0819X009XC00151", self.hw.cpuSerialNo)

    def test_info_read(self):
        self.assertRegex(self.hw.mcFwVersion, r"^\d+\.\d+\.\d+[a-zA-Z0-9-+.]*$")
        self.assertEqual("CZPX0619X678XC12345", self.hw.mcSerialNo)
        self.assertEqual(6, self.hw.mcFwRevision)
        self.assertEqual("6c", self.hw.mcBoardRevision)

    def test_uv_led(self):
        # Default state
        self.assertEqual(0, self.hw.uv_led.active)
        self.assertEqual(0, self.hw.uv_led.pulse_remaining)
        sleep(1)

        # Active state
        self.hw.uv_led.pulse(10000)
        self.assertEqual(1, self.hw.uv_led.active)
        self.assertGreater(self.hw.uv_led.pulse_remaining, 5000)

        # Current settings
        pwm = 233
        self.hw.uv_led.pwm = pwm
        self.assertEqual(pwm, self.hw.uv_led.pwm)

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

    def test_power_led_mode_normal(self):
        power_led_mode = PowerLedActions.Normal
        self.hw.power_led.mode = power_led_mode
        self.assertEqual(power_led_mode, self.hw.power_led.mode)

    def test_power_led_intensity(self):
        power_led_pwm = 100
        self.hw.power_led.intensity = power_led_pwm
        self.assertEqual(power_led_pwm, self.hw.power_led.intensity)

    def test_power_led_mode_warning(self):
        self.hw.power_led.mode = PowerLedActions.Warning
        self.assertEqual(PowerLedActions.Warning, self.hw.power_led.mode)

    def test_power_led_error(self):
        self.assertEqual(1, self.hw.power_led.set_error())
        self.assertEqual(PowerLedActions.Error, self.hw.power_led.mode)
        self.assertEqual(2, self.hw.power_led.set_error())
        self.assertEqual(PowerLedActions.Error, self.hw.power_led.mode)
        self.assertEqual(1, self.hw.power_led.remove_error())
        self.assertEqual(PowerLedActions.Error, self.hw.power_led.mode)
        self.assertEqual(0, self.hw.power_led.remove_error())
        self.assertEqual(PowerLedActions.Normal, self.hw.power_led.mode)

    def test_power_led_warning(self):
        self.assertEqual(1, self.hw.power_led.set_warning())
        self.assertEqual(PowerLedActions.Warning, self.hw.power_led.mode)
        self.assertEqual(2, self.hw.power_led.set_warning())
        self.assertEqual(PowerLedActions.Warning, self.hw.power_led.mode)
        self.assertEqual(1, self.hw.power_led.remove_warning())
        self.assertEqual(PowerLedActions.Warning, self.hw.power_led.mode)
        self.assertEqual(0, self.hw.power_led.remove_warning())
        self.assertEqual(PowerLedActions.Normal, self.hw.power_led.mode)

    def test_power_led_mixed(self):
        self.assertEqual(1, self.hw.power_led.set_warning())
        self.assertEqual(PowerLedActions.Warning, self.hw.power_led.mode)
        self.assertEqual(1, self.hw.power_led.set_error())
        self.assertEqual(PowerLedActions.Error, self.hw.power_led.mode)
        self.assertEqual(2, self.hw.power_led.set_warning())
        self.assertEqual(PowerLedActions.Error, self.hw.power_led.mode)
        self.assertEqual(0, self.hw.power_led.remove_error())
        self.assertEqual(PowerLedActions.Warning, self.hw.power_led.mode)
        self.assertEqual(1, self.hw.power_led.remove_warning())
        self.assertEqual(PowerLedActions.Warning, self.hw.power_led.mode)
        self.assertEqual(0, self.hw.power_led.remove_warning())
        self.assertEqual(PowerLedActions.Normal, self.hw.power_led.mode)

    def test_uv_statistics(self):
        # clear any garbage
        self.hw.uv_led.clear_usage()
        self.hw.display.clear_usage()

        self.assertEqual(0, self.hw.uv_led.usage_s)
        self.assertEqual(0, self.hw.display.usage_s)
        self.hw.uv_led.pulse(1000)
        sleep(1)
        self.assertEqual(1, self.hw.uv_led.usage_s)
        self.assertEqual(1, self.hw.display.usage_s)
        self.hw.uv_led.clear_usage()
        self.assertEqual(0, self.hw.uv_led.usage_s)
        self.assertEqual(1, self.hw.display.usage_s)
        self.hw.display.clear_usage()
        self.assertEqual(0, self.hw.uv_led.usage_s)
        self.assertEqual(0, self.hw.display.usage_s)

    def test_uv_display_counter(self):
        self.hw.uv_led.off()
        # clear any garbage
        self.hw.uv_led.clear_usage()
        self.hw.display.clear_usage()

        self.assertEqual(0, self.hw.uv_led.usage_s)
        self.assertEqual(0, self.hw.display.usage_s)
        uv_stats = self.hw.uv_led.usage_s
        display_stats = self.hw.display.usage_s
        sleep(1)
        self.assertEqual(0, uv_stats)
        self.assertGreater(1, display_stats)
        self.hw.display.stop_counting_usage()
        uv_stats = self.hw.uv_led.usage_s
        display_stats = self.hw.display.usage_s
        sleep(1)
        self.assertEqual(uv_stats, self.hw.uv_led.usage_s)
        self.assertEqual(display_stats, self.hw.display.usage_s)

    def test_voltages(self):
        if not isinstance(self.hw.uv_led, SL1UVLED):
            return

        voltages = self.hw.uv_led.read_voltages()
        self.assertEqual(4, len(voltages))
        for voltage in voltages:
            self.assertEqual(float, type(voltage))

    def test_resin_sensor(self):
        self.assertFalse(self.hw.getResinSensorState())
        self.hw.resinSensor(True)
        self.assertTrue(self.hw.getResinSensor())

        self.assertFalse(self.hw.getResinSensorState())

        # self.assertEqual(42, self.hw.get_resin_volume())

        self.assertEqual(80, self.hw.calcPercVolume(150))

    def test_cover_closed(self):
        self.assertFalse(self.hw.isCoverClosed())

    def test_power_switch(self):
        self.assertFalse(self.hw.getPowerswitchState())

    def test_fans(self):
        self.assertFalse(self.hw.mcc.checkState('fans'))

        self.assertFalse(self.hw.uv_led_fan.enabled)
        self.assertFalse(self.hw.blower_fan.enabled)
        self.assertFalse(self.hw.rear_fan.enabled)

        self.hw.startFans()
        self.assertTrue(self.hw.uv_led_fan.enabled)
        self.assertTrue(self.hw.blower_fan.enabled)
        self.assertTrue(self.hw.rear_fan.enabled)

        self.hw.uv_led_fan.enabled = True
        self.hw.blower_fan.enabled = False
        self.hw.rear_fan.enabled = True

        self.assertTrue(self.hw.uv_led_fan.enabled)
        self.assertFalse(self.hw.blower_fan.enabled)
        self.assertTrue(self.hw.rear_fan.enabled)

        self.hw.stopFans()
        self.assertFalse(self.hw.uv_led_fan.enabled)
        self.assertFalse(self.hw.blower_fan.enabled)
        self.assertFalse(self.hw.rear_fan.enabled)

        # TODO: Unreliable
        # self.assertEqual({ 0:False, 1:False, 2:False }, self.hw.getFansError())

        # RPMs
        self.assertEqual(0, self.hw.uv_led_fan.rpm)
        self.assertEqual(0, self.hw.blower_fan.rpm)
        self.assertEqual(0, self.hw.rear_fan.rpm)
        self.hw.startFans()
        sleep(3)  # Wait for fans to stabilize
        self.assertLessEqual(self.hw.config.fan1Rpm, self.hw.uv_led_fan.rpm)  # due to rounding
        self.assertLessEqual(self.hw.config.fan2Rpm, self.hw.blower_fan.rpm)  # due to rounding
        self.assertLessEqual(self.hw.config.fan3Rpm, self.hw.rear_fan.rpm)  # due to rounding

        # Setters
        self.assertEqual(3, len(self.hw.fans))
        for key in self.hw.fans:
            # max RPM
            self.hw.fans[key].target_rpm = defines.fanMaxRPM[key]
            self.assertEqual(defines.fanMaxRPM[key], self.hw.fans[key].target_rpm)
            self.assertEqual(True, self.hw.fans[key].enabled)

            # min RPM
            self.hw.fans[key].target_rpm = defines.fanMinRPM
            self.assertEqual(defines.fanMinRPM, self.hw.fans[key].target_rpm)
            self.assertEqual(True, self.hw.fans[key].enabled)

            # below min RPM (exception)
            with self.assertRaises(ValueError):
                self.hw.fans[key].target_rpm = defines.fanMinRPM - 1

    def test_uv_fan_rpm_control(self):
        self.hw.uv_led_fan.enabled = True
        # self.hw_config.rpmControlOverride = True
        sleep(1)
        self.hw.uv_led_fan.auto_control = False
        rpm = self.hw.uv_led_fan.rpm
        sleep(1)
        self.assertEqual(rpm, self.hw.uv_led_fan.rpm)
        # self.hw_config.rpmControlOverride = False
        self.hw.uv_led_fan.auto_control = True
        self.hw.uv_led_temp = Mock()
        type(self.hw.uv_led_temp).value = PropertyMock(return_value=self.hw_config.rpmControlUvLedMinTemp)
        sleep(1)  # Wait for fans to stabilize
        rpm = self.hw.uv_led_fan.rpm
        self.assertLessEqual(self.hw_config.rpmControlUvFanMinRpm, rpm)
        # due to rounding in MC
        type(self.hw.uv_led_temp).value = PropertyMock(return_value=self.hw_config.rpmControlUvLedMaxTemp)
        sleep(1)  # Wait for fans to stabilize
        rpm = self.hw.uv_led_fan.rpm
        # due to rounding in MC
        self.assertLessEqual(self.hw_config.rpmControlUvFanMaxRpm, rpm)

    def test_temperatures(self):
        self.assertGreaterEqual(self.hw.uv_led_temp.value, 0)
        self.assertGreaterEqual(self.hw.ambient_temp.value, 0)
        self.assertEqual(53.5, self.hw.cpu_temp.value)

        # TODO: This is weak test, The simulated value seems random 0, 52, 58, 125

    def test_tower_hold_tilt_release(self):
        self.hw.towerHoldTiltRelease()
        # TODO: test result

    def test_tower_home_calibrate_wait(self):
        self.hw.towerHomeCalibrateWait()
        # TODO: test result

    def test_tower_sync(self):
        self.hw.towerSync()
        self.assertTrue(self.hw.isTowerMoving())
        while self.hw.isTowerMoving():
            self.assertFalse(self.hw.isTowerSynced())
            sleep(0.25)
        self.assertTrue(self.hw.isTowerSynced())

    def test_tower_sync_wait(self):
        self.hw.towerSyncWait()
        self.assertTrue(self.hw.isTowerSynced())

    def test_tower_printstart(self):
        self.hw.setTowerProfile('homingFast')
        self.hw.tower_position_nm = 0.25 * 1_000_000
        while not self.hw.isTowerOnPosition(retries=2):
            sleep(0.25)
        self.assertFalse(self.hw.towerPositonFailed())

    def test_tower_move(self):
        position = 100000
        self.hw.tower_position_nm = position
        self.assertTrue(self.hw.isTowerMoving())
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertFalse(self.hw.isTowerMoving())
        self.assertEqual(position, self.hw.tower_position_nm)

    def test_tower_move_wait(self):
        position = 100000
        self.hw.tower_move_absolute_nm_wait(position)
        self.assertFalse(self.hw.isTowerMoving())
        self.assertEqual(position, self.hw.tower_position_nm)
        self.assertTrue(self.hw.isTowerOnPosition(retries=5))

    def test_tower_to_position(self):
        position_nm = 10_000_000
        self.hw.tower_position_nm = position_nm
        while self.hw.isTowerMoving():
            sleep(0.1)
        self.assertEqual(position_nm, self.hw.tower_position_nm)

    def test_tower_stop(self):
        position = 100000
        self.hw.tower_position_nm = position
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

    def test_tower_position(self):
        position = 1000000
        self.hw.set_tower_position_nm(position)
        self.assertEqual(position, self.hw.tower_position_nm)

    def test_tower_profile(self):
        self.hw.setTowerProfile("homingFast")
        # TODO: test result

    def test_tower_current(self):
        current = 32
        self.hw.setTowerCurrent(current)
        # TODO: test result


if __name__ == '__main__':
    unittest.main()
