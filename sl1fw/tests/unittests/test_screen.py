#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import numpy
from PIL import Image

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.configs.hw import HwConfig
from sl1fw.screen.screen import Screen
from sl1fw.project.project import Project
from sl1fw import defines, test_runtime


class TestScreen(Sl1fwTestCase):
    # pylint: disable=too-many-public-methods
    HW_CONFIG = Sl1fwTestCase.SAMPLES_DIR / "hardware.cfg"
    NUMBERS = Sl1fwTestCase.SAMPLES_DIR / "numbers.sl1"
    CALIBRATION = Sl1fwTestCase.SAMPLES_DIR / "Resin_calibration_object.sl1"
    CALIBRATION_LINEAR = Sl1fwTestCase.SAMPLES_DIR / "Resin_calibration_linear_object.sl1"
    ZABA = Sl1fwTestCase.SAMPLES_DIR / "zaba.png"
    PREVIEW_FILE = Sl1fwTestCase.TEMP_DIR / "live.png"
    DISPLAY_USAGE = Sl1fwTestCase.TEMP_DIR / "display_usage.npz"

    def setUp(self):
        super().setUp()
        defines.factoryConfigPath = str(self.SL1FW_DIR / ".." / "factory" / "factory.toml")
        defines.livePreviewImage = str(self.PREVIEW_FILE)
        defines.displayUsageData = str(self.DISPLAY_USAGE)
        test_runtime.testing = True
        self.hw_config = HwConfig(self.HW_CONFIG)
        self.hw_config.read_file()
        self.screen = Screen(self.hw_config)

    def tearDown(self):
        super().tearDown()
        files = [
            self.PREVIEW_FILE,
            self.DISPLAY_USAGE,
        ]
        for file in files:
            if file.exists():
                file.unlink()

    def test_init(self):
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "all_black.png"))

    def test_inverse(self):
        self.assertTrue(self.screen.is_screen_blank)
        self.screen.inverse()
        self.assertFalse(self.screen.is_screen_blank)

    def test_show_image(self):
        self.screen.show_image_with_path(TestScreen.ZABA)
        self.assertSameImage(self.screen.buffer, Image.open(self.ZABA))

    def test_mask(self):
        project = Project(self.hw_config, self.screen.printer_model, self.NUMBERS)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.assertFalse(project.per_partes)
        self.assertEqual(233600.0, self.screen.blit_image())
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "mask.png"))

    def test_display_usage(self):
        project = Project(self.hw_config, self.screen.printer_model, self.NUMBERS)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.assertFalse(project.per_partes)
        self.screen.save_display_usage()
        with numpy.load(TestScreen.DISPLAY_USAGE) as npzfile:
            savedData = npzfile['display_usage']
        with numpy.load(self.SAMPLES_DIR / "display_usage.npz") as npzfile:
            exampleData = npzfile['display_usage']
        self.assertTrue(numpy.array_equal(savedData, exampleData))

    def test_per_partes(self):
        project = Project(self.hw_config, self.screen.printer_model, self.NUMBERS)
        project.per_partes = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.assertTrue(project.per_partes)
        second = False
        self.screen.screenshot_rename(second)
        self.assertEqual(233600.0, self.screen.blit_image(second))
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "part1.png"))
        self.assertSameImage(Image.open(defines.livePreviewImage), Image.open(self.SAMPLES_DIR / "live1.png"))
        second = True
        self.screen.screenshot_rename(second)
        self.assertEqual(233600.0, self.screen.blit_image(second))
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "part2.png"))
        self.assertSameImage(Image.open(defines.livePreviewImage), Image.open(self.SAMPLES_DIR / "live2.png"))

    def test_calibration_calib_pad(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION)
        project.exposure_time_ms = 4000
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.assertEqual(1293509, self.screen.blit_image(False))
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_pad.png"))

    def test_calibration_calib(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION)
        project.exposure_time_ms = 4000
        self.screen.new_project(project)
        self.assertFalse(project.warnings)
        self.screen.preload_image(10)
        white = self.screen.blit_image(False)
        self.assertLess(abs(1166913 - white), 50)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib.png"), threshold=40)

    def test_calibration_fill(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.screen.blit_image(False)
        for idx in range(8):
            self.screen.fill_area(idx, idx * 32)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_fill.png"))

    def test_calibration_calib_pad_compact(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.assertEqual(1114168, self.screen.blit_image(False))
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_pad_compact.png"))

    def test_calibration_calib_compact(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.assertFalse(project.warnings)
        self.screen.preload_image(10)
        white = self.screen.blit_image(False)
        self.assertLess(abs(1126168 - white), 50)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_compact.png"), threshold=40)

    def test_calibration_fill_compact(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.screen.blit_image(False)
        for idx in range(8):
            self.screen.fill_area(idx, idx * 32)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_fill_compact.png"))

    def test_calibration_calib_pad_10(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION_LINEAR)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        white = self.screen.blit_image(False)
        self.assertLess(abs(3591170 - white), 50)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_pad_10.png"))

    def test_calibration_calib_10(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION_LINEAR)
        self.screen.new_project(project)
        self.assertFalse(project.warnings)
        self.screen.preload_image(10)
        white = self.screen.blit_image(False)
        self.assertLess(abs(1781967 - white), 50)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_10.png"), threshold=40)

    def test_calibration_fill_10(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION_LINEAR)
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.screen.blit_image(False)
        for idx in range(10):
            self.screen.fill_area(idx, idx * 32)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_fill_10.png"))

    def test_calibration_calib_pad_10_compact(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION_LINEAR)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        white = self.screen.blit_image(False)
        self.assertLess(abs(3361680 - white), 50)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_pad_10_compact.png"))

    def test_calibration_calib_10_compact(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION_LINEAR)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.assertFalse(project.warnings)
        self.screen.preload_image(10)
        white = self.screen.blit_image(False)
        self.assertLess(abs(1728640 - white), 50)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_10_compact.png"), threshold=40)

    def test_calibration_fill_10_compact(self):
        project = Project(self.hw_config, self.screen.printer_model, self.CALIBRATION_LINEAR)
        project.calibrate_compact = True
        self.screen.new_project(project)
        self.screen.preload_image(0)
        self.assertFalse(project.warnings)
        self.screen.blit_image(False)
        for idx in range(10):
            self.screen.fill_area(idx, idx * 32)
        self.assertSameImage(self.screen.buffer, Image.open(self.SAMPLES_DIR / "fbdev" / "calib_fill_10_compact.png"))

if __name__ == '__main__':
    unittest.main()
