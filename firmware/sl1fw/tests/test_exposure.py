import unittest
from mock import Mock
import gettext
import os

gettext.install('sl1fw', 'locales')

from sl1fw import libExposure
from sl1fw import libConfig


class TestExposure(unittest.TestCase):
    PROJECT = os.path.join(os.path.dirname(__file__), "samples/empty-sample.sl1")

    def setUp(self):
        hwConfig = libConfig.HwConfig()

        self.config = libConfig.PrintConfig(hwConfig)
        display = Mock()
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
