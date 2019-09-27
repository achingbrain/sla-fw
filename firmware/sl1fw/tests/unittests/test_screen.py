#!/usr/bin/env python3

import os
import unittest
import logging
import zipfile
import filecmp
import numpy
from pathlib import Path

from sl1fw.tests.base import Sl1fwTestCase

from sl1fw import defines
from sl1fw import libConfig


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
        defines.fbFile = str(self.FB_DEV)
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory" / "factory.toml")
        defines.livePreviewImage = str(self.PREVIEW_FILE)
        defines.displayUsageData = str(self.DISPLAY_USAGE)

        from sl1fw.libScreen import Screen
        self.screen = Screen()
        self.screen.start()
        self.params = {
                'filename' : TestScreen.NUMBERS,
                'toPrint' : self.toPrint(TestScreen.NUMBERS),
                'expTime' : 4.0,
                'calibrateRegions' : 0,
                'calibrateTime' : 1.0,
                'calibratePenetration' : int(0.5 / defines.screenPixelSize),
                'perPartes' : False,
                'whitePixelsThd' : 50,
                'overlayName' : None,
                }

    def toPrint(self, project):
        toPrint = []
        try:
            zf = zipfile.ZipFile(project, "r")
            namelist = zf.namelist()
            zf.close()
        except Exception as e:
            logging.exception("zip read exception:" + str(e))
            return
        for filename in namelist:
            fName, fExt = os.path.splitext(filename)
            if fExt.lower() == ".png" and fName.find("0") > -1:
                toPrint.append(filename)
        return toPrint

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
        self.assertTrue(filecmp.cmp(self.FB_DEV, Sl1fwTestCase.SAMPLES_DIR / "fbdev" / "all_black",
            shallow=False), "Init - display is not cleared at start")

    def test_getImg(self):
        self.screen.getImg(filename = TestScreen.ZABA)
        self.screen.ping()
        self.assertTrue(filecmp.cmp(self.FB_DEV, Sl1fwTestCase.SAMPLES_DIR / "fbdev" / "zaba",
            shallow=False), "getImg - wrong display content")

    def test_mask(self):
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Mask - retcode")
        self.assertFalse(perPartes, "Mask - perPartes")
        self.assertEqual(calibAreas, list(), "Mask - calibAreas")
        self.assertEqual(233600.0, self.screen.blitImg(), "Mask - wrong number of white pixels")
        self.assertTrue(filecmp.cmp(self.FB_DEV, Sl1fwTestCase.SAMPLES_DIR / "fbdev" / "mask",
            shallow=False), "Mask - wrong display content")

    def test_display_usage(self):
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Display usage - retcode")
        self.assertFalse(perPartes, "Display usage - perPartes")
        self.assertEqual(calibAreas, list(), "Display usage - calibAreas")
        self.screen.saveDisplayUsage()
        self.screen.ping()
        with numpy.load(TestScreen.DISPLAY_USAGE) as npzfile:
            savedData = npzfile['display_usage']
        with numpy.load(Sl1fwTestCase.SAMPLES_DIR / "display_usage.npz") as npzfile:
            exampleData = npzfile['display_usage']
        self.assertTrue(numpy.array_equal(savedData, exampleData), "Display usage - wrong display usage data")

    def test_perpartes(self):
        self.params['perPartes'] = True
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Perpartes - retcode")
        self.assertTrue(perPartes, "Perpartes - perPartes")
        self.assertEqual(calibAreas, list(), "Perpartes - calibAreas")
        self.screen.screenshot(second = False)
        self.screen.screenshotRename()
        self.assertEqual(233600.0, self.screen.blitImg(second = False), "Perpartes - wrong number of white pixels 1")
        self.assertTrue(filecmp.cmp(self.FB_DEV, Sl1fwTestCase.SAMPLES_DIR / "fbdev" / "part1",
            shallow=False), "Perpartes - wrong display content 1")
        self.assertTrue(filecmp.cmp(defines.livePreviewImage, Sl1fwTestCase.SAMPLES_DIR / "live1.png",
            shallow=False), "Perpartes - wrong preview image 1")
        self.screen.screenshot(second = True)
        self.screen.screenshotRename()
        self.assertEqual(233600.0, self.screen.blitImg(second = True), "Perpartes - wrong number of white pixels 2")
        self.assertTrue(filecmp.cmp(self.FB_DEV, Sl1fwTestCase.SAMPLES_DIR / "fbdev" / "part2",
            shallow=False), "Perpartes - wrong display content 2")
        self.assertTrue(filecmp.cmp(defines.livePreviewImage, Sl1fwTestCase.SAMPLES_DIR / "live2.png",
            shallow=False), "Perpartes - wrong preview image 2")

    def test_calibration_areas(self):
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Regions 0 - retcode")
        self.assertFalse(perPartes, "Regions 0 - perPartes")
        self.assertEqual(len(calibAreas), 0, "Regions 0 - calibAreas")

        self.params['calibrateRegions'] = 1
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Regions 1 - retcode")
        self.assertFalse(perPartes, "Regions 1 - perPartes")
        self.assertEqual(len(calibAreas), 0, "Regions 1 - calibAreas")

        self.params['calibrateRegions'] = 2
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Regions 2 - retcode")
        self.assertFalse(perPartes, "Regions 2 - perPartes")
        self.assertEqual(len(calibAreas), 2, "Regions 2 - calibAreas")

        self.params['calibrateRegions'] = 4
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Regions 4 - retcode")
        self.assertFalse(perPartes, "Regions 4 - perPartes")
        self.assertEqual(len(calibAreas), 4, "Regions 4 - calibAreas")

        self.params['calibrateRegions'] = 6
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Regions 6 - retcode")
        self.assertFalse(perPartes, "Regions 6 - perPartes")
        self.assertEqual(len(calibAreas), 6, "Regions 6 - calibAreas")

        self.params['calibrateRegions'] = 8
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Regions 8 - retcode")
        self.assertFalse(perPartes, "Regions 8 - perPartes")
        self.assertEqual(len(calibAreas), 8, "Regions 8 - calibAreas")

        self.params['calibrateRegions'] = 9
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "Regions 9 - retcode")
        self.assertFalse(perPartes, "Regions 9 - perPartes")
        self.assertEqual(len(calibAreas), 9, "Regions 9 - calibAreas")

    def test_calibration(self):
        self.params['filename'] = TestScreen.CALIBRATION
        self.params['toPrint'] = self.toPrint(TestScreen.CALIBRATION)
        self.params['calibrateRegions'] = 9
        self.params['overlayName'] = 'calibPad'
        self.screen.startProject(params = self.params)
        retcode, perPartes, calibAreas = self.screen.projectStatus()
        self.assertTrue(retcode, "calibPad - retcode")
        self.assertFalse(perPartes, "calibPad - perPartes")
        self.assertEqual(len(calibAreas), 9, "calibPad - calibAreas")
        self.assertEqual(1704721.0, self.screen.blitImg(second = False), "calibPad - wrong number of white pixels")
        self.assertTrue(filecmp.cmp(self.FB_DEV, Sl1fwTestCase.SAMPLES_DIR / "fbdev" / "calibPad",
            shallow=False), "calibPad - wrong display content")

# FIXME it doesn't work on docker image (different results)
#        self.params['overlayName'] = 'calib'
#        self.screen.startProject(params = self.params)
#        retcode, perPartes, calibAreas = self.screen.projectStatus()
#        self.assertTrue(retcode, "calib - retcode")
#        self.assertFalse(perPartes, "calib - perPartes")
#        self.assertEqual(len(calibAreas), 9, "calib - calibAreas")
#        self.assertEqual(1332082.25, self.screen.blitImg(second = False), "calib - wrong number of white pixels")
#        self.assertTrue(filecmp.cmp(self.FB_DEV, Sl1fwTestCase.SAMPLES_DIR / "fbdev" / "calib",
#            shallow=False), "calib - wrong display content")

if __name__ == '__main__':
    unittest.main()
