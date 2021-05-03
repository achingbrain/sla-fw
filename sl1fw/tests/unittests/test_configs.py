# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest import mock
from pathlib import Path
from shutil import copyfile

from sl1fw import defines
from sl1fw.configs.hw import HwConfig
from sl1fw.configs.ini import Config
from sl1fw.configs.writer import ConfigWriter
from sl1fw.configs.value import FloatValue, IntListValue, IntValue, BoolValue, FloatListValue, TextValue
from sl1fw.configs.project import ProjectConfig
from sl1fw.tests.base import Sl1fwTestCase


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
        c.read_text(
            """
        a = 55
        b = 11
        c = -1
        """
        )
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
        c.read_text(
            """
        a = 5.5
        b = 11
        c = -1
        """
        )
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
        c.read_text(
            """
        f0 = true
        f1 = yes
        f2 = on
        t0 = false
        t1 = no
        t2 = off
        """
        )
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
        c.read_text(
            """
        a = old school text
        b = "toml compatible text"
        c = 123 numbers test 123"""
        )
        self.assertEqual("old school text", c.a)
        self.assertEqual("toml compatible text", c.b)
        self.assertEqual("123 numbers test 123", c.c)

    def test_lists(self):
        class ListConfig(Config):
            i0 = IntListValue([1, 2, 3], length=3)
            i1 = IntListValue([1, 2, 3], length=3)
            f0 = FloatListValue([0.1, 0.2, 0.3], length=3)
            f1 = FloatListValue([0.1, 0.2, 0.3], length=3)
            i2 = IntListValue([0, 0, 0], length=3)

        c = ListConfig()
        self.assertEqual([1, 2, 3], c.i0)
        self.assertEqual([1, 2, 3], c.i1)
        self.assertEqual([0.1, 0.2, 0.3], c.f0)
        self.assertEqual([0.1, 0.2, 0.3], c.f1)

        c.read_text(
            """
        i0 = [ 1, 1, 1 ]
        i1 = 1 1 1
        f0 = [0.1, 0.1,0.1]
        f1 = 0.1    0.1 0.1
        i2 = [ 12840, 14115, 15640,]
        """
        )
        self.assertEqual([1, 1, 1], c.i0)
        self.assertEqual([1, 1, 1], c.i1)
        self.assertEqual([0.1, 0.1, 0.1], c.f0)
        self.assertEqual([0.1, 0.1, 0.1], c.f1)
        self.assertEqual([12840, 14115, 15640], c.i2)

    def test_dictionary(self):
        class SimpleConfig(Config):
            a = IntValue(5)

        s = SimpleConfig()
        self.assertIn("a", s.as_dictionary())
        self.assertEqual(5, s.as_dictionary()["a"])
        self.assertNotIn("a", s.as_dictionary(nondefault=False))
        s.read_text("a = 5")  # Setting value to default should not make it non-default
        self.assertNotIn("a", s.as_dictionary(nondefault=False))

    def test_value_reset(self):
        class SimpleConfig(Config):
            a = IntValue(5)

        s = SimpleConfig()
        self.assertEqual(5, s.a)
        s.a = 7
        self.assertEqual(7, s.a)
        s.factory_reset()
        self.assertEqual(5, s.a)

    def test_alternated(self):
        class SimpleConfig(Config):
            a = IntValue(5, minimum=4, maximum=6)

        # No alternated values
        s = SimpleConfig()
        s.read_text("a = 4")
        self.assertEqual(4, s.a)
        self.assertEqual({}, s.get_altered_values())

        # Alternated value a
        s.read_text("a = 10")
        self.assertEqual(6, s.a)
        self.assertEqual({"a": (6, 10)}, s.get_altered_values())


class TestHardwareConfig(Sl1fwTestCase):
    def __init__(self, *args, **kwargs):
        self.test_config_path = Path("hwconfig.test")
        self.writetest_config_path = Path("hwconfig.writetest")
        super().__init__(*args, **kwargs)

    def setUp(self):
        super().setUp()
        defines.factoryConfigPath = self.SL1FW_DIR / ".." / "factory" / "factory.toml"
        defines.hwConfigPathFactory = self.SAMPLES_DIR / "hardware.toml"
        defines.hwConfigPath = self.SAMPLES_DIR / "hardware-toml.cfg"
        copyfile(defines.hwConfigPath, "hwconfig.test")

    def tearDown(self):
        for path in [self.test_config_path, self.writetest_config_path]:
            if path.exists():
                path.unlink()
        super().tearDown()

    def test_read(self):
        hw_config = HwConfig(Path(defines.hwConfigPath))
        hw_config.read_file()

        self.assertFalse(hw_config.showUnboxing, "Test show unboxing read")
        self.assertTrue(hw_config.coverCheck, "Test cover check read")
        self.assertTrue(hw_config.coverCheck, "Test cover check read")
        self.assertFalse(hw_config.calibrated, "Test calibrated read")
        self.assertEqual(hw_config.layerTowerHop, 0, "Test layerTowerHop read")

    @staticmethod
    def get_config_content(path: Path):
        with open(str(path), "r") as f:
            return f.read()

    def test_instances(self):
        """
        Ensure different instances do not share the data
        """
        a = HwConfig()
        a.showUnboxing = False
        HwConfig()
        self.assertFalse(a.showUnboxing)

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
            "uvPwm = 222\n" "towerHeight = 1024\n",
            self.get_config_content(self.writetest_config_path),
            "Check file lines append",
        )

        del hw_config.MCBoardVersion
        hw_config.write(self.test_config_path)
        print(self.get_config_content(self.writetest_config_path))
        self.assertEqual(
            # "showUnboxing = false\r\n"
            # "MCversionCheck = false\r\n"
            # "autoOff = true\r\n"
            "uvPwm = 222\n" "towerHeight = 1024\n",
            self.get_config_content(self.test_config_path),
            "Check file lines delete",
        )

    def test_uvledpwm1(self):
        hw_config = HwConfig(self.SAMPLES_DIR / "hardware.cfg")
        hw_config.read_file()
        print(hw_config.uvPwm)
        self.assertEqual(0, hw_config.uvPwm, "UV LED PWM - No defaults at all")

    def test_uvledpwm2(self):
        hw_config = HwConfig(self.SAMPLES_DIR / "hardware-current.cfg")
        hw_config.read_file()
        self.assertEqual(152, hw_config.uvPwm, "UV LED PWM - current to PWM")

    def test_uvledpwm3(self):
        hw_config = HwConfig(self.SAMPLES_DIR / "hardware-pwm.cfg")
        hw_config.read_file()
        self.assertEqual(142, hw_config.uvPwm, "UV LED PWM - direct PWM")

    def test_uvledpwm4(self):
        hw_config = HwConfig(
            self.SAMPLES_DIR / "hardware.cfg", factory_file_path=self.SAMPLES_DIR / "hardware-current.toml"
        )
        hw_config.read_file()
        self.assertEqual(243, hw_config.uvPwm, "UV LED PWM - default current to PWM")

    def test_uvledpwm5(self):
        hw_config = HwConfig(
            self.SAMPLES_DIR / "hardware.cfg", factory_file_path=self.SAMPLES_DIR / "hardware-pwm.toml"
        )
        hw_config.read_file()
        self.assertEqual(123, hw_config.uvPwm, "UV LED PWM - default direct PWM")


class TestConfigHelper(Sl1fwTestCase):
    CONFIG_PATH = Path("config.cfg")

    def setUp(self):
        super().setUp()
        self.hw_config = HwConfig(self.CONFIG_PATH, is_master=True)
        self.helper = ConfigWriter(self.hw_config)

    def tearDown(self):
        if self.CONFIG_PATH.exists():
            self.CONFIG_PATH.unlink()
        super().tearDown()

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
        self.assertFalse(self.helper.changed("autoOff"))
        self.assertFalse(self.helper.changed("tiltFastTime"))

        self.helper.autoOff = False

        # Underling valus is intact before commit
        self.assertTrue(self.hw_config.autoOff)

        # Changed behaviour before commit
        self.assertTrue(self.helper.changed())
        self.assertTrue(self.helper.changed("autoOff"))
        self.assertFalse(self.helper.changed("tiltFastTime"))

        self.helper.commit()

        # Underling value is changed after commit
        self.assertFalse(self.hw_config.autoOff)

        # Changed behaviour after commit
        self.assertFalse(self.helper.changed())
        self.assertFalse(self.helper.changed("autoOff"))
        self.assertFalse(self.helper.changed("tiltFastTime"))

    def test_changed(self):
        self.assertFalse(self.helper.changed(), "Fresh config is not changed")
        self.helper.autoOff = not self.helper.autoOff
        self.assertTrue(self.helper.changed(), "Modified config is changed")
        self.helper.autoOff = not self.helper.autoOff
        self.assertFalse(self.helper.changed(), "After modify revert the config is not changed")

    def test_on_change(self):
        on_change = mock.MagicMock()
        on_change.__self__ = mock.Mock(name='self')
        on_change.__func__ = mock.Mock(name='func')
        on_change("calibrated", True)
        self.hw_config.add_onchange_handler(on_change)
        self.helper.calibrated = True
        self.helper.commit()
        on_change.assert_called_with("calibrated", True)


class TestPrintConfig(Sl1fwTestCase):
    CONFIG_PATH = Path("config.cfg")

    def setUp(self):
        super().setUp()
        self.print_config = ProjectConfig()
        self.print_config.read_file(self.SAMPLES_DIR / "num_name_print_config.ini")

    def test_num_fade(self):
        self.assertEqual(10, self.print_config.fadeLayers)

    def test_material(self):
        self.assertEqual(19.292032, self.print_config.usedMaterial)

    def test_name(self):
        self.assertEqual("123456789", self.print_config.job_dir)


if __name__ == "__main__":
    unittest.main()
