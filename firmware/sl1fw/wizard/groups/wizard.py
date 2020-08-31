# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.libConfig import HwConfig, RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.display import DisplayTest
from sl1fw.wizard.checks.resin import ResinSensorTest
from sl1fw.wizard.checks.sn import SerialNumberTest
from sl1fw.wizard.checks.speaker import SpeakerTest
from sl1fw.wizard.checks.temperature import TemperatureTest
from sl1fw.wizard.checks.tilt import TiltRangeTest, TiltHomeTest
from sl1fw.wizard.checks.tower import TowerHomeTest, TowerRangeTest
from sl1fw.wizard.checks.uvfans import UVFansTest
from sl1fw.wizard.checks.uvleds import UVLEDsTest
from sl1fw.wizard.groups.base import CheckGroup
from sl1fw.wizard.setup import Configuration, TankSetup, PlatformSetup


class WizardPart1CheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig, screen: Screen, runtime_config: RuntimeConfig):
        super().__init__(
            Configuration(TankSetup.REMOVED, PlatformSetup.PRINT),
            [
                SerialNumberTest(hw),
                TemperatureTest(hw),
                SpeakerTest(),
                TiltHomeTest(hw),
                TiltRangeTest(hw),
                TowerHomeTest(hw, hw_config),
                UVLEDsTest(hw),
                UVFansTest(hw, hw_config),
                DisplayTest(hw, hw_config, screen, runtime_config),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        self._logger.debug("Running part1 setup")
        await self.wait_for_user(actions, actions.prepare_wizard_part_1_done, WizardState.PREPARE_WIZARD_PART_1)
        self._logger.debug("Running part1 setup done")


class WizardPart2CheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(Configuration(TankSetup.PRINT, PlatformSetup.RESIN_TEST), [ResinSensorTest(hw, hw_config)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.prepare_wizard_part_2_done, WizardState.PREPARE_WIZARD_PART_2)


class WizardPart3CheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(Configuration(TankSetup.PRINT, PlatformSetup.PRINT), [TowerRangeTest(hw, hw_config)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.prepare_wizard_part_3_done, WizardState.PREPARE_WIZARD_PART_3)
