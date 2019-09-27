import unittest
from pathlib import Path
from shutil import copyfile

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.libConfig import HwConfig, PrintConfig, Config, FloatValue, IntListValue, IntValue, BoolValue, \
    FloatListValue, TextValue, ConfigWriter, WizardData
from sl1fw import defines


class TestConfigValues(Sl1fwTestCase):
    def test_int(self):
        class IntConfig(Config):
            a = IntValue(4)
            b = IntValue(8, minimum=5, maximum=10)
            c = IntValue(-5, minimum=-10, maximum=1)
            ab = IntValue(lambda s: s.a * s.b)

        c = IntConfig()

        self.assertEqual(4, c.a)
        self.assertEqual(8, c.b)
        self.assertEqual(-5, c.c)
        self.assertEqual(c.a * c.b, c.ab)
        c.read_text("""
        a = 55
        b = 11
        c = -1
        """)
        self.assertEqual(55, c.a)
        self.assertEqual(10, c.b)
        self.assertEqual(-1, c.c)
        self.assertEqual(c.a * c.b, c.ab)
        c.a = 30
        c.b = 5
        c.c = -4
        self.assertEqual(30, c.a)
        self.assertEqual(5, c.b)
        self.assertEqual(-4, c.c)
        self.assertEqual(c.a * c.b, c.ab)

    def test_float(self):
        class FloatConfig(Config):
            a = FloatValue(4)
            b = FloatValue(8, minimum=5, maximum=10.1)
            c = FloatValue(-5, minimum=-10, maximum=1)
            ab = FloatValue(lambda s: s.a * s.b)

        c = FloatConfig()

        self.assertEqual(4, c.a)
        self.assertEqual(8, c.b)
        self.assertEqual(-5, c.c)
        self.assertEqual(c.a * c.b, c.ab)
        c.read_text("""
        a = 5.5
        b = 11
        c = -1
        """)
        self.assertEqual(5.5, c.a)
        self.assertEqual(10.1, c.b)
        self.assertEqual(-1, c.c)
        self.assertEqual(c.a * c.b, c.ab)
        c.a = 123.456
        c.b = 10.1
        c.c = -4.44
        self.assertEqual(123.456, c.a)
        self.assertEqual(10.1, c.b)
        self.assertEqual(-4.44, c.c)
        self.assertEqual(c.a * c.b, c.ab)

    def test_bool(self):
        class BoolConfig(Config):
            a = BoolValue(False)
            b = BoolValue(True)
            t0 = BoolValue(True)
            t1 = BoolValue(True)
            t2 = BoolValue(True)
            f0 = BoolValue(False)
            f1 = BoolValue(False)
            f2 = BoolValue(False)

        c = BoolConfig()
        self.assertFalse(c.a)
        self.assertTrue(c.b)
        c.read_text("""
        f0 = true
        f1 = yes
        f2 = on
        t0 = false
        t1 = no
        t2 = off
        """)
        self.assertTrue(c.f0)
        self.assertTrue(c.f1)
        self.assertTrue(c.f2)
        self.assertFalse(c.t0)
        self.assertFalse(c.t1)
        self.assertFalse(c.t2)

    def test_string(self):
        class StringConfig(Config):
            a = TextValue("def")
            b = TextValue()
            c = TextValue()

        c = StringConfig()
        self.assertEqual("def", c.a)
        self.assertEqual("", c.b)
        c.read_text("""
        a = old school text
        b = "toml compatible text"
        c = 123 numbers test 123""")
        self.assertEqual("old school text", c.a)
        self.assertEqual("toml compatible text", c.b)
        self.assertEqual("123 numbers test 123", c.c)

    def test_lists(self):
        class ListConfig(Config):
            i0 = IntListValue([1, 2, 3], length=3)
            i1 = IntListValue([1, 2, 3], length=3)
            f0 = FloatListValue([0.1, 0.2, 0.3], length=3)
            f1 = FloatListValue([0.1, 0.2, 0.3], length=3)

        c = ListConfig()
        self.assertEqual([1, 2, 3], c.i0)
        self.assertEqual([1, 2, 3], c.i1)
        self.assertEqual([0.1, 0.2, 0.3], c.f0)
        self.assertEqual([0.1, 0.2, 0.3], c.f1)

        c.read_text("""
        i0 = [ 1, 1, 1 ]
        i1 = 1 1 1
        f0 = [0.1, 0.1,0.1]
        f1 = 0.1    0.1 0.1
        """)
        self.assertEqual([1, 1, 1], c.i0)
        self.assertEqual([1, 1, 1], c.i1)
        self.assertEqual([0.1, 0.1, 0.1], c.f0)
        self.assertEqual([0.1, 0.1, 0.1], c.f1)


class TestHardwareConfig(Sl1fwTestCase):
    def __init__(self, *args, **kwargs):
        self.test_config_path = Path("hwconfig.test")
        self.writetest_config_path = Path("hwconfig.writetest")
        super().__init__(*args, **kwargs)

    def setUp(self):
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory" / "factory.toml")
        defines.hwConfigFile = str(self.SAMPLES_DIR / "hardware.cfg")
        copyfile(defines.hwConfigFile, "hwconfig.test")

    def tearDown(self):
        for path in [self.test_config_path, self.writetest_config_path]:
            if path.exists():
                path.unlink()

    def test_read(self):
        hw_config = HwConfig(Path(defines.hwConfigFile))
        print(hw_config)

        self.assertTrue(hw_config.coverCheck, "Test cover check read")
        self.assertTrue(hw_config.coverCheck, "Test cover check read")
        self.assertFalse(hw_config.calibrated, "Test calibrated read")
        self.assertEqual(hw_config.layerTowerHop, 0, "Test layerTowerHop read")

    @staticmethod
    def get_config_content(path: Path):
        with open(str(path), "r") as f:
            return f.read()

    def test_write(self):
        hw_config = HwConfig(self.test_config_path, is_master=True)
        hw_config.towerHeight = -1
        tower_height = 1024
        hw_config.towerHeight = tower_height

        self.assertEqual(hw_config.towerHeight, tower_height, "Check towerHeight is set")

        hw_config.uvPwm = 222

        print(hw_config)
        hw_config.write(self.writetest_config_path)
        self.assertEqual(
            # "MCBoardVersion = 6\r\n"
            # "showUnboxing = true\r\n"
            # "MCversionCheck = false\r\n"
            # "autoOff = true\r\n"
            "uvPwm = 222\n"
            "towerHeight = 1024\n",
            self.get_config_content(self.writetest_config_path),
            "Check file lines append")

        del hw_config.MCBoardVersion
        hw_config.write(self.test_config_path)
        print(self.get_config_content(self.writetest_config_path))
        self.assertEqual(
            # "showUnboxing = false\r\n"
            # "MCversionCheck = false\r\n"
            # "autoOff = true\r\n"
            "uvPwm = 222\n"
            "towerHeight = 1024\n",
            self.get_config_content(self.test_config_path),
            "Check file lines delete")

    def test_uvledpwm1(self):
        hw_config = HwConfig(self.SAMPLES_DIR / "hardware.cfg")
        hw_config.read_file()
        print(hw_config.uvPwm)
        self.assertEqual(219, hw_config.uvPwm, "UV LED PWM - No defaults at all")

    def test_uvledpwm2(self):
        hw_config = HwConfig(self.SAMPLES_DIR / "hardware-current.cfg")
        hw_config.read_file()
        self.assertEqual(152, hw_config.uvPwm, "UV LED PWM - current to PWM")

    def test_uvledpwm3(self):
        hw_config = HwConfig(self.SAMPLES_DIR / "hardware-pwm.cfg")
        hw_config.read_file()
        self.assertEqual(142, hw_config.uvPwm, "UV LED PWM - direct PWM")

    def test_uvledpwm4(self):
        hw_config = HwConfig(self.SAMPLES_DIR / "hardware.cfg",
                             factory_file_path=self.SAMPLES_DIR / "hardware-current.toml")
        hw_config.read_file()
        self.assertEqual(243, hw_config.uvPwm, "UV LED PWM - default current to PWM")

    def test_uvledpwm5(self):
        hw_config = HwConfig(self.SAMPLES_DIR / "hardware.cfg",
                             factory_file_path=self.SAMPLES_DIR / "hardware-pwm.toml")
        hw_config.read_file()
        self.assertEqual(123, hw_config.uvPwm, "UV LED PWM - default direct PWM")


class TestPrintConfig(Sl1fwTestCase):
    def setUp(self):
        self.hwConfig = HwConfig(self.SAMPLES_DIR / "samples" / "hardware.cfg",
                                 factory_file_path=defines.factoryConfigFile)

    def test_read(self):
        config = PrintConfig(self.hwConfig)
        print(config)

        self.assertEqual(config.projectName, "no project", "Check empty project name")

        config.parseFile(str(self.SAMPLES_DIR / "numbers.sl1"))

        self.assertIs(config.zipError, None, "Test for no read errors")

        print(config)


        self.assertEqual(config.projectName, "numbers", "Check projectName")
        self.assertEqual(config.totalLayers, 2, "Check total layers count")

        print(config.as_dictionary())
        config.expTime = 5.0

        self.assertEqual(config.expTime, 5, "Check expTime value")

        # config.write("printconfig.txt")


class TestWizardData(Sl1fwTestCase):
    def setUp(self):
        self.test_wizarddata = Path("wizardData.test")
        copyfile(self.SAMPLES_DIR / "wizardData.cfg", self.test_wizarddata)
        self.wizardData = WizardData(self.test_wizarddata, is_master=True)

    def tearDown(self):
        if self.test_wizarddata.exists():
            self.test_wizarddata.unlink()

    def test_lists(self):
        sensor_data = [98, 105, 108, 128, 136, 111, 145]
        perc_diff = [-23.4, -17.9, -15.6, 0.0, 6.3, -13.3, 13.3, -6.2, -10.9, -18.7]
        writer = ConfigWriter(self.wizardData)
        writer.uvSensorData = sensor_data
        writer.uvPercDiff = perc_diff
        writer.commit()

        self.assertEqual(self.wizardData.uvSensorData, sensor_data, "Check uvSensorData is set")
        self.assertEqual(self.wizardData.uvPercDiff, perc_diff, "Check uvSensorData is set")

        print(self.wizardData)

        self.wizardData.write(self.test_wizarddata)
        with self.test_wizarddata.open("r") as f:
            self.assertEqual(
                "uvSensorData = [ 98, 105, 108, 128, 136, 111, 145,]\n"
                "uvPercDiff = [ -23.4, -17.9, -15.6, 0.0, 6.3, -13.3, 13.3, -6.2, -10.9, -18.7,]\n",
                f.read(),
                "Check file lines")

        self.assertEqual(self.wizardData.uvSensorData, sensor_data, "Test sensor data read")
        self.assertEqual(self.wizardData.uvPercDiff, perc_diff, "Test perc diff read")


class TestConfigHelper(Sl1fwTestCase):
    CONFIG_PATH = Path("config.cfg")

    def setUp(self):
        self.hwConfig = HwConfig(self.CONFIG_PATH, is_master=True)
        self.helper = ConfigWriter(self.hwConfig)

    def tearDown(self):
        if self.CONFIG_PATH.exists():
            self.CONFIG_PATH.unlink()

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
        self.helper.tiltFastTime = 4.2

        self.assertAlmostEqual(self.helper.tiltFastTime, 4.2)
        self.assertIsInstance(self.helper.tiltFastTime, float)

    def test_commit(self):
        # Fresh helper is not changed
        self.assertFalse(self.helper.changed())
        self.assertFalse(self.helper.changed('autoOff'))
        self.assertFalse(self.helper.changed('tiltFastTime'))

        self.helper.autoOff = False

        # Underling valus is intact before commit
        self.assertTrue(self.hwConfig.autoOff)

        # Changed behaviour before commit
        self.assertTrue(self.helper.changed())
        self.assertTrue(self.helper.changed('autoOff'))
        self.assertFalse(self.helper.changed('tiltFastTime'))

        self.helper.commit()

        # Underling valus is changed after commit
        self.assertFalse(self.hwConfig.autoOff)

        # Changed behaviour after commit
        self.assertFalse(self.helper.changed())
        self.assertFalse(self.helper.changed('autoOff'))
        self.assertFalse(self.helper.changed('tiltFastTime'))

    def test_changed(self):
        self.assertFalse(self.helper.changed(), "Fresh config is not changed")

        self.helper.autoOff = not self.helper.autoOff

        self.assertTrue(self.helper.changed(), "Modified config is changed")

        self.helper.autoOff = not self.helper.autoOff

        self.assertFalse(self.helper.changed(), "After modify revert the config is not changed")


if __name__ == '__main__':
    unittest.main()
