import unittest
import gettext
import os
import logging

try:
    gettext.install('sl1fw', unicode=1)
except:
    gettext.install('sl1fw')

from libConfig import *
import defines

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)


class TestHardwareConfig(unittest.TestCase):
    def setUp(self):
        defines.hwConfigFile = os.path.join(os.path.dirname(__file__), "samples/hardware.cfg")
        from shutil import copyfile
        copyfile(defines.hwConfigFile, "hwconfig.test")
        self.hwConfig = HwConfig(defines.hwConfigFile)

    def tearDown(self):
        os.remove("hwconfig.test")

    def test_read(self):
        self.hwConfig.logAllItems()
        self.hwConfig.logFile()

        self.assertTrue(self.hwConfig.coverCheck, "Test cover check read")
        self.assertFalse(self.hwConfig.calibrated, "Test calibrated read")
        self.assertEqual(self.hwConfig.layerTowerHop, 0, "Test layerTowerHop read")

    def test_write(self):
        towerHeight = "1024"
        self.hwConfig.update(towerheight = towerHeight)

        self.assertEqual(self.hwConfig.towerHeight, 1024, "Check towerHeight is set")

        self.hwConfig.logAllItems()
        self.hwConfig.logFile()
        logging.info(self.hwConfig.getSourceString())
        self.assertTrue(self.hwConfig.writeFile("hwconfig.test"), "Write config file")


class TestPrintConfig(unittest.TestCase):
    def setUp(self):
        defines.hwConfigFile = os.path.join(os.path.dirname(__file__), "samples/hardware.cfg")
        self.hwConfig = HwConfig(defines.hwConfigFile)

    def test_read(self):
        config = PrintConfig(self.hwConfig)
        config.logAllItems()
        config.logFile()

        self.assertEqual(config.projectName, "no project", "Check empty project name")

        config.parseFile(os.path.join(os.path.dirname(__file__), "samples/empty-sample.sl1"))

        self.assertIs(config.zipError, None, "Test for no read errors")

        config.logAllItems()
        config.logFile()

        self.assertEqual(config.projectName, "empty-sample", "Check projectName")
        self.assertEqual(config.totalLayers, 20, "Check total layers count")

        logging.info(config.getSourceString())
        config.update(expTime = "5")

        self.assertEqual(config.expTime, 5, "Check expTime value")

        #config.writeFile("printconfig.txt")


class TestNetConfig(unittest.TestCase):
    def test_read(self):
        netConfig = NetConfig()
        netConfig.parseText("""image = RSL-180-318
        firmware = Gen2-180-319""")
        netConfig.logAllItems()
        netConfig.logFile()

        self.assertEqual(netConfig.firmware, "Gen2-180-319", "Check firmware version")
        self.assertEqual(netConfig.image, "RSL-180-318", "Check image version")


class TestFWConfig(unittest.TestCase):
    def test_read(self):
        fwConfig = FwConfig(os.path.join(defines.usbUpdatePath + defines.swPath, "defines.py"))
        fwConfig.logAllItems()

        # TODO: What is this supposed to do?


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