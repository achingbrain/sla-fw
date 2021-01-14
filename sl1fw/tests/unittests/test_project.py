# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from sl1fw.libConfig import HwConfig
from sl1fw.errors.errors import ProjectErrorNotFound, ProjectErrorNotEnoughLayers, \
                                ProjectErrorCorrupted, ProjectErrorWrongPrinterModel, \
                                ProjectErrorCantRead, ProjectErrorCalibrationInvalid
from sl1fw.project.project import Project, ProjectLayer, LayerCalibrationType
from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.utils.bounding_box import BBox
from sl1fw.screen.printer_model import PrinterModelTypes


def _layer_generator(name, count, height_nm, times_ms, layer_times_ms):
    layers = []
    for i in range(count):
        layer = ProjectLayer('%s%05d.png' % (name, i), height_nm)
        if i >= len(layer_times_ms):
            times_ms[0] = layer_times_ms[-1]
        else:
            times_ms[0] = layer_times_ms[i]
        layer.times_ms = times_ms.copy()
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
        self.hwConfig = HwConfig(self.SAMPLES_DIR / "hardware.cfg")
        self.printer_model = PrinterModelTypes.SL1.parameters()

    def test_notfound(self):
        with self.assertRaises(ProjectErrorNotFound):
            Project(self.hwConfig, self.printer_model, "bad_file")

    def test_empty(self):
        with self.assertRaises(ProjectErrorCantRead):
            Project(self.hwConfig, self.printer_model, str(self.SAMPLES_DIR / "empty_file.sl1"))

    def test_truncated(self):
        with self.assertRaises(ProjectErrorCantRead):
            Project(self.hwConfig, self.printer_model, str(self.SAMPLES_DIR / "test_truncated.sl1"))

    def test_nolayers(self):
        with self.assertRaises(ProjectErrorNotEnoughLayers):
            Project(self.hwConfig, self.printer_model, str(self.SAMPLES_DIR / "test_nolayer.sl1"))

    def test_corrupted(self):
        project = Project(self.hwConfig, self.printer_model, str(self.SAMPLES_DIR / "test_corrupted.sl1"))
        with self.assertRaises(ProjectErrorCorrupted):
            project.copy_and_check()

    def test_printer_model(self):
        self.printer_model = PrinterModelTypes.TEST.parameters()
        with self.assertRaises(ProjectErrorWrongPrinterModel):
            Project(self.hwConfig, self.printer_model, str(self.SAMPLES_DIR / "numbers.sl1"))

    def test_read(self):
        project = Project(self.hwConfig, self.printer_model, str(self.SAMPLES_DIR / "numbers.sl1"))
        print(project)

        self.assertEqual(project.name, "numbers", "Check project name")
        self.assertEqual(project.total_layers, 2, "Check total layers count")
        self.assertEqual(project.total_height_nm, 1e5, "Total height calculation")
        self.assertAlmostEqual(project.modification_time, 1569863651.0, msg="Check modification time")

        result = _layer_generator('numbers', 2, 50000, [1000], [1000])
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
        project = Project(self.hwConfig, self.printer_model, str(self.SAMPLES_DIR / "Resin_calibration_linear_object.sl1"))
        print(project)

        self.assertEqual(project.total_layers, 20, "Check total layers count")
        self.assertEqual(project.total_height_nm, 1e6, "Total height calculation")
        self.assertEqual(project.count_remain_time(), 8, "Total time calculation")
        self.assertEqual(project.count_remain_time(layers_done = 10), 3, "Half time calculation")

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
        project = Project(self.hwConfig, self.printer_model, str(self.SAMPLES_DIR / "Resin_calibration_linear_object.sl1"))
        with self.assertRaises(ProjectErrorCalibrationInvalid):
            project.calibrate_regions = 3

        # BIG TODO!
#        project.expTime = 5.0
#        self.assertAlmostEqual(project.expTime, 5.0, msg="Check expTime value")
#        self.assertEqual(project.calibrateAreas, [], "calibrateAreas")

        # project.config.write("projectconfig.txt")


if __name__ == '__main__':
    unittest.main()
