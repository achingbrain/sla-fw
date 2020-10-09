# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from sl1fw.libConfig import HwConfig
from sl1fw.states.project import ProjectErrors, LayerCalibrationType
from sl1fw.project.project import Project, ProjectLayer
from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.utils.bounding_box import BBox

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
        self.assertEqual.__self__.maxDiff = None
        self.hwConfig = HwConfig(self.SAMPLES_DIR / "hardware.cfg")

    def test_read(self):
        project = Project(self.hwConfig, "bad_file")
        self.assertEqual(ProjectErrors.NOT_FOUND, project.error, "Bad file test")

        project = Project(self.hwConfig, str(self.SAMPLES_DIR / "numbers.sl1"))
        self.assertEqual(ProjectErrors.NONE, project.error, "Base project read test")
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
        project = Project(self.hwConfig, str(self.SAMPLES_DIR / "Resin_calibration_linear_object.sl1"))
        self.assertEqual(ProjectErrors.NONE, project.error, "Calibration project read test")
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

        # TODO check project preview/icon image


#    def test_project_modification(self):
        # BIG TODO!

#        project.expTime = 5.0
#        self.assertAlmostEqual(project.expTime, 5.0, msg="Check expTime value")
#        self.assertEqual(project.calibrateAreas, [], "calibrateAreas")

        # project.config.write("projectconfig.txt")

if __name__ == '__main__':
    unittest.main()