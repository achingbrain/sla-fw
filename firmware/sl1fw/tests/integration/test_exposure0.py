# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

import pydbus

from sl1fw.api.states import Exposure0State
from sl1fw.tests.integration.base import Sl1FwIntegrationTestCaseBase


class TestIntegrationExposure0(Sl1FwIntegrationTestCaseBase):
    def setUp(self):
        super().setUp()
        self.bus = pydbus.SystemBus()
        self.printer0 = self.bus.get("cz.prusa3d.sl1.printer0")
        path = self.printer0.get_current_exposure()
        self.exposure0 = self.bus.get("cz.prusa3d.sl1.exposure0", path)

    def test_init(self):
        self.assertEqual(Exposure0State.INIT.value, self.exposure0.state)

    # TODO: Add some more tests once it is possible to start exposure


if __name__ == '__main__':
    unittest.main()
