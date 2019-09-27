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
        defines.statsData = str(Sl1fwTestCase.TEMP_DIR / "stats.toml")

        hw_config = HwConfig()
        display = Mock()
        display.devices = []
        hw = Mock()
        hw.getUvLedState.return_value = (False, 0)
        hw.getUvStatistics.return_value = (6912,)
        screen = Mock()
        screen.blitImg.return_value = 100
        screen.projectStatus.return_value = True, False, list()
        self.exposure = libExposure.Exposure(hw_config, display, hw, screen)

    def test_exposure_init(self):
        pass

    def test_exposure_load(self):
        self.exposure.setProject(TestExposure.PROJECT)
        self.exposure.parseProject(TestExposure.PROJECT)
        self.exposure.startProjectLoading()
        self.exposure.collectProjectData()

    def test_exposure_start_stop(self):
        self.test_exposure_load()

        self.exposure.start()
        self.exposure.doExitPrint()
        self.exposure.waitDone()


if __name__ == '__main__':
    unittest.main()
