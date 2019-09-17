import unittest
from shutil import copyfile

from sl1fw.tests.base import Sl1fwTestCase

from sl1fw.libConfig import *
from sl1fw import defines


class TestHardwareConfig(Sl1fwTestCase):
    def __init__(self, *args, **kwargs):
        self.hw_config = None
        super().__init__(*args, **kwargs)

    def setUp(self):
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory/factory.toml")
        defines.hwConfigFile = str(self.SAMPLES_DIR / "hardware.cfg")
        copyfile(defines.hwConfigFile, "hwconfig.test")
        self.hw_config = HwConfig(defines.hwConfigFile)

    def tearDown(self):
        os.remove("hwconfig.test")

    def test_read(self):
        self.hw_config.logAllItems()
        self.hw_config.logFile()

        self.assertTrue(self.hw_config.coverCheck, "Test cover check read")
        self.assertFalse(self.hw_config.calibrated, "Test calibrated read")
        self.assertEqual(self.hw_config.layerTowerHop, 0, "Test layerTowerHop read")

    def test_write(self):
        self.hw_config.update(towerHeight=-1)
        tower_height = 1024
        self.hw_config.update(towerHeight=tower_height)

        self.assertEqual(self.hw_config.towerHeight, tower_height, "Check towerHeight is set")

        self.hw_config.update(uvPwm=222)

        self.hw_config.logAllItems()
        self.hw_config.logFile()
        self.assertTrue(self.hw_config.writeFile("hwconfig.test"), "Write config file")
        self.assertEqual(self.hw_config.getSourceString(),
                         "MCBoardVersion = 6\r\n"
                         "showUnboxing = no\r\n"
                         "MCversionCheck = no\r\n"
                         "autoOff = on\r\n"
                         "towerHeight = 1024\r\n"
                         "uvPwm = 222",
                         "Check file lines append")

        self.hw_config.update(MCBoardVersion=None)
        self.hw_config.logFile()
        self.assertTrue(self.hw_config.writeFile("hwconfig.test"), "Write config file")
        self.assertEqual(self.hw_config.getSourceString(),
                         "showUnboxing = no\r\n"
                         "MCversionCheck = no\r\n"
                         "autoOff = on\r\n"
                         "towerHeight = 1024\r\n"
                         "uvPwm = 222",
                         "Check file lines delete")

    def test_uvledpwm1(self):
        hw_config = HwConfig(str(self.SAMPLES_DIR / "hardware.cfg"))
        self.assertEqual(hw_config.uvPwm, 219, "UV LED PWM - No defaults at all")

    def test_uvledpwm2(self):
        hw_config = HwConfig(str(self.SAMPLES_DIR / "hardware-current.cfg"))
        self.assertEqual(hw_config.uvPwm, 152, "UV LED PWM - current to PWM")

    def test_uvledpwm3(self):
        hw_config = HwConfig(str(self.SAMPLES_DIR / "hardware-pwm.cfg"))
        self.assertEqual(hw_config.uvPwm, 142, "UV LED PWM - direct PWM")

    def test_uvledpwm4(self):
        with open(str(self.SAMPLES_DIR / "hardware-current.toml"), "r") as factory:
            factory_defaults = toml.load(factory)
        # endwith
        hw_config = HwConfig(str(self.SAMPLES_DIR / "hardware.cfg"), factory_defaults)
        self.assertEqual(hw_config.uvPwm, 243, "UV LED PWM - default current to PWM")

    def test_uvledpwm5(self):
        with open(str(self.SAMPLES_DIR / "hardware-pwm.toml"), "r") as factory:
            factory_defaults = toml.load(factory)
        # endwith
        hw_config = HwConfig(str(self.SAMPLES_DIR / "hardware.cfg"), factory_defaults)
        self.assertEqual(hw_config.uvPwm, 123, "UV LED PWM - default direct PWM")


class TestPrintConfig(Sl1fwTestCase):
    def setUp(self):
        defines.hwConfigFile = str(self.SAMPLES_DIR / "samples/hardware.cfg")
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory/factory.toml")
        self.hwConfig = HwConfig(defines.hwConfigFile)

    def test_read(self):
        config = PrintConfig(self.hwConfig)
        config.logAllItems()
        config.logFile()

        self.assertEqual(config.projectName, "no project", "Check empty project name")

        config.parseFile(str(self.SAMPLES_DIR / "numbers.sl1"))

        self.assertIs(config.zipError, None, "Test for no read errors")

        config.logAllItems()
        config.logFile()

        self.assertEqual(config.projectName, "numbers", "Check projectName")
        self.assertEqual(config.totalLayers, 2, "Check total layers count")

        logging.info(config.getSourceString())
        config.update(expTime=5)

        self.assertEqual(config.expTime, 5, "Check expTime value")

        # config.writeFile("printconfig.txt")


class TestWizardData(Sl1fwTestCase):
    def setUp(self):
        defines.hwConfigFile = str(self.SAMPLES_DIR / "wizardData.cfg")
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory/factory.toml")
        from shutil import copyfile
        copyfile(defines.hwConfigFile, "wizardData.test")
        self.wizardData = WizardData(defines.hwConfigFile)

    def tearDown(self):
        os.remove("wizardData.test")

    def test_lists(self):
        sensor_data = [98, 105, 108, 128, 136, 111, 145]
        perc_diff = [-23.4, -17.9, -15.6, 0.0, 6.3, -13.3, 13.3, -6.2, -10.9, -18.7]
        self.wizardData.update(uvSensorData=sensor_data, uvPercDiff=perc_diff)

        self.assertEqual(self.wizardData.uvSensorData, sensor_data, "Check uvSensorData is set")
        self.assertEqual(self.wizardData.uvPercDiff, perc_diff, "Check uvSensorData is set")

        self.wizardData.logAllItems()
        self.wizardData.logFile()
        print(self.wizardData.getJson())

        self.wizardData.writeFile("wizardData.test")
        self.assertEqual(self.wizardData.getSourceString(),
                         "uvSensorData = 98 105 108 128 136 111 145\r\n"
                         "uvPercDiff = -23.4 -17.9 -15.6 0.0 6.3 -13.3 13.3 -6.2 -10.9 -18.7",
                         "Check file lines")

        self.assertEqual(self.wizardData.uvSensorData, sensor_data, "Test sensor data read")
        self.assertEqual(self.wizardData.uvPercDiff, perc_diff, "Test perc diff read")


class TestConfigHelper(Sl1fwTestCase):
    CONFIG_PATH = "config.cfg"

    def setUp(self):
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory/factory.toml")
        self.hwConfig = HwConfig(TestConfigHelper.CONFIG_PATH)
        self.helper = ConfigHelper(self.hwConfig)

    def tearDown(self):
        if os.path.exists(TestConfigHelper.CONFIG_PATH):
            os.remove(TestConfigHelper.CONFIG_PATH)

    def test_boolValueStore(self):
        self.helper.autoOff = True
        self.helper.resinSensor = False

        self.assertTrue(self.helper.autoOff)
        self.assertFalse(self.helper.resinSensor)
        self.assertIsInstance(self.helper.autoOff, bool)
        self.assertIsInstance(self.helper.resinSensor, bool)

    def test_integerValueStore(self):
        self.helper.towerHeight = 42

        self.assertEqual(self.helper.towerHeight, 42)
        self.assertIsInstance(self.helper.towerHeight, int)

    def test_floatValueStore(self):
        self.helper.pixelSize = 4.2

        self.assertAlmostEqual(self.helper.pixelSize, 4.2)
        self.assertIsInstance(self.helper.pixelSize, float)

    def test_commit(self):
        # Fresh helper is not changed
        self.assertFalse(self.helper.changed())
        self.assertFalse(self.helper.changed('autoOff'))
        self.assertFalse(self.helper.changed('pixelSize'))

        self.helper.autoOff = False

        # Underling valus is intact before commit
        self.assertTrue(self.hwConfig.autoOff)

        # Changed behaviour before commit
        self.assertTrue(self.helper.changed())
        self.assertTrue(self.helper.changed('autoOff'))
        self.assertFalse(self.helper.changed('pixelSize'))

        self.helper.commit()

        # Underling valus is changed after commit
        self.assertFalse(self.hwConfig.autoOff)

        # Changed behaviour after commit
        self.assertFalse(self.helper.changed())
        self.assertFalse(self.helper.changed('autoOff'))
        self.assertFalse(self.helper.changed('pixelSize'))

    def test_changed(self):
        self.assertFalse(self.helper.changed(), "Fresh config is not changed")

        self.helper.autoOff = not self.helper.autoOff

        self.assertTrue(self.helper.changed(), "Modified config is changed")

        self.helper.autoOff = not self.helper.autoOff

        self.assertFalse(self.helper.changed(), "After modify revert the config is not changed")


if __name__ == '__main__':
    unittest.main()
