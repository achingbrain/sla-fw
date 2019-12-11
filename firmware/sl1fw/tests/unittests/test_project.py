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
        self.hwConfig = HwConfig(self.SAMPLES_DIR / "samples" / "hardware.cfg",
                                 factory_file_path=defines.factoryConfigFile)

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

        # project.config.write("projectconfig.txt")


if __name__ == '__main__':
    unittest.main()
