#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import numpy
from PIL import Image

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.libConfig import HwConfig
from sl1fw.screen.screen import Screen
from sl1fw.screen.resin_calibration import Area, AreaWithLabel, AreaWithLabelStripe, Calibration
from sl1fw.project.project import Project
from sl1fw.states.project import ProjectErrors
from sl1fw.utils.bounding_box import BBox
from sl1fw import defines, test_runtime


class TestScreen(Sl1fwTestCase):
    # pylint: disable=too-many-public-methods
    HW_CONFIG = Sl1fwTestCase.SAMPLES_DIR / "hardware.cfg"
    NUMBERS = Sl1fwTestCase.SAMPLES_DIR / "numbers.sl1"
    CALIBRATION = Sl1fwTestCase.SAMPLES_DIR / "Resin_calibration_object.sl1"
    CALIBRATION_LINEAR = Sl1fwTestCase.SAMPLES_DIR / "Resin_calibration_linear_object.sl1"
    ZABA = Sl1fwTestCase.SAMPLES_DIR / "zaba.png"
    FB_DEV = Sl1fwTestCase.TEMP_DIR / "test.fbdev"
    PREVIEW_FILE = Sl1fwTestCase.TEMP_DIR / "live.png"
    DISPLAY_USAGE = Sl1fwTestCase.TEMP_DIR / "display_usage.npz"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        super().setUp()
        defines.fbFile = str(self.FB_DEV)
        defines.factoryConfigPath = str(self.SL1FW_DIR / ".." / "factory" / "factory.toml")
        defines.livePreviewImage = str(self.PREVIEW_FILE)
        defines.displayUsageData = str(self.DISPLAY_USAGE)
        test_runtime.testing = True

        with open(self.FB_DEV, 'wb') as fb:
            fb.truncate(4 * defines.screenWidth * defines.screenHeight)

        self.screen = Screen()

    def tearDown(self):
        files = [
            self.FB_DEV,
            self.PREVIEW_FILE,
            self.DISPLAY_USAGE,
        ]
        for file in files:
            if file.exists():
                file.unlink()

    def load_project(self, filename):
        hw_config = HwConfig(self.HW_CONFIG)
        hw_config.read_file()
        return Project(hw_config, filename)

    def test_init(self):
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "all_black.png"))

    def test_inverse(self):
        self.assertTrue(self.screen.is_screen_blank)
        self.screen.inverse()
        self.assertFalse(self.screen.is_screen_blank)

    def test_show_image(self):
        self.screen.show_image(filename = TestScreen.ZABA)
        self.assertSameImage(self._fb, Image.open(self.ZABA))

    def test_mask(self):
        project = self.load_project(self.NUMBERS)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.assertFalse(project.per_partes)
        self.assertEqual(233600.0, self.screen.blit_image())
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "mask.png"))

    def test_display_usage(self):
        project = self.load_project(self.NUMBERS)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.assertFalse(project.per_partes)
        self.screen.save_display_usage()
        with numpy.load(TestScreen.DISPLAY_USAGE) as npzfile:
            savedData = npzfile['display_usage']
        with numpy.load(self.SAMPLES_DIR / "display_usage.npz") as npzfile:
            exampleData = npzfile['display_usage']
        self.assertTrue(numpy.array_equal(savedData, exampleData))

    def test_per_partes(self):
        project = self.load_project(self.NUMBERS)
        project.per_partes = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.assertTrue(project.per_partes)
        second = False
        self.screen.screenshot_rename(second)
        self.assertEqual(233600.0, self.screen.blit_image(second))
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "part1.png"))
        self.assertSameImage(Image.open(defines.livePreviewImage), Image.open(self.SAMPLES_DIR / "live1.png"))
        second = True
        self.screen.screenshot_rename(second)
        self.assertEqual(233600.0, self.screen.blit_image(second))
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "part2.png"))
        self.assertSameImage(Image.open(defines.livePreviewImage), Image.open(self.SAMPLES_DIR / "live2.png"))

    @property
    def _fb(self) -> Image:
        with self.FB_DEV.open("rb") as f:
            return Image.frombytes("RGBX", (defines.screenWidth, defines.screenHeight), f.read())

    def test_calibration_areas_no_bbox(self):
        calib = Calibration()
        self.assertFalse(calib.create_areas(1, None))
        self.assertEqual(calib.areas, [])
        calib = Calibration()
        self.assertTrue(calib.create_areas(2, None))
        result = [
                AreaWithLabel((0, 0, defines.screenWidth, defines.screenHeight // 2)),
                AreaWithLabel((0, defines.screenHeight // 2, defines.screenWidth, defines.screenHeight)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(4, None))
        result = [
                AreaWithLabel((0, 0, defines.screenWidth // 2, defines.screenHeight // 2)),
                AreaWithLabel((0, defines.screenHeight // 2, defines.screenWidth // 2, defines.screenHeight)),
                AreaWithLabel((defines.screenWidth // 2, 0, defines.screenWidth, defines.screenHeight // 2)),
                AreaWithLabel((defines.screenWidth // 2, defines.screenHeight // 2, defines.screenWidth, defines.screenHeight)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(6, None))
        result = [
                AreaWithLabel((0, 0, defines.screenWidth // 2, defines.screenHeight // 3)),
                AreaWithLabel((0, defines.screenHeight // 3, defines.screenWidth // 2, defines.screenHeight // 3 * 2)),
                AreaWithLabel((0, defines.screenHeight // 3 * 2, defines.screenWidth // 2, defines.screenHeight - 1)),
                AreaWithLabel((defines.screenWidth // 2, 0, defines.screenWidth, defines.screenHeight // 3)),
                AreaWithLabel((defines.screenWidth // 2, defines.screenHeight // 3, defines.screenWidth, defines.screenHeight // 3 * 2)),
                AreaWithLabel((defines.screenWidth // 2, defines.screenHeight // 3 * 2, defines.screenWidth, defines.screenHeight - 1)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(8, None))
        result = [
                AreaWithLabel((0, 0, defines.screenWidth // 2, defines.screenHeight // 4)),
                AreaWithLabel((0, defines.screenHeight // 4, defines.screenWidth // 2, defines.screenHeight // 2)),
                AreaWithLabel((0, defines.screenHeight // 2, defines.screenWidth // 2, defines.screenHeight // 4 * 3)),
                AreaWithLabel((0, defines.screenHeight // 4 * 3, defines.screenWidth // 2, defines.screenHeight)),
                AreaWithLabel((defines.screenWidth // 2, 0, defines.screenWidth, defines.screenHeight // 4)),
                AreaWithLabel((defines.screenWidth // 2, defines.screenHeight // 4, defines.screenWidth, defines.screenHeight // 2)),
                AreaWithLabel((defines.screenWidth // 2, defines.screenHeight // 2, defines.screenWidth, defines.screenHeight // 4 * 3)),
                AreaWithLabel((defines.screenWidth // 2, defines.screenHeight // 4 * 3, defines.screenWidth, defines.screenHeight)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(9, None))
        result = [
                AreaWithLabel((0, 0, defines.screenWidth // 3, defines.screenHeight // 3)),
                AreaWithLabel((0, defines.screenHeight // 3, defines.screenWidth // 3, defines.screenHeight // 3 * 2)),
                AreaWithLabel((0, defines.screenHeight // 3 * 2, defines.screenWidth // 3, defines.screenHeight - 1)),
                AreaWithLabel((defines.screenWidth // 3, 0, defines.screenWidth // 3 * 2, defines.screenHeight // 3)),
                AreaWithLabel((defines.screenWidth // 3, defines.screenHeight // 3, defines.screenWidth // 3 * 2, defines.screenHeight // 3 * 2)),
                AreaWithLabel((defines.screenWidth // 3, defines.screenHeight // 3 * 2, defines.screenWidth // 3 * 2, defines.screenHeight - 1)),
                AreaWithLabel((defines.screenWidth // 3 * 2, 0, defines.screenWidth, defines.screenHeight // 3)),
                AreaWithLabel((defines.screenWidth // 3 * 2, defines.screenHeight // 3, defines.screenWidth, defines.screenHeight // 3 * 2)),
                AreaWithLabel((defines.screenWidth // 3 * 2, defines.screenHeight // 3 * 2, defines.screenWidth, defines.screenHeight - 1)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(10, None))
        stripe = defines.screenHeight // 10
        result = [
                AreaWithLabelStripe((0, 0, defines.screenWidth, stripe)),
                AreaWithLabelStripe((0, 1 * stripe, defines.screenWidth, 2 * stripe)),
                AreaWithLabelStripe((0, 2 * stripe, defines.screenWidth, 3 * stripe)),
                AreaWithLabelStripe((0, 3 * stripe, defines.screenWidth, 4 * stripe)),
                AreaWithLabelStripe((0, 4 * stripe, defines.screenWidth, 5 * stripe)),
                AreaWithLabelStripe((0, 5 * stripe, defines.screenWidth, 6 * stripe)),
                AreaWithLabelStripe((0, 6 * stripe, defines.screenWidth, 7 * stripe)),
                AreaWithLabelStripe((0, 7 * stripe, defines.screenWidth, 8 * stripe)),
                AreaWithLabelStripe((0, 8 * stripe, defines.screenWidth, 9 * stripe)),
                AreaWithLabelStripe((0, 9 * stripe, defines.screenWidth, 10 * stripe)),
                ]
        self.assertEqual(calib.areas, result)

    def test_calibration_areas_with_bbox(self):
        bbox = BBox((608, 1135, 832, 1455))
        w, h = bbox.size
        calib = Calibration()
        self.assertTrue(calib.create_areas(2, bbox))
        x = (defines.screenWidth - w ) // 2
        y = (defines.screenHeight - 2 * h) // 2
        result = [
                Area((x, y, x + w, y + h)),
                Area((x, y + h, x + w, y + 2 * h)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(4, bbox))
        x = (defines.screenWidth - 2 * w) // 2
        y = (defines.screenHeight - 2 * h) // 2
        result = [
                Area((x, y, x + w, y + h)),
                Area((x, y + h, x + w, y + 2 * h)),
                Area((x + w, y, x + 2 * w, y + h)),
                Area((x + w, y + h, x + 2 * w, y + 2 *h)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(6, bbox))
        x = (defines.screenWidth - 2 * w) // 2
        y = (defines.screenHeight - 3 * h) // 2
        result = [
                Area((x, y, x + w, y + h)),
                Area((x, y + h, x + w, y + 2 * h)),
                Area((x, y + 2 * h, x + w, y + 3 * h)),
                Area((x + w, y, x + 2 * w, y + h)),
                Area((x + w, y + h, x + 2 * w, y + 2 * h)),
                Area((x + w, y + 2 * h, x + 2 * w, y + 3 * h)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(8, bbox))
        x = (defines.screenWidth - 2 * w) // 2
        y = (defines.screenHeight - 4 * h) // 2
        result = [
                Area((x, y, x + w, y + h)),
                Area((x, y + h, x + w, y + 2 * h)),
                Area((x, y + 2 * h, x + w, y + 3 * h)),
                Area((x, y + 3 * h, x + w, y + 4 * h)),
                Area((x + w, y, x + 2 * w, y + h)),
                Area((x + w, y + h, x + 2 * w, y + 2 * h)),
                Area((x + w, y + 2 * h, x + 2 * w, y + 3 * h)),
                Area((x + w, y + 3 * h, x + 2 * w, y + 4 * h)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(9, bbox))
        x = (defines.screenWidth - 3 * w) // 2
        y = (defines.screenHeight - 3 * h) // 2
        result = [
                Area((x, y, x + w, y + h)),
                Area((x, y + h, x + w, y + 2 * h)),
                Area((x, y + 2 * h, x + w, y + 3 * h)),
                Area((x + w, y, x + 2 * w, y + h)),
                Area((x + w, y + h, x + 2 * w, y + 2 * h)),
                Area((x + w, y + 2 * h, x + 2 * w, y + 3 * h)),
                Area((x + 2 * w, y, x + 3 * w, y + h)),
                Area((x + 2 * w, y + h, x + 3 * w, y + 2 * h)),
                Area((x + 2 * w, y + 2 * h, x + 3 * w, y + 3 * h)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration()
        self.assertTrue(calib.create_areas(10, bbox))
        h = 256
        x = (defines.screenWidth - w) // 2
        result = [
                Area((x, 0, x + w, h)),
                Area((x, 1 * h, x + w, 2 * h)),
                Area((x, 2 * h, x + w, 3 * h)),
                Area((x, 3 * h, x + w, 4 * h)),
                Area((x, 4 * h, x + w, 5 * h)),
                Area((x, 5 * h, x + w, 6 * h)),
                Area((x, 6 * h, x + w, 7 * h)),
                Area((x, 7 * h, x + w, 8 * h)),
                Area((x, 8 * h, x + w, 9 * h)),
                Area((x, 9 * h, x + w, 10 * h)),
                ]
        self.assertEqual(calib.areas, result)

    def test_calibration_calib_pad(self):
        project = self.load_project(self.CALIBRATION)
        project.exposure_time_ms = 4000
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.assertEqual(1293509, self.screen.blit_image(False))
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_pad.png"))

    def test_calibration_calib(self):
        project = self.load_project(self.CALIBRATION)
        project.exposure_time_ms = 4000
        self.screen.new_project(project)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.screen.preload_image(10)
        white = self.screen.blit_image(False)
        self.assertLess(abs(1166913 - white), 50)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib.png"), threshold=40)

    def test_calibration_fill(self):
        project = self.load_project(self.CALIBRATION)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.screen.blit_image(False)
        for idx in range(8):
            self.screen.fill_area(idx, idx * 32)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_fill.png"))

    def test_calibration_calib_pad_compact(self):
        project = self.load_project(self.CALIBRATION)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.assertEqual(1114168, self.screen.blit_image(False))
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_pad_compact.png"))

    def test_calibration_calib_compact(self):
        project = self.load_project(self.CALIBRATION)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.screen.preload_image(10)
        white = self.screen.blit_image(False)
        self.assertLess(abs(1126168 - white), 50)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_compact.png"), threshold=40)

    def test_calibration_fill_compact(self):
        project = self.load_project(self.CALIBRATION)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.screen.blit_image(False)
        for idx in range(8):
            self.screen.fill_area(idx, idx * 32)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_fill_compact.png"))

    def test_calibration_calib_pad_10(self):
        project = self.load_project(self.CALIBRATION_LINEAR)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        white = self.screen.blit_image(False)
        self.assertLess(abs(3591170 - white), 50)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_pad_10.png"))

    def test_calibration_calib_10(self):
        project = self.load_project(self.CALIBRATION_LINEAR)
        self.screen.new_project(project)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.screen.preload_image(10)
        white = self.screen.blit_image(False)
        self.assertLess(abs(1781967 - white), 50)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_10.png"), threshold=40)

    def test_calibration_fill_10(self):
        project = self.load_project(self.CALIBRATION_LINEAR)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.screen.blit_image(False)
        for idx in range(10):
            self.screen.fill_area(idx, idx * 32)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_fill_10.png"))

    def test_calibration_calib_pad_10_compact(self):
        project = self.load_project(self.CALIBRATION_LINEAR)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        white = self.screen.blit_image(False)
        self.assertLess(abs(3361680 - white), 50)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_pad_10_compact.png"))

    def test_calibration_calib_10_compact(self):
        project = self.load_project(self.CALIBRATION_LINEAR)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.screen.preload_image(10)
        white = self.screen.blit_image(False)
        self.assertLess(abs(1728640 - white), 50)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_10_compact.png"), threshold=40)

    def test_calibration_fill_10_compact(self):
        project = self.load_project(self.CALIBRATION_LINEAR)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertEqual(project.error, ProjectErrors.NONE)
        self.assertFalse(project.warnings)
        self.screen.blit_image(False)
        for idx in range(10):
            self.screen.fill_area(idx, idx * 32)
        self.assertSameImage(self._fb, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_fill_10_compact.png"))

if __name__ == '__main__':
    unittest.main()
