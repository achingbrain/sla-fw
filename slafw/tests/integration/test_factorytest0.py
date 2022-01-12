# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from pydbus import SystemBus

from slafw.tests.integration.base import SlaFwIntegrationTestCaseBase
from slafw.api.factorytests0 import FactoryTests0


class TestIntegrationFactoryTest0(SlaFwIntegrationTestCaseBase):
    def setUp(self):
        super().setUp()
        bus = SystemBus()
        FactoryTests0(self.printer)
        self.ft0 = bus.get("cz.prusa3d.sl1.factorytests0")

    def tearDown(self):
        self.printer.runtime_config.factory_mode = False
        super().tearDown()

    def test_api_basics(self):
        self.ft0.enter_test_mode()

        self.assertFalse(self.ft0.get_uv())
        self.ft0.set_uv(True)
        self.assertTrue(self.ft0.get_uv())
        self.ft0.display_image("logo.png")
        self.ft0.blank_screen()
        self.ft0.invert_screen()

        self.ft0.leave_test_mode()


if __name__ == "__main__":
    unittest.main()
