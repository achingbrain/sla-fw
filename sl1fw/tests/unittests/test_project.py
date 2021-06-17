# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import unittest
from pathlib import Path

from sl1fw import defines
from sl1fw.configs.hw import HwConfig
from sl1fw.tests.mocks.hardware import Hardware
from sl1fw.errors.errors import ProjectErrorNotFound, ProjectErrorNotEnoughLayers, \
                                ProjectErrorCorrupted, ProjectErrorWrongPrinterModel, \
                                ProjectErrorCantRead, ProjectErrorCalibrationInvalid
from sl1fw.errors.warnings import PrintingDirectlyFromMedia
from sl1fw.project.project import Project, ProjectLayer, LayerCalibrationType, ExposureUserProfile
from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.utils.bounding_box import BBox
from sl1fw.hardware.printer_model import PrinterModel


def _layer_generator(name, count, height_nm, times_ms, layer_times_ms):
    layers = []
    for i in range(count):
        layer = ProjectLayer('%s%05d.png' % (name, i), height_nm)
        if i >= len(layer_times_ms):
            times_ms[0] = layer_times_ms[-1]
        else:
            times_ms[0] = layer_times_ms[i]
        layer.times_ms = tuple(times_ms)
        if i < 10:
            layer.calibration_type = LayerCalibrationType.LABEL_PAD
        else:
            layer.calibration_type = LayerCalibrationType.LABEL_TEXT
        layers.append(layer)
    return layers


class TestProject(Sl1fwTestCase):
    def setUp(self):
        super().setUp()
        self.assertEqual.__self__.maxDiff = None
        self.hw_config = HwConfig(self.SAMPLES_DIR / "hardware.cfg")
        self.hw_config.read_file()
        self.hw = Hardware(self.hw_config)
        self.file2copy = self.SAMPLES_DIR / "Resin_calibration_object.sl1"
        (dummy, filename) = os.path.split(self.file2copy)
        self.destfile = Path(os.path.join(defines.previousPrints, filename))

    def test_notfound(self):
        with self.assertRaises(ProjectErrorNotFound):
            Project(self.hw, "bad_file")

    def test_empty(self):
        with self.assertRaises(ProjectErrorCantRead):
            Project(self.hw, str(self.SAMPLES_DIR / "empty_file.sl1"))

    def test_truncated(self):
        with self.assertRaises(ProjectErrorCantRead):
            Project(self.hw, str(self.SAMPLES_DIR / "test_truncated.sl1"))

    def test_nolayers(self):
        with self.assertRaises(ProjectErrorNotEnoughLayers):
            Project(self.hw, str(self.SAMPLES_DIR / "test_nolayer.sl1"))

    def test_corrupted(self):
        project = Project(self.hw, str(self.SAMPLES_DIR / "test_corrupted.sl1"))
        with self.assertRaises(ProjectErrorCorrupted):
            project.copy_and_check()

    def test_copy_and_check(self):
        project = Project(self.hw, str(self.file2copy))
        project.copy_and_check()
        self.assertFalse(PrintingDirectlyFromMedia() in project.warnings, "Printed directly warning issued")
        self.destfile.unlink()

    def test_avaiable_space_check_usb(self):
        statvfs = os.statvfs(os.path.dirname(defines.previousPrints))
        backup = defines.internalReservedSpace
        defines.internalReservedSpace = statvfs.f_frsize * statvfs.f_bavail
        project = Project(self.hw, str(self.file2copy))
        project.copy_and_check()
        self.assertTrue(PrintingDirectlyFromMedia() in project.warnings, "Printed directly warning not issued")
        defines.internalReservedSpace = backup

    def test_avaiable_space_check_internal(self):
        statvfs = os.statvfs(os.path.dirname(defines.previousPrints))
        backup1 = defines.internalReservedSpace
        backup2 = defines.internalProjectPath
        defines.internalReservedSpace = statvfs.f_frsize * statvfs.f_bavail
        defines.internalProjectPath = str(self.SAMPLES_DIR)
        project = Project(self.hw, str(self.file2copy))
        project.copy_and_check()
        self.assertFalse(PrintingDirectlyFromMedia() in project.warnings, "Printed directly warning issued")
        self.destfile.unlink()
        defines.internalReservedSpace = backup1
        defines.internalProjectPath = backup2

    def test_printer_model(self):
        hw = Hardware(self.hw_config)
        hw.printer_model = PrinterModel.NONE
        with self.assertRaises(ProjectErrorWrongPrinterModel):
            Project(hw, str(self.SAMPLES_DIR / "numbers.sl1"))

    def test_read(self):
        project = Project(self.hw, str(self.SAMPLES_DIR / "numbers.sl1"))
        print(project)

        self.assertEqual(project.name, "numbers", "Check project name")
        self.assertEqual(project.total_layers, 2, "Check total layers count")
        self.assertEqual(project.total_height_nm, 1e5, "Total height calculation")
        self.assertAlmostEqual(project.modification_time, 1569863651.0, msg="Check modification time")

        result = _layer_generator('numbers', 2, 50000, [1000], (1000,))
        self.assertEqual(project.layers, result, "Base layers")
        #consumed_resin_slicer = project.used_material_nl / 1e6
        project.analyze()
        print(project)
        result[0].bbox = BBox((605, 735, 835, 1825))
        result[1].bbox = BBox((605, 735, 835, 1825))
        result[0].consumed_resin_nl = 25664
        result[1].consumed_resin_nl = 20819
        self.assertEqual(project.layers, result, "Analyzed base layers")
        # FIXME project usedMaterial is wrong (modified project)
        #self.assertAlmostEqual(consumed_resin_slicer, project.used_material_nl / 1e6, delta=0.1, msg="Resin count")

    def test_read_calibration(self):
        project = Project(self.hw, str(self.SAMPLES_DIR / "Resin_calibration_linear_object.sl1"))
        print(project)

        self.assertEqual(project.total_layers, 20, "Check total layers count")
        self.assertEqual(project.total_height_nm, 1e6, "Total height calculation")
        self.assertEqual(project.count_remain_time(), 478750, "Total time calculation")
        self.assertEqual(project.count_remain_time(layers_done = 10), 177500, "Half time calculation")

        result = _layer_generator('sl1_linear_calibration_pattern',
                20,
                50000,
                [7500, 500, 500, 500, 500, 500, 500, 500, 500, 500],
                [35000, 35000, 35000, 28125, 21250, 14375, 7500])
        self.assertEqual(project.layers, result, "Calibration layers")
        consumed_resin_slicer = project.used_material_nl / 1e6
        project.analyze()
        print(project)
        project.analyze()
        self.assertAlmostEqual(consumed_resin_slicer, project.used_material_nl / 1e6, delta=0.1, msg="Resin count")
        # TODO analyze check

    def test_project_modification(self):
        project = Project(self.hw, str(self.SAMPLES_DIR / "Resin_calibration_linear_object.sl1"))
        with self.assertRaises(ProjectErrorCalibrationInvalid):
            project.calibrate_regions = 3

        # BIG TODO!
#        project.expTime = 5.0
#        self.assertAlmostEqual(project.expTime, 5.0, msg="Check expTime value")
#        self.assertEqual(project.calibrateAreas, [], "calibrateAreas")

        # project.config.write("projectconfig.txt")


    def test_project_remaining_time_estimate_with_tilt(self):
        project = Project(self.hw, str(self.SAMPLES_DIR / "numbers.sl1"))
        self.assertEqual(13500, project.count_remain_time(0, 0))

    def test_project_remaining_time_estimate_without_tilt(self):
        self.hw.config.tilt = False
        project = Project(self.hw, str(self.SAMPLES_DIR / "numbers.sl1"))
        self.assertEqual(2500, project.count_remain_time(0, 0))

    def test_project_exposure_user_profile(self):
        project = Project(self.hw, str(self.SAMPLES_DIR / "layer_change.sl1"))
        self.assertEqual(ExposureUserProfile.DEFAULT, project.exposure_user_profile)

        project = Project(self.hw, str(self.SAMPLES_DIR / "layer_change_safe_profile.sl1"))
        self.assertEqual(ExposureUserProfile.SAFE, project.exposure_user_profile)

if __name__ == '__main__':
    unittest.main()
