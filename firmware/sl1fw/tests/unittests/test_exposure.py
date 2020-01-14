# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from typing import Optional

from mock import Mock

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

        hw_config = HwConfig()
        runtime_config = RuntimeConfig()
        hw = Mock()
        hw.getUvLedState.return_value = (False, 0)
        hw.getUvStatistics.return_value = (6912,)
        screen = Mock()
        screen.blitImg.return_value = 100
        screen.projectStatus.return_value = True, False
        self.exposure = Exposure(hw_config, hw, screen, runtime_config)

    def test_exposure_init(self):
        pass

    def test_exposure_load(self):
        self.exposure.setProject(TestExposure.PROJECT)
        self.exposure.startProjectLoading()
        self.exposure.collectProjectData()

    def test_exposure_start_stop(self):
        self.test_exposure_load()

        self.exposure.start()
        self.exposure.doExitPrint()
        self.exposure.waitDone()


if __name__ == '__main__':
    unittest.main()
