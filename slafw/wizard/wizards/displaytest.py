# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import weakref

from slafw.configs.runtime import RuntimeConfig
from slafw.image.exposure_image import ExposureImage
from slafw.libHardware import Hardware
from slafw.states.wizard import WizardId
from slafw.states.wizard import WizardState
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.display import DisplayTest
from slafw.wizard.checks.uvleds import UVLEDsTest
from slafw.wizard.group import CheckGroup
from slafw.wizard.setup import Configuration, TankSetup
from slafw.wizard.wizard import Wizard, WizardDataPackage
from slafw.wizard.wizards.generic import ShowResultsGroup


class DisplayTestCheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.REMOVED, None),
            [UVLEDsTest.get_test(package.hw), DisplayTest(package.hw, package.exposure_image, package.runtime_config)],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.prepare_displaytest_done, WizardState.PREPARE_DISPLAY_TEST)


class DisplayTestWizard(Wizard):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(
            hw=hw, exposure_image=weakref.proxy(exposure_image), runtime_config=runtime_config
        )
        super().__init__(
            WizardId.DISPLAY,
            [
                DisplayTestCheckGroup(self._package),
                ShowResultsGroup(),
            ],
            self._package,
        )

    @classmethod
    def get_name(cls) -> str:
        return "display_test"
