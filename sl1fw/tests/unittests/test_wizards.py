# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, MagicMock

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw import defines
from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware, Fan
from sl1fw.states.wizard import WizardState, WizardId
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import Check, WizardCheckType
from sl1fw.wizard.groups.base import CheckGroup
from sl1fw.wizard.setup import Configuration, PlatformSetup, TankSetup
from sl1fw.wizard.wizard import Wizard
from sl1fw.wizard.wizards.calibration import CalibrationWizard
from sl1fw.wizard.wizards.displaytest import DisplayTestWizard
from sl1fw.wizard.wizards.self_test import SelfTestWizard
from sl1fw.wizard.wizards.unboxing import CompleteUnboxingWizard, KitUnboxingWizard

from sl1fw.wizard.wizard import serializer

class TestGroup(CheckGroup):
    setup = AsyncMock()


class TestWizardInfrastructure(Sl1fwTestCase):
    # pylint: disable=no-self-use

    def test_wizard_group_run(self):
        group = AsyncMock()
        group.checks = []
        # group.setup.return_value = None

        wizard = Wizard(WizardId.SELF_TEST, [group], Mock(), RuntimeConfig())
        self.assertEqual(WizardState.INIT, wizard.state)
        wizard.start()
        wizard.join()

        self.assertEqual(WizardState.DONE, wizard.state)
        group.run.assert_called()
        group.run.assert_awaited()

    def test_wizard_failure(self):
        # pylint: disable = too-many-ancestors
        class Test(MagicMock, Check):
            async def async_task_run(self, actions: UserActionBroker):
                pass

            def __init__(self):
                MagicMock.__init__(self)
                Check.__init__(self, WizardCheckType.UNKNOWN, Mock(), [])

        check = Test()
        exception = Exception("Synthetic fail")
        task_body = AsyncMock()
        task_body.side_effect = exception
        check.async_task_run = task_body
        wizard = Wizard(WizardId.SELF_TEST, [TestGroup(Mock(), [check])], Mock(), RuntimeConfig())
        wizard.start()
        wizard.join()

        self.assertEqual(WizardState.FAILED, wizard.state)
        self.assertEqual(exception, wizard.exception)

    def test_wizard_warning(self):
        warning = Warning("Warning")

        class Test(Check):
            async def async_task_run(self, actions: UserActionBroker):
                self.add_warning(warning)

            def __init__(self):
                super().__init__(WizardCheckType.UNKNOWN, Mock(), [])

        check = Test()
        wizard = Wizard(WizardId.SELF_TEST, [TestGroup(Mock(), [check])], Mock(), RuntimeConfig())
        wizard.start()
        wizard.join()

        self.assertEqual(WizardState.DONE, wizard.state)
        self.assertIn(warning, wizard.warnings)

    def test_group_setup(self):
        test = TestGroup(Mock(), [])
        actions = Mock()
        asyncio.run(test.run(actions))
        test.setup.assert_called()

    def test_check_execution(self):
        check = AsyncMock()
        actions = Mock()
        group = TestGroup(Mock(), [check])
        asyncio.run(group.run(actions))

        check.run.assert_called()

    def test_configuration_match(self):
        check = Mock()
        check.configuration = Configuration(TankSetup.UV, PlatformSetup.RESIN_TEST)

        with self.assertRaises(ValueError):
            TestGroup(Configuration(TankSetup.PRINT, PlatformSetup.PRINT), [check])


class TestWizards(Sl1fwTestCase):
    @staticmethod
    def _get_hw_mock():
        hw = Mock()
        hw.__class__ = Hardware
        hw.__reduce__ = lambda self: (Mock, ())
        hw.is500khz = True
        hw.getUvLedState.return_value = (False, 0)
        hw.getUvStatistics.return_value = (6912, 3600)
        hw.isTiltOnPosition.return_value = True
        hw.isTiltMoving.return_value = False
        hw.getMcTemperatures.return_value = [46.7, 26.1, 0, 0]
        hw.getResinVolume.return_value = defines.resinWizardMaxVolume
        hw.towerPositonFailed.return_value = False
        hw.getFansError.return_value = {0: False, 1: False, 2: False}
        hw.getCpuTemperature.return_value = 53.5
        hw.cpuSerialNo = "CZPX0819X009XC00151"
        hw.mcSerialNo = "CZPX0619X678XC12345"
        hw.getTiltPosition.return_value = 0
        hw.getVoltages.return_value = [11.203, 11.203, 11.203, 0]
        hw.getUvLedTemperature.return_value = 46.7
        hw.tilt_position = 5000
        hw.tower_position_nm = defines.defaultTowerHeight * 1000 * 1000 * 1000

        hw_config = HwConfig()
        hw.fans = {
            0: Fan("UV LED fan", defines.fanMaxRPM[0], hw_config.fan1Rpm, hw_config.fan1Enabled),
            1: Fan("blower fan", defines.fanMaxRPM[1], hw_config.fan2Rpm, hw_config.fan2Enabled),
            2: Fan("rear fan", defines.fanMaxRPM[2], hw_config.fan3Rpm, hw_config.fan3Enabled),
        }
        hw.getFansRpm.return_value = [hw_config.fan1Rpm, hw_config.fan2Rpm, hw_config.fan3Rpm]
        hw.isTowerMoving.return_value = False
        hw.tower_end = hw_config.calcMicroSteps(150)
        hw.getTowerPositionMicroSteps.return_value = hw.tower_end
        hw.tower_above_surface = hw.tower_end
        hw.tower_min = hw.tower_end - 1
        hw.tower_calib_pos = hw.tower_end
        hw.mcFwVersion = "1.0.0"
        hw.mcBoardRevision = "6c"

        return hw

    def test_self_test_data(self):
        hw_config = HwConfig()
        hw_config.uvWarmUpTime = 0
        wizard = SelfTestWizard(self._get_hw_mock(), hw_config, Mock(), RuntimeConfig())

        def on_state_changed():
            if wizard.state == WizardState.PREPARE_WIZARD_PART_1:
                wizard.prepare_wizard_part_1_done()
            if wizard.state == WizardState.TEST_AUDIO:
                wizard.report_audio(True)
            if wizard.state == WizardState.TEST_DISPLAY:
                wizard.report_display(True)
            if wizard.state == WizardState.PREPARE_WIZARD_PART_2:
                wizard.prepare_wizard_part_2_done()
            if wizard.state == WizardState.PREPARE_WIZARD_PART_3:
                wizard.prepare_wizard_part_3_done()

        wizard.state_changed.connect(on_state_changed)
        self._run_wizard(wizard)

        wizard_data_path = defines.configDir / wizard.data_filename
        self.assertTrue(wizard_data_path.exists(), "Wizard data file exists")
        print(f"Wizard data:\n{wizard_data_path.read_text()}")
        with wizard_data_path.open("rt") as file:
            data = serializer.load(file)

        self.assertEqual("CZPX0819X009XC00151", data["a64SerialNo"])
        self.assertIn("osVersion", data)
        self.assertEqual("CZPX0619X678XC12345", data["mcSerialNo"])
        self.assertEqual("1.0.0", data["mcFwVersion"])
        self.assertEqual("6c", data["mcBoardRev"])

        self.assertEqual(96000, data["towerHeight"])
        self.assertEqual(4928, data["tiltHeight"])
        self.assertIn("uvPwm", data)

        self.assertListEqual([11203, 11203, 11203,], data["wizardUvVoltageRow1"])
        self.assertListEqual([11203, 11203, 11203,], data["wizardUvVoltageRow2"])
        self.assertListEqual([11203, 11203, 11203,], data["wizardUvVoltageRow3"])
        self.assertListEqual([hw_config.fan1Rpm, hw_config.fan2Rpm, hw_config.fan3Rpm], data["wizardFanRpm"])
        self.assertEqual(46.7, data["wizardTempUvInit"])
        self.assertEqual(46.7, data["wizardTempUvWarm"])
        self.assertEqual(26.1, data["wizardTempAmbient"])
        self.assertEqual(53.5, data["wizardTempA64"])
        self.assertEqual(defines.resinWizardMaxVolume, data["wizardResinVolume"])
        self.assertEqual(0, data["towerSensitivity"])

    def test_display_test(self):
        wizard = DisplayTestWizard(self._get_hw_mock(), HwConfig(), Mock(), RuntimeConfig())

        def on_state_changed():
            if wizard.state == WizardState.PREPARE_DISPLAY_TEST:
                wizard.prepare_displaytest_done()
            if wizard.state == WizardState.TEST_DISPLAY:
                wizard.report_display(True)

        wizard.state_changed.connect(on_state_changed)
        self._run_wizard(wizard)

    def test_unboxing_complete(self):
        wizard = CompleteUnboxingWizard(self._get_hw_mock(), HwConfig(), RuntimeConfig())

        def on_state_changed():
            if wizard.state == WizardState.REMOVE_SAFETY_STICKER:
                wizard.safety_sticker_removed()
            if wizard.state == WizardState.REMOVE_SIDE_FOAM:
                wizard.side_foam_removed()
            if wizard.state == WizardState.REMOVE_TANK_FOAM:
                wizard.tank_foam_removed()
            if wizard.state == WizardState.REMOVE_DISPLAY_FOIL:
                wizard.display_foil_removed()

        wizard.state_changed.connect(on_state_changed)
        self._run_wizard(wizard)

    def test_unboxing_kit(self):
        wizard = KitUnboxingWizard(self._get_hw_mock(), HwConfig(), RuntimeConfig())

        def on_state_changed():
            if wizard.state == WizardState.REMOVE_DISPLAY_FOIL:
                wizard.display_foil_removed()

        wizard.state_changed.connect(on_state_changed)
        self._run_wizard(wizard)

    def test_calibration(self):
        wizard = CalibrationWizard(self._get_hw_mock(), HwConfig(), RuntimeConfig())

        def on_state_changed():
            if wizard.state == WizardState.PREPARE_CALIBRATION_PLATFORM_INSERT:
                wizard.prepare_calibration_platform_insert_done()
            if wizard.state == WizardState.PREPARE_CALIBRATION_TANK_PLACEMENT:
                wizard.prepare_calibration_tank_placement_done()
            if wizard.state == WizardState.PREPARE_CALIBRATION_TILT_ALIGN:
                wizard.prepare_calibration_tilt_align_done()
            if wizard.state == WizardState.LEVEL_TILT:
                wizard.tilt_aligned()
            if wizard.state == WizardState.PREPARE_CALIBRATION_PLATFORM_ALIGN:
                wizard.prepare_calibration_platform_align_done()
            if wizard.state == WizardState.PREPARE_CALIBRATION_FINISH:
                wizard.prepare_calibration_finish_done()

        wizard.state_changed.connect(on_state_changed)
        self._run_wizard(wizard)

    def _run_wizard(self, wizard: Wizard, limit_s: int = 5):
        wizard.start()
        wizard.join(limit_s)
        if wizard.is_alive():
            wizard.cancel()
            wizard.abort()
            wizard.join()
        self.assertEqual(WizardState.DONE, wizard.state)


if __name__ == "__main__":
    unittest.main()
