#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.screen.resin_calibration import Area, AreaWithLabel, AreaWithLabelStripe, Calibration
from sl1fw.utils.bounding_box import BBox

from sl1fw.configs.hw import HwConfig
from sl1fw.screen.screen import Screen
from sl1fw.project.project import Project

class TestResinCalibration(Sl1fwTestCase):

    def setUp(self):
        super().setUp()
        self.width = 1440
        self.height = 2560
        self.size = (self.width, self.height)

    def test_calibration_areas_no_bbox(self):
        calib = Calibration(self.size)
        self.assertFalse(calib.create_areas(1, None))
        self.assertEqual(calib.areas, [])
        self.assertFalse(calib.is_cropped)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(2, None))
        self.assertFalse(calib.is_cropped)
        result = [
                AreaWithLabel((0, 0, self.width, self.height // 2)),
                AreaWithLabel((0, self.height // 2, self.width, self.height)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(4, None))
        self.assertFalse(calib.is_cropped)
        result = [
                AreaWithLabel((0, 0, self.width // 2, self.height // 2)),
                AreaWithLabel((0, self.height // 2, self.width // 2, self.height)),
                AreaWithLabel((self.width // 2, 0, self.width, self.height // 2)),
                AreaWithLabel((self.width // 2, self.height // 2, self.width, self.height)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(6, None))
        self.assertFalse(calib.is_cropped)
        result = [
                AreaWithLabel((0, 0, self.width // 2, self.height // 3)),
                AreaWithLabel((0, self.height // 3, self.width // 2, self.height // 3 * 2)),
                AreaWithLabel((0, self.height // 3 * 2, self.width // 2, self.height - 1)),
                AreaWithLabel((self.width // 2, 0, self.width, self.height // 3)),
                AreaWithLabel((self.width // 2, self.height // 3, self.width, self.height // 3 * 2)),
                AreaWithLabel((self.width // 2, self.height // 3 * 2, self.width, self.height - 1)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(8, None))
        self.assertFalse(calib.is_cropped)
        result = [
                AreaWithLabel((0, 0, self.width // 2, self.height // 4)),
                AreaWithLabel((0, self.height // 4, self.width // 2, self.height // 2)),
                AreaWithLabel((0, self.height // 2, self.width // 2, self.height // 4 * 3)),
                AreaWithLabel((0, self.height // 4 * 3, self.width // 2, self.height)),
                AreaWithLabel((self.width // 2, 0, self.width, self.height // 4)),
                AreaWithLabel((self.width // 2, self.height // 4, self.width, self.height // 2)),
                AreaWithLabel((self.width // 2, self.height // 2, self.width, self.height // 4 * 3)),
                AreaWithLabel((self.width // 2, self.height // 4 * 3, self.width, self.height)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(9, None))
        self.assertFalse(calib.is_cropped)
        result = [
                AreaWithLabel((0, 0, self.width // 3, self.height // 3)),
                AreaWithLabel((0, self.height // 3, self.width // 3, self.height // 3 * 2)),
                AreaWithLabel((0, self.height // 3 * 2, self.width // 3, self.height - 1)),
                AreaWithLabel((self.width // 3, 0, self.width // 3 * 2, self.height // 3)),
                AreaWithLabel((self.width // 3, self.height // 3, self.width // 3 * 2, self.height // 3 * 2)),
                AreaWithLabel((self.width // 3, self.height // 3 * 2, self.width // 3 * 2, self.height - 1)),
                AreaWithLabel((self.width // 3 * 2, 0, self.width, self.height // 3)),
                AreaWithLabel((self.width // 3 * 2, self.height // 3, self.width, self.height // 3 * 2)),
                AreaWithLabel((self.width // 3 * 2, self.height // 3 * 2, self.width, self.height - 1)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(10, None))
        self.assertFalse(calib.is_cropped)
        stripe = self.height // 10
        result = [
                AreaWithLabelStripe((0, 0, self.width, stripe)),
                AreaWithLabelStripe((0, 1 * stripe, self.width, 2 * stripe)),
                AreaWithLabelStripe((0, 2 * stripe, self.width, 3 * stripe)),
                AreaWithLabelStripe((0, 3 * stripe, self.width, 4 * stripe)),
                AreaWithLabelStripe((0, 4 * stripe, self.width, 5 * stripe)),
                AreaWithLabelStripe((0, 5 * stripe, self.width, 6 * stripe)),
                AreaWithLabelStripe((0, 6 * stripe, self.width, 7 * stripe)),
                AreaWithLabelStripe((0, 7 * stripe, self.width, 8 * stripe)),
                AreaWithLabelStripe((0, 8 * stripe, self.width, 9 * stripe)),
                AreaWithLabelStripe((0, 9 * stripe, self.width, 10 * stripe)),
                ]
        self.assertEqual(calib.areas, result)

    def test_calibration_areas_with_bbox(self):
        bbox = BBox((608, 1135, 832, 1455))
        w, h = bbox.size
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(2, bbox))
        self.assertFalse(calib.is_cropped)
        x = (self.width - w ) // 2
        y = (self.height - 2 * h) // 2
        result = [
                Area((x, y, x + w, y + h)),
                Area((x, y + h, x + w, y + 2 * h)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(4, bbox))
        self.assertFalse(calib.is_cropped)
        x = (self.width - 2 * w) // 2
        y = (self.height - 2 * h) // 2
        result = [
                Area((x, y, x + w, y + h)),
                Area((x, y + h, x + w, y + 2 * h)),
                Area((x + w, y, x + 2 * w, y + h)),
                Area((x + w, y + h, x + 2 * w, y + 2 *h)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(6, bbox))
        self.assertFalse(calib.is_cropped)
        x = (self.width - 2 * w) // 2
        y = (self.height - 3 * h) // 2
        result = [
                Area((x, y, x + w, y + h)),
                Area((x, y + h, x + w, y + 2 * h)),
                Area((x, y + 2 * h, x + w, y + 3 * h)),
                Area((x + w, y, x + 2 * w, y + h)),
                Area((x + w, y + h, x + 2 * w, y + 2 * h)),
                Area((x + w, y + 2 * h, x + 2 * w, y + 3 * h)),
                ]
        self.assertEqual(calib.areas, result)
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(8, bbox))
        self.assertFalse(calib.is_cropped)
        x = (self.width - 2 * w) // 2
        y = (self.height - 4 * h) // 2
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
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(9, bbox))
        self.assertFalse(calib.is_cropped)
        x = (self.width - 3 * w) // 2
        y = (self.height - 3 * h) // 2
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
        calib = Calibration(self.size)
        self.assertTrue(calib.create_areas(10, bbox))
        self.assertFalse(calib.is_cropped)
        h = 256
        x = (self.width - w) // 2
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

    def test_calibration_areas_crop(self):
        HW_CONFIG = Sl1fwTestCase.SAMPLES_DIR / "hardware.cfg"
        NUMBERS = Sl1fwTestCase.SAMPLES_DIR / "numbers.sl1"
        hw_config = HwConfig(HW_CONFIG)
        hw_config.read_file()
        screen = Screen(hw_config)
        project = Project(hw_config, screen.printer_model, NUMBERS)
        project.calibrate_regions = 9
        project.analyze()
        #  project bbox: (605, 735, 835, 1825)
        calib = Calibration(self.size)
        self.assertTrue(calib.new_project(
            project.bbox,
            project.layers[0].bbox,
            project.calibrate_regions,
            project.calibrate_compact,
            project.layers[-1].times_ms,
            project.calibrate_penetration_px,
            project.calibrate_text_size_px,
            project.calibrate_pad_spacing_px))
        self.assertTrue(calib.is_cropped)
        screen.exit()
