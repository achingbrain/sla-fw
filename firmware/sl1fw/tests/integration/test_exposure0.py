# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
from time import sleep

import pydbus
from sl1codes.errors import Errors
from sl1codes.warnings import Warnings

from sl1fw.tests.integration.base import Sl1FwIntegrationTestCaseBase
from sl1fw.api.exposure0 import Exposure0State
from sl1fw.project.project import ProjectState
from sl1fw.errors.warnings import AmbientTooHot


class TestIntegrationExposure0(Sl1FwIntegrationTestCaseBase):
    def setUp(self):
        super().setUp()

        # Fake calibration
        self.printer.hwConfig.calibrated = True
        self.printer.hwConfig.fanCheck = False
        self.printer.hwConfig.coverCheck = False
        self.printer.hwConfig.resinSensor = False

        # Resolve printer and start the print
        self.bus = pydbus.SystemBus()
        self.printer0 = self.bus.get("cz.prusa3d.sl1.printer0")
        expo_path = self.printer0.print(str(self.SAMPLES_DIR / "numbers.sl1"), False)
        self.exposure0 = self.bus.get("cz.prusa3d.sl1.exposure0", expo_path)

    def test_init(self):
        self.assertEqual(Exposure0State.CONFIRM, Exposure0State(self.exposure0.state))
        self.assertEqual("numbers.sl1", Path(self.exposure0.project_file).name)
        self.assertEqual("numbers", self.exposure0.project_name)
        self.assertEqual(0, self.exposure0.current_layer)
        self.assertEqual(0, self.exposure0.calibration_regions)
        self.assertAlmostEqual(87.792032, self.exposure0.total_resin_required_ml, 1)
        self.assertAlmostEqual(50, self.exposure0.total_resin_required_percent, 1)

    def test_print(self):
        self.exposure0.confirm_start()
        self._wait_for_state(Exposure0State.CHECKS, 5)
        self._wait_for_state(Exposure0State.PRINTING, 30)
        self.assertEqual(ProjectState.OK, ProjectState(self.exposure0.project_state))
        self._wait_for_state(Exposure0State.FINISHED, 30)
        self.assertEqual(100, self.exposure0.progress)

    def test_print_cancel(self):
        self.exposure0.confirm_start()
        self.exposure0.cancel()
        self._wait_for_state(Exposure0State.CANCELED, 45)

    def test_print_warning(self):
        self.printer.action_manager.exposure.warnings.append(AmbientTooHot(ambient_temperature=42.0))
        self.exposure0.confirm_start()
        self._wait_for_state(Exposure0State.CHECK_WARNING, 30)

        self.assertEqual(1, len(self.exposure0.exposure_warnings))
        warning = self.exposure0.exposure_warnings[0]
        print(warning)
        self.assertEqual(warning["code"], Warnings.EXPOSURE_AMBIENT_TOO_HOT.value)
        self.assertAlmostEqual(warning["ambient_temperature"], 42.0)
        self.exposure0.reject_print_warnings()
        self._wait_for_state(Exposure0State.FAILURE, 30)

        exception = self.exposure0.exposure_exception
        self.assertIsNotNone(exception)
        self.assertEqual(exception["code"], Errors.EXPOSURE_WARNING_ESCALATION.code)

    def _wait_for_state(self, state: Exposure0State, timeout_s: int):
        for _ in range(timeout_s):
            if self.exposure0.state == state.value:
                break
            sleep(1)
        self.assertEqual(state, Exposure0State(self.exposure0.state))


if __name__ == '__main__':
    unittest.main()
