# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from typing import Optional

from mock import Mock

from sl1fw.errors.errors import NotUVCalibrated
from sl1fw.tests.base import Sl1fwTestCase

from sl1fw.libExposure import Exposure
from sl1fw.libConfig import HwConfig, RuntimeConfig
from sl1fw import defines


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
        self.hw = Mock()
        self.hw.getMinPwm.return_value = defines.uvLedMeasMinPwm500k
        self.hw.getUvLedState.return_value = (False, 0)
        self.hw.getUvStatistics.return_value = (6912,)
        self.screen = Mock()
        self.screen.blitImg.return_value = 100
        self.screen.projectStatus.return_value = True, False

    def test_exposure_init_not_calibrated(self):
        with self.assertRaises(NotUVCalibrated):
            Exposure(self.hw_config, self.hw, self.screen, self.runtime_config, TestExposure.PROJECT)

    def test_exposure_init(self):
        self._fake_calibration()
        Exposure(self.hw_config, self.hw, self.screen, self.runtime_config, TestExposure.PROJECT)

    def test_exposure_load(self):
        self._fake_calibration()
        exposure = Exposure(self.hw_config, self.hw, self.screen, self.runtime_config, TestExposure.PROJECT)
        exposure.startProjectLoading()
        exposure.collectProjectData()

    def test_exposure_start_stop(self):
        self._fake_calibration()
        exposure = Exposure(self.hw_config, self.hw, self.screen, self.runtime_config, TestExposure.PROJECT)
        exposure.startProjectLoading()
        exposure.collectProjectData()

        exposure.start()
        exposure.doExitPrint()
        exposure.waitDone()

    def _fake_calibration(self):
        self.hw_config.uvPwm = self.hw.getMinPwm()
        self.hw_config.calibrated = True


if __name__ == "__main__":
    unittest.main()
