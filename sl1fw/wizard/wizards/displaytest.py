# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.states.wizard import WizardId
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.display import DisplayTest
from sl1fw.wizard.checks.tilt import TiltLevelTest
from sl1fw.wizard.checks.tower import TowerHome
from sl1fw.wizard.checks.uvleds import UVLEDsTest
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.setup import Configuration, TankSetup
from sl1fw.wizard.wizard import Wizard


class DisplayTestCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        super().__init__(
            Configuration(TankSetup.REMOVED, None),
            [UVLEDsTest(hw), TowerHome(hw), TiltLevelTest(hw), DisplayTest(hw, exposure_image, runtime_config)],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.prepare_displaytest_done, WizardState.PREPARE_DISPLAY_TEST)


class DisplayTestWizard(Wizard):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        super().__init__(
            WizardId.DISPLAY,
            [DisplayTestCheckGroup(hw, exposure_image, runtime_config)],
            hw,
            runtime_config,
        )

    @property
    def name(self) -> str:
        return "display_test"
