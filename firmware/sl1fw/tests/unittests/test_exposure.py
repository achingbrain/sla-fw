import unittest
from mock import Mock

from sl1fw.tests.base import Sl1fwTestCase

from sl1fw import libExposure
from sl1fw.libConfig import HwConfig
from sl1fw import defines


class TestExposure(Sl1fwTestCase):
    PROJECT = str(Sl1fwTestCase.SAMPLES_DIR / "numbers.sl1")

    def __init__(self, *args, **kwargs):
        self.exposure = None

        super().__init__(*args, **kwargs)

    def setUp(self):
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory" / "factory.toml")

        hw_config = HwConfig()
        display = Mock()
        display.devices = []
        hw = Mock()
        hw.getUvLedState.return_value = (False, 0)
        screen = Mock()
        screen.blitImg.return_value = 100
        self.exposure = libExposure.Exposure(hw_config, display, hw, screen)

    def test_exposure_init(self):
        pass

    def test_exposure_load(self):
        self.exposure.setProject(TestExposure.PROJECT)
        self.exposure.parseProject(TestExposure.PROJECT)
        self.exposure.loadProject()

    def test_exposure_start_stop(self):
        self.test_exposure_load()

        self.exposure.start()
        self.exposure.doExitPrint()
        self.exposure.waitDone()


if __name__ == '__main__':
    unittest.main()
