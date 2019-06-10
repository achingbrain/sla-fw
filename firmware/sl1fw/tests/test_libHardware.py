import unittest
from mock import Mock
import os
import gettext
import sys
import time

gettext.install('sl1fw')

sys.modules['gpio'] = Mock()

from sl1fw.libHardware import Hardware
from sl1fw.libConfig import HwConfig, PrintConfig
from sl1fw.tests.mcPortSim import MCPortSim
from sl1fw import defines

defines.cpuSNFile = os.path.join(os.path.dirname(__file__), "samples/nvmem")
defines.cpuTempFile = os.path.join(os.path.dirname(__file__), "samples/cputemp")
defines.factoryConfigFile = os.path.join(os.path.dirname(__file__), "../../factory/factory.toml")


class TestLibHardware(unittest.TestCase):
    EEPROM_FILE = "EEPROM.dat"

    def setUp(self):
        self.hwConfig = HwConfig(os.path.join(os.path.dirname(__file__), "samples/hardware.cfg"))
        self.config = PrintConfig(self.hwConfig)
        self.mcsimport = MCPortSim()
        self.hw = Hardware(self.hwConfig, self.config, serial_port=self.mcsimport, debug=Mock())

        self.hw.connectMC(Mock(), Mock())

    def tearDown(self):
        self.mcsimport.stop()
        if os.path.isfile(self.EEPROM_FILE):
            os.remove(self.EEPROM_FILE)

    def test_connect(self):
        pass

    def test_cpu_read(self):
        self.assertEqual("CZPX0819X009XC00151", self.hw.cpuSerialNo)

    def test_info_read(self):
        try:
            # Use this in Python3 only code:
            self.assertRegex(self.hw.mcVersion, "SLA-control.*")
        except AttributeError:
            self.assertTrue(self.hw.mcVersion.startswith("SLA-control"))

        self.assertEqual("CZPX0619X678XC12345", self.hw.mcSerialNo)
        self.assertEqual("6 4", self.hw.mcRevision)

    def test_motor_onoff(self):
        self.hw.motorsHold()
        self.hw.tiltMoveAbsolute(1000)
        self.hw.motorsRelease()

        # TODO: This is just test of a test

    def test_uv_led(self):
        # Default state
        self.assertEqual([0, 0], self.hw.getUvLedState())
        time.sleep(1)

        # Active state
        self.hw.uvLed(1, 10000)
        state = self.hw.getUvLedState()
        self.assertEqual(1, state[0])
        self.assertGreater(state[1], 5000)

        # Current settings
        current = 640
        self.hw.setUvLedCurrent(current)
        self.assertEqual(current, self.hw.getUvLedCurrent())

    # TODO: Fix test / functinoality
    # def test_dummy_switch(self):
    #     # Set current
    #     current = 640
    #     self.hw.setUvLedCurrent(current)
    #     self.assertEqual(current, self.hw.getUvLedCurrent())
    #
    #     # Switch to dummy and change current
    #     self.hw.switchToDummy()
    #     self.hw.setUvLedCurrent(current + 10)
    #
    #     # Switch back adn see nothing changed
    #     self.hw.switchToMC(Mock(), Mock())
    #     self.assertEqual(current, self.hw.getUvLedCurrent())

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
        self.hw.setTiltTempProfile(tilt_profiles)
        self.hw.setTowerTempProfile(tower_profiles)

    def test_stallguard_buffer(self):
        self.assertEqual([], self.hw.getStallguardBuffer())

    def test_beeps(self):
        self.hw.beep(1024, 3)
        self.hw.beepEcho()
        self.hw.beepRepeat(3)
        self.hw.beepAlarm(3)

    def test_power_led(self):
        self.assertEqual(1, self.hw.getPowerLedMode())
        self.assertEqual(8, self.hw.getPowerLedSpeed())
        self.assertEqual(100, self.hw.getPowerLedPwm())

        self.hw.powerLed("warn")
        self.assertEqual(2, self.hw.getPowerLedMode())
        self.assertEqual(10, self.hw.getPowerLedSpeed())

        # TODO: Not passing with MC simulator
        # pwm = 255
        # self.hw.setPowerLedPwm(pwm)
        # self.assertEqual(pwm, self.hw.getPowerLedPwm())

        speed = 42
        self.hw.setPowerLedSpeed(speed)
        self.assertEqual(42, self.hw.getPowerLedSpeed())

    def test_uv_statistics(self):
        self.assertEqual([0], self.hw.getUvStatistics())
        self.hw.saveUvStatistics()
        self.hw.clearUvStatistics()
        self.assertEqual([0], self.hw.getUvStatistics())

    def test_voltages(self):
        voltages = self.hw.getVoltages()
        self.assertEqual(4 , len(voltages))
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

    def test_power_sitch(self):
        self.assertFalse(self.hw.getPowerswitchState())

    def test_fans(self):
        self.assertFalse(self.hw.checkState('fans'))

        self.assertEqual([False, False, False], self.hw.getFans())
        self.hw.startFans()
        self.assertEqual([True, True, True], self.hw.getFans())

        fans = [True, False, True]
        self.hw.setFans(fans)
        self.assertEqual(fans, self.hw.getFans())

        self.hw.stopFans()
        self.assertEqual([False, False, False], self.hw.getFans())
        self.assertEqual((False, False, False), self.hw.getFansError())

        # Check mask
        self.assertEqual([False, False, False], self.hw.getFanCheckMask())

        mask = [True, True, True]
        self.hw.setFanCheckMask(mask)
        self.assertEqual(mask, self.hw.getFanCheckMask())

        # PWMs
        self.assertEqual([60, 100, 40], self.hw.getFansPwm())
        pwms = [80, 20, 60]
        self.hw.setFansPwm(pwms)
        self.assertEqual(pwms, self.hw.getFansPwm())

        # RPMs
        rpms = self.hw.getFansRpm()
        for rpm in rpms:
            self.assertGreaterEqual(rpm, 0)
            # TODO: This is weak test, The simulated value seems random 0 - 20

        # Names
        self.assertEqual("UV LED fan", self.hw.getFanName(0))
        self.assertEqual("blower fan", self.hw.getFanName(1))
        self.assertEqual("rear fan", self.hw.getFanName(2))

    def test_temperatures(self):
        temps = self.hw.getMcTemperatures()
        for temp in temps:
            self.assertGreaterEqual(temp, 0)
        self.assertGreaterEqual(self.hw.getUvLedTemperature(), 0)
        self.assertEqual(53.5, self.hw.getCpuTemperature())

        # TODO: This is weak test, The simulated value seems random 0, 52, 58, 125

    def test_sensor_naming(self):
        self.assertEqual("UV LED temperature", self.hw.getSensorName(0))

    def test_mechanics(self):
        # TODO: This test is weak and some functionality is even not enabled due to MC sim deficiencies

        self.hw.towerHoldTiltRelease()
        # self.hw.towerHomeCalibrateWait()
        self.hw.towerSync()

        self.assertFalse(self.hw.isTowerSynced())

        # self.hw.towerSyncWait()
        self.hw.towerSyncFailed()

        # self.hw.towerMoveAbsoluteWait(1000)
        self.hw.towerMoveAbsolute(1000)
        self.hw.towerToPosition(10)
        self.hw.towerStop()
        self.assertFalse(self.hw.isTowerMoving())
        # self.assertFalse(self.hw.isTowerOnPosition())
        self.hw.towerToZero()
        self.assertFalse(self.hw.isTowerOnZero())
        self.hw.towerToTop()
        self.assertFalse(self.hw.isTowerOnTop())
        self.hw.setTowerOnMax()
        self.hw.towerToMax()
        self.assertFalse(self.hw.isTowerOnMax())
        self.hw.towerToMin()
        self.assertFalse(self.hw.isTowerOnMin())
        self.hw.setTowerPosition(1000)
        self.hw.getTowerPosition()
        self.hw.getTowerPositionMicroSteps()
        self.hw.setTowerProfile("homingFast")
        self.hw.setTowerCurrent(0)
        # self.hw.tiltHomeCalibrateWait()
        self.hw.tiltSync()
        self.assertFalse(self.hw.isTiltSynced())
        # self.hw.tiltSyncWait()
        self.hw.tiltSyncFailed()
        self.hw.tiltMoveAbsolute(1000)
        self.hw.tiltStop()
        self.assertTrue(self.hw.isTiltMoving())
        self.assertFalse(self.hw.isTiltOnPosition())
        self.hw.tiltDown()
        self.assertFalse(self.hw.isTiltDown())
        # self.hw.tiltDownWait()
        self.hw.tiltUp()
        self.hw.isTiltUp()
        # self.hw.tiltUpWait()
        self.hw.tiltToMax()
        self.assertFalse(self.hw.isTiltOnMax())
        self.hw.tiltToMin()
        self.hw.isTiltOnMin()
        # self.hw.tiltLayerDownWait()
        # self.hw.tiltLayerUpWait()
        self.hw.setTiltPosition(1000)
        self.hw.getTiltPosition()
        self.hw.getTiltPositionMicroSteps()
        self.hw.setTiltProfile(0)
        self.hw.setTiltCurrent(0)

    # def test_resin_stir(self):
    #     self.hw.stirResin()


if __name__ == '__main__':
    unittest.main()
