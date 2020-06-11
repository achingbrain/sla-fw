# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from typing import Optional

from mock import Mock

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw import defines
from sl1fw.errors.errors import NotUVCalibrated, ResinTooLow
from sl1fw.errors.warnings import PrintingDirectlyFromMedia, ResinNotEnough
from sl1fw.libConfig import HwConfig, RuntimeConfig
from sl1fw.libExposure import Exposure


class TestExposure(Sl1fwTestCase):
    PROJECT = str(Sl1fwTestCase.SAMPLES_DIR / "numbers.sl1")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exposure: Optional[Exposure] = None

    def setUp(self):
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory" / "factory.toml")
        defines.statsData = str(Sl1fwTestCase.TEMP_DIR / "stats.toml")

        self.hw_config = HwConfig()
        self.runtime_config = RuntimeConfig()
        self.screen = Mock()
        self.screen.blitImg.return_value = 100
        self.screen.projectStatus.return_value = True, False

    def test_exposure_init_not_calibrated(self):
        with self.assertRaises(NotUVCalibrated):
            Exposure(self.hw_config, self._get_hw_mock(), self.screen, self.runtime_config, TestExposure.PROJECT)

    def test_exposure_init(self):
        self._fake_calibration()
        Exposure(self.hw_config, self._get_hw_mock(), self.screen, self.runtime_config, TestExposure.PROJECT)

    def test_exposure_load(self):
        self._fake_calibration()
        exposure = Exposure(self.hw_config, self._get_hw_mock(), self.screen, self.runtime_config, TestExposure.PROJECT)
        exposure.startProjectLoading()
        exposure.collectProjectData()

    def test_exposure_start_stop(self):
        exposure = self._run_exposure(self._get_hw_mock())
        self.assertListEqual([PrintingDirectlyFromMedia], [type(warning) for warning in exposure.warnings])

    def test_resin_enough(self):
        hw = self._get_hw_mock()
        hw.getResinVolume.return_value = defines.resinMaxVolume
        exposure = self._run_exposure(hw)
        self.assertNotIn(ResinNotEnough, [type(warning) for warning in exposure.warnings])

    def test_resin_warning(self):
        hw = self._get_hw_mock()
        hw.getResinVolume.return_value = defines.resinMinVolume + 0.1
        exposure = self._run_exposure(hw)
        self.assertIn(ResinNotEnough, [type(warning) for warning in exposure.warnings])

    def test_resin_error(self):
        hw = self._get_hw_mock()
        hw.getResinVolume.return_value = defines.resinMinVolume - 0.1
        exposure = self._run_exposure(hw)
        self.assertIsInstance(exposure.exception, ResinTooLow)

    def _run_exposure(self, hw) -> Exposure:
        self._fake_calibration()
        exposure = Exposure(self.hw_config, hw, self.screen, self.runtime_config, TestExposure.PROJECT)
        exposure.startProjectLoading()
        exposure.collectProjectData()

        exposure.confirm_print_start()
        exposure.doExitPrint()
        exposure.waitDone()
        return exposure

    @staticmethod
    def _get_hw_mock():
        hw = Mock()
        hw.getMinPwm.return_value = defines.uvLedMeasMinPwm500k
        hw.getUvLedState.return_value = (False, 0)
        hw.getUvStatistics.return_value = (6912,)
        hw.isTiltOnPosition.return_value = True
        hw.isTiltMoving.return_value = False
        hw.getMcTemperatures.return_value = [42, 24, 0, 0]
        hw.getResinVolume.return_value = defines.resinMaxVolume
        hw.towerPositonFailed.return_value = False
        hw.getFansError.return_value = {0: False, 1: False, 2: False}
        return hw

    def _fake_calibration(self):
        self.hw_config.uvPwm = defines.uvLedMeasMinPwm500k
        self.hw_config.calibrated = True


if __name__ == "__main__":
    unittest.main()
