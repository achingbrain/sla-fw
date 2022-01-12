# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

import pydbus

from slafw.tests.integration.base import SlaFwIntegrationTestCaseBase
from slafw.api.printer0 import Printer0


class TestIntegrationConfig0(SlaFwIntegrationTestCaseBase):
    def setUp(self):
        super().setUp()
        self.config0: Printer0 = pydbus.SystemBus().get("cz.prusa3d.sl1.config0")

    def test_value_read(self):
        self.assertEqual(6, self.config0.MCBoardVersion)
        self.assertTrue(self.config0.showWizard) # selftest is skipped in setUp so this flag is set to True forcing user to successfully pass it before print
        self.assertFalse(self.config0.MCversionCheck)
        self.assertEqual(5, self.config0.stirringDelay)
        self.assertTrue(self.config0.autoOff)
        self.assertEqual(4928, self.config0.tiltHeight)
        self.assertEqual(0, self.config0.tiltSensitivity)
        self.assertEqual(40, self.config0.calibTowerOffset)
        self.assertEqual(8.0, self.config0.tiltSlowTime)
        self.assertFalse(self.config0.calibrated)
        self.assertEqual(96000, self.config0.towerHeight)
        self.assertEqual(-1, self.config0.towerSensitivity)
        self.assertTrue(self.config0.coverCheck)
        self.assertEqual(1250, self.config0.tower_microstep_size_nm)
        self.assertEqual(0, self.config0.delayAfterExposure)
        self.assertEqual(0, self.config0.trigger)
        self.assertEqual(0, self.config0.delayBeforeExposure)
        self.assertEqual(list, type(self.config0.tuneTilt))
        self.assertEqual(1800, self.config0.fan1Rpm)
        self.assertFalse(self.config0.upAndDownEveryLayer)
        self.assertEqual(3300, self.config0.fan2Rpm)
        self.assertEqual(0, self.config0.upAndDownExpoComp)
        self.assertEqual(1000, self.config0.fan3Rpm)
        self.assertFalse(self.config0.upAndDownUvOn)
        self.assertTrue(self.config0.fanCheck)
        self.assertEqual(10, self.config0.upAndDownWait)
        self.assertFalse(self.config0.layerTowerHop)
        self.assertEqual(0, self.config0.upAndDownZoffset)
        self.assertEqual(1, self.config0.limit4fast)
        self.assertEqual(140, self.config0.uvCalibIntensity)
        self.assertEqual(800, self.config0.microStepsMM)
        self.assertEqual(90, self.config0.uvCalibMinIntEdge)
        self.assertFalse(self.config0.mute)
        self.assertEqual(0, self.config0.uvCurrent)
        self.assertEqual(204, self.config0.uvPwm)
        self.assertEqual(0, self.config0.uvPwmTune)
        self.assertEqual(204, self.config0.uvPwmPrint)
        self.assertFalse(self.config0.perPartes)
        self.assertEqual(120, self.config0.uvWarmUpTime)
        self.assertEqual(100, self.config0.pwrLedPwm)
        self.assertTrue(self.config0.resinSensor)
        self.assertEqual(dict, type(self.config0.constraints))

        # TODO: Test update_motor_sensitivity
        # TODO: Test save


if __name__ == "__main__":
    unittest.main()
