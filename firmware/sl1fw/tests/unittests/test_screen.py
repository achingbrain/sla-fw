#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import filecmp
import numpy

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.libScreen import Screen
from sl1fw import defines


class TestScreen(Sl1fwTestCase):
    NUMBERS = Sl1fwTestCase.SAMPLES_DIR / "numbers.sl1"
    CALIBRATION = Sl1fwTestCase.SAMPLES_DIR / "calibration_test.sl1"
    ZABA = Sl1fwTestCase.SAMPLES_DIR / "zaba.png"
    FB_DEV = Sl1fwTestCase.TEMP_DIR / "test.fbdev"
    PREVIEW_FILE = Sl1fwTestCase.TEMP_DIR / "live.png"
    DISPLAY_USAGE = Sl1fwTestCase.TEMP_DIR / "display_usage.npz"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        super().setUp()
        defines.fbFile = str(self.FB_DEV)
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory" / "factory.toml")
        defines.livePreviewImage = str(self.PREVIEW_FILE)
        defines.displayUsageData = str(self.DISPLAY_USAGE)
        defines.testing = True
        defines.hwConfigFile = str(self.SAMPLES_DIR / "hardware.cfg")

        self.screen = Screen()
        self.screen.start()
        self.params = {
                'project' : self.NUMBERS,
                'expTime' : 7.5,
                'expTimeFirst' : 35,
                'calibrateTime' : 1.0,
                }

    def tearDown(self):
        self.screen.ping()
        self.screen.exit()
        files = [
            self.FB_DEV,
            self.PREVIEW_FILE,
            self.DISPLAY_USAGE,
        ]
        for file in files:
            if file.exists():
                file.unlink()

    def test_init(self):
        self.assertTrue(filecmp.cmp(self.FB_DEV, self.SAMPLES_DIR / "fbdev" / "all_black",
            shallow=False), "Init - display is not cleared at start")

    def test_getImg(self):
        self.screen.getImg(filename = TestScreen.ZABA)
        self.screen.ping()
        self.assertTrue(filecmp.cmp(self.FB_DEV, self.SAMPLES_DIR / "fbdev" / "zaba",
            shallow=False), "getImg - wrong display content")

    def test_mask(self):
        self.screen.startProject(params = self.params)
        retcode, perPartes = self.screen.projectStatus()
        self.assertTrue(retcode, "Mask - retcode")
        self.assertFalse(perPartes, "Mask - perPartes")
        self.assertEqual(233600.0, self.screen.blitImg(), "Mask - wrong number of white pixels")
        self.assertTrue(filecmp.cmp(self.FB_DEV, self.SAMPLES_DIR / "fbdev" / "mask",
            shallow=False), "Mask - wrong display content")

    def test_display_usage(self):
        self.screen.startProject(params = self.params)
        retcode, perPartes = self.screen.projectStatus()
        self.assertTrue(retcode, "Display usage - retcode")
        self.assertFalse(perPartes, "Display usage - perPartes")
        self.screen.saveDisplayUsage()
        self.screen.ping()
        with numpy.load(TestScreen.DISPLAY_USAGE) as npzfile:
            savedData = npzfile['display_usage']
        with numpy.load(self.SAMPLES_DIR / "display_usage.npz") as npzfile:
            exampleData = npzfile['display_usage']
        self.assertTrue(numpy.array_equal(savedData, exampleData), "Display usage - wrong display usage data")

    def test_perpartes(self):
        self.params['perPartes'] = True
        self.screen.startProject(params = self.params)
        retcode, perPartes = self.screen.projectStatus()
        self.assertTrue(retcode, "Perpartes - retcode")
        self.assertTrue(perPartes, "Perpartes - perPartes")
        self.screen.screenshot(second = False)
        self.screen.screenshotRename()
        self.assertEqual(233600.0, self.screen.blitImg(second = False), "Perpartes - wrong number of white pixels 1")
        self.assertTrue(filecmp.cmp(self.FB_DEV, self.SAMPLES_DIR / "fbdev" / "part1",
            shallow=False), "Perpartes - wrong display content 1")
        self.assertTrue(filecmp.cmp(defines.livePreviewImage, self.SAMPLES_DIR / "live1.png",
            shallow=False), "Perpartes - wrong preview image 1")
        self.screen.screenshot(second = True)
        self.screen.screenshotRename()
        self.assertEqual(233600.0, self.screen.blitImg(second = True), "Perpartes - wrong number of white pixels 2")
        self.assertTrue(filecmp.cmp(self.FB_DEV, self.SAMPLES_DIR / "fbdev" / "part2",
            shallow=False), "Perpartes - wrong display content 2")
        self.assertTrue(filecmp.cmp(defines.livePreviewImage, self.SAMPLES_DIR / "live2.png",
            shallow=False), "Perpartes - wrong preview image 2")

    def test_calibration(self):
        self.params['project'] = TestScreen.CALIBRATION
        self.params['expTime'] = 4.0
        self.screen.startProject(params = self.params)
        retcode, perPartes = self.screen.projectStatus()
        self.assertTrue(retcode, "calibPad - retcode")
        self.assertFalse(perPartes, "calibPad - perPartes")
        self.assertEqual(1704721.0, self.screen.blitImg(second = False), "calibPad - wrong number of white pixels")
        self.assertTrue(filecmp.cmp(self.FB_DEV, self.SAMPLES_DIR / "fbdev" / "calibPad",
            shallow=False), "calibPad - wrong display content")

# FIXME it doesn't work on docker image (different results)
#        self.params['overlayName'] = "calib"
#        self.screen.startProject(params = self.params)
#        retcode, perPartes = self.screen.projectStatus()
#        self.assertTrue(retcode, "calib - retcode")
#        self.assertFalse(perPartes, "calib - perPartes")
#        self.assertEqual(1332082.25, self.screen.blitImg(second = False), "calib - wrong number of white pixels")
#        self.assertTrue(filecmp.cmp(self.FB_DEV, self.SAMPLES_DIR / "fbdev" / "calib",
#            shallow=False), "calib - wrong display content")

if __name__ == '__main__':
    unittest.main()
