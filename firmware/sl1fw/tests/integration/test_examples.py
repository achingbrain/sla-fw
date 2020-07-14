# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from time import sleep

import pydbus

from sl1fw.tests.integration.base import Sl1FwIntegrationTestCaseBase
from sl1fw.states.examples import ExamplesState
from sl1fw.api.examples0 import Examples0
from sl1fw.api.printer0 import Printer0


class TestIntegrationExamples0(Sl1FwIntegrationTestCaseBase):
    def setUp(self):
        super().setUp()
        self.printer0: Printer0 = pydbus.SystemBus().get("cz.prusa3d.sl1.printer0")

    def test_example_download(self):
        dbus_path = self.printer0.download_examples()
        self.assertEqual(dbus_path, "/cz/prusa3d/sl1/examples0", "Examples0 dbus path")
        examples0 = pydbus.SystemBus().get(Examples0.__INTERFACE__)
        for _ in range(100):
            if ExamplesState(examples0.state) == ExamplesState.FAILURE:
                break
            sleep(0.1)
        self.assertEqual(ExamplesState.FAILURE, ExamplesState(examples0.state), "Failure, network not simulated")


if __name__ == "__main__":
    unittest.main()
