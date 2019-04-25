import unittest
import gettext
import os

try:
    gettext.install('sl1fw', unicode=1)
except:
    gettext.install('sl1fw')

from libConfig import *


class TestConfigHelper(unittest.TestCase):
    CONFIG_PATH = "config.cfg"

    def setUp(self):
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


if __name__ == '__main__':
    unittest.main()