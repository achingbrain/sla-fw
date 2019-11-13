# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

import pydbus

from sl1fw.api.states import DisplayTest0State
from sl1fw.tests.integration.base import Sl1FwIntegrationTestCaseBase


class TestIntegrationRawDisplayTest(Sl1FwIntegrationTestCaseBase):
    def test_displaytest_start(self):
        printer0 = pydbus.SystemBus().get("cz.prusa3d.sl1.printer0")
        path = printer0.display_test()
        self.assertIsNot(None, path)


class TestIntegrationDisplayTest0(Sl1FwIntegrationTestCaseBase):
    def setUp(self):
        super().setUp()
        self.bus = pydbus.SystemBus()
        self.printer0 = self.bus.get("cz.prusa3d.sl1.printer0")
        path = self.printer0.display_test()
        self.displaytest0 = self.bus.get("cz.prusa3d.sl1.displaytest0", path)

    def test_init(self):
        self.assertEqual(DisplayTest0State.INIT.value, self.displaytest0.state)
        self.displaytest0.finish(True)

    def test_pass(self):
        self.assertEqual(DisplayTest0State.INIT.value, self.displaytest0.state)
        self.displaytest0.start()
        self.assertEqual(DisplayTest0State.COVER_OPEN.value, self.displaytest0.state)
        self.displaytest0.finish(True)


if __name__ == '__main__':
    unittest.main()
