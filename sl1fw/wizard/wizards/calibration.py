# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardId
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.tilt import TiltHomeTest, TiltCalibrationStartTest, TiltAlignTest, TiltTimingTest
from sl1fw.wizard.checks.tower import TowerAlignTest, TowerHomeTest
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.setup import Configuration, TankSetup, PlatformSetup
from sl1fw.wizard.wizard import Wizard


class PlatformTankInsertCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            Configuration(None, None), [TiltHomeTest(hw), TowerHomeTest(hw, hw_config), TiltCalibrationStartTest(hw)]
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions,
            actions.prepare_calibration_platform_tank_done,
            WizardState.PREPARE_CALIBRATION_INSERT_PLATFORM_TANK,
        )


class TiltAlignCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(Configuration(TankSetup.REMOVED, None), [TiltAlignTest(hw, hw_config)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions, actions.prepare_calibration_tilt_align_done, WizardState.PREPARE_CALIBRATION_TILT_ALIGN
        )


class PlatformAlignCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(Configuration(TankSetup.PRINT, PlatformSetup.PRINT), [TowerAlignTest(hw, hw_config)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions, actions.prepare_calibration_platform_align_done, WizardState.PREPARE_CALIBRATION_PLATFORM_ALIGN
        )


class CalibrationFinishCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(Configuration(TankSetup.PRINT, PlatformSetup.PRINT), [TiltTimingTest(hw, hw_config)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions, actions.prepare_calibration_finish_done, WizardState.PREPARE_CALIBRATION_FINISH
        )


class CalibrationWizard(Wizard):
    def __init__(self, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig):
        super().__init__(
            WizardId.CALIBRATION,
            [
                PlatformTankInsertCheckGroup(hw, hw_config),
                TiltAlignCheckGroup(hw, hw_config),
                PlatformAlignCheckGroup(hw, hw_config),
                CalibrationFinishCheckGroup(hw, hw_config),
            ],
            hw,
            runtime_config,
        )

    @property
    def name(self) -> str:
        return "calibration"
