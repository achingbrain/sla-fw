import logging
import unittest
from mock import Mock
import os
import sys

from sl1fw.tests.gettextSim import fake_gettext

fake_gettext()

# This has to stay in order to prevent loading of real pydbus
import sl1fw.tests.pydbusSim
sys.modules['pydbus'] = sl1fw.tests.pydbusSim

from sl1fw import libExposure
from sl1fw import libConfig
from sl1fw import defines

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)


class TestExposure(unittest.TestCase):
    PROJECT = os.path.join(os.path.dirname(__file__), "samples/numbers.sl1")

    def setUp(self):
        defines.factoryConfigFile = os.path.join(os.path.dirname(__file__), "../../factory/factory.toml")

        hwConfig = libConfig.HwConfig()
        self.config = libConfig.PrintConfig(hwConfig)
        display = Mock()
        display.devices = []
        hw = Mock()
        hw.getUvLedState.return_value = (False, 0)
        screen = Mock()
        screen.blitImg.return_value = 100
        self.exposure = libExposure.Exposure(hwConfig, self.config, display, hw, screen)

    def test_exposure_init(self):
        pass

    def test_exposure_load(self):
        self.config.parseFile(TestExposure.PROJECT)
        self.exposure.setProject(TestExposure.PROJECT)
        self.exposure.loadProject()

    def test_exposure_start_stop(self):
        self.test_exposure_load()

        self.exposure.start()
        self.exposure.doExitPrint()
        self.exposure.waitDone()


if __name__ == '__main__':
    unittest.main()
