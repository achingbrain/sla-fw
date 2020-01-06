# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from sl1fw import defines
from sl1fw.libConfig import HwConfig
from sl1fw.project.project import Project, ProjectState
from sl1fw.tests.base import Sl1fwTestCase


class TestProject(Sl1fwTestCase):
    def setUp(self):
        self.assertEqual.__self__.maxDiff = None
        self.hwConfig = HwConfig(self.SAMPLES_DIR / "hardware.cfg")

    def test_read(self):
        project = Project(self.hwConfig)
        self.assertEqual(ProjectState.NOT_FOUND, project.read("bad_file"), "Bad file test")

        self.assertEqual(ProjectState.OK, project.read(str(self.SAMPLES_DIR / "numbers.sl1")), "No read errors test")
        print(project)

        self.assertEqual(project.name, "numbers", "Check project name")
        self.assertEqual(project.totalLayers, 2, "Check total layers count")
        self.assertAlmostEqual(project.modificationTime, 1569863651.0, msg="Check modification time")

        print(project.config.as_dictionary())
        project.expTime = 5.0
        self.assertAlmostEqual(project.expTime, 5.0, msg="Check expTime value")
        self.assertEqual(project.calibrateAreas, [], "calibrateAreas")

        # project.config.write("projectconfig.txt")

    def test_calibration_areas(self):
        project = Project(self.hwConfig)
        self.assertEqual(ProjectState.OK, project.read(str(self.SAMPLES_DIR / "numbers.sl1")), "No read errors test")

        project.config.calibrateRegions = 1
        project.expTime = 1.0
        result = []
        self.assertEqual(project.calibrateAreas, result, "calibrateAreas = 1")

        project.config.calibrateRegions = 2
        project.expTime = 2.0
        result = [
                {'stripe': False, 'time': 2.0, 'rect': {'x': 0, 'y': 0, 'w': defines.screenWidth, 'h': defines.screenHeight // 2}},
                {'stripe': False, 'time': 3.0, 'rect': {'x': 0, 'y': defines.screenHeight // 2, 'w': defines.screenWidth, 'h': defines.screenHeight // 2}},
                ]
        self.assertEqual(project.calibrateAreas, result, "calibrateAreas = 2")

        project.config.calibrateRegions = 4
        project.expTime = 4.0
        result = [
                {'stripe': False, 'time': 4.0, 'rect': {'x': 0, 'y': 0, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 2}},
                {'stripe': False, 'time': 5.0, 'rect': {'x': 0, 'y': defines.screenHeight // 2, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 2}},
                {'stripe': False, 'time': 6.0, 'rect': {'x': defines.screenWidth // 2, 'y': 0, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 2}},
                {'stripe': False, 'time': 7.0, 'rect': {'x': defines.screenWidth // 2, 'y': defines.screenHeight // 2, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 2}},
                ]
        self.assertEqual(project.calibrateAreas, result, "calibrateAreas = 4")

        project.config.calibrateRegions = 6
        project.expTime = 6.0
        result = [
                {'stripe': False, 'time': 6.0, 'rect': {'x': 0, 'y': 0, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 7.0, 'rect': {'x': 0, 'y': defines.screenHeight // 3, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 8.0, 'rect': {'x': 0, 'y': defines.screenHeight // 3 * 2, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 9.0, 'rect': {'x': defines.screenWidth // 2, 'y': 0, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 10.0, 'rect': {'x': defines.screenWidth // 2, 'y': defines.screenHeight // 3, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 11.0, 'rect': {'x': defines.screenWidth // 2, 'y': defines.screenHeight // 3 * 2, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 3}},
                ]
        self.assertEqual(project.calibrateAreas, result, "calibrateAreas = 6")

        project.config.calibrateRegions = 8
        project.expTime = 8.0
        result = [
                {'stripe': False, 'time': 8.0, 'rect': {'x': 0, 'y': 0, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 4}},
                {'stripe': False, 'time': 9.0, 'rect': {'x': 0, 'y': defines.screenHeight // 4, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 4}},
                {'stripe': False, 'time': 10.0, 'rect': {'x': 0, 'y': defines.screenHeight // 2, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 4}},
                {'stripe': False, 'time': 11.0, 'rect': {'x': 0, 'y': defines.screenHeight // 4 * 3, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 4}},
                {'stripe': False, 'time': 12.0, 'rect': {'x': defines.screenWidth // 2, 'y': 0, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 4}},
                {'stripe': False, 'time': 13.0, 'rect': {'x': defines.screenWidth // 2, 'y': defines.screenHeight // 4, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 4}},
                {'stripe': False, 'time': 14.0, 'rect': {'x': defines.screenWidth // 2, 'y': defines.screenHeight // 2, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 4}},
                {'stripe': False, 'time': 15.0, 'rect': {'x': defines.screenWidth // 2, 'y': defines.screenHeight // 4 * 3, 'w': defines.screenWidth // 2, 'h': defines.screenHeight // 4}},
                ]
        self.assertEqual(project.calibrateAreas, result, "calibrateAreas = 8")

        project.config.calibrateRegions = 9
        project.expTime = 9.0
        result = [
                {'stripe': False, 'time': 9.0, 'rect': {'x': 0, 'y': 0, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 10.0, 'rect': {'x': 0, 'y': defines.screenHeight // 3, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 11.0, 'rect': {'x': 0, 'y': defines.screenHeight // 3 * 2, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 12.0, 'rect': {'x': defines.screenWidth // 3, 'y': 0, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 13.0, 'rect': {'x': defines.screenWidth // 3, 'y': defines.screenHeight // 3, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 14.0, 'rect': {'x': defines.screenWidth // 3, 'y': defines.screenHeight // 3 * 2, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 15.0, 'rect': {'x': defines.screenWidth // 3 * 2, 'y': 0, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 16.0, 'rect': {'x': defines.screenWidth // 3 * 2, 'y': defines.screenHeight // 3, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                {'stripe': False, 'time': 17.0, 'rect': {'x': defines.screenWidth // 3 * 2, 'y': defines.screenHeight // 3 * 2, 'w': defines.screenWidth // 3, 'h': defines.screenHeight // 3}},
                ]
        self.assertEqual(project.calibrateAreas, result, "calibrateAreas = 9")

        project.config.calibrateRegions = 10
        project.expTime = 10.0
        stripe = defines.screenHeight // 10
        result = [
                {'stripe': True, 'time': 10.0, 'rect': {'x': 0, 'y': 0, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 11.0, 'rect': {'x': 0, 'y': 1 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 12.0, 'rect': {'x': 0, 'y': 2 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 13.0, 'rect': {'x': 0, 'y': 3 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 14.0, 'rect': {'x': 0, 'y': 4 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 15.0, 'rect': {'x': 0, 'y': 5 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 16.0, 'rect': {'x': 0, 'y': 6 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 17.0, 'rect': {'x': 0, 'y': 7 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 18.0, 'rect': {'x': 0, 'y': 8 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                {'stripe': True, 'time': 19.0, 'rect': {'x': 0, 'y': 9 * stripe, 'w': defines.screenWidth, 'h': stripe}},
                ]
        self.assertEqual(project.calibrateAreas, result, "calibrateAreas = 10")

if __name__ == '__main__':
    unittest.main()
