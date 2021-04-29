# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import weakref

from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.states.wizard import WizardId
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.display import DisplayTest
from sl1fw.wizard.checks.tilt import TiltLevelTest
from sl1fw.wizard.checks.tower import TowerHome
from sl1fw.hardware.printer_model import PrinterModel
from sl1fw.wizard.checks.uvleds_sl1 import UVLEDsTest_SL1
from sl1fw.wizard.checks.uvleds_sl1s import UVLEDsTest_SL1S
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.setup import Configuration, TankSetup
from sl1fw.wizard.wizard import Wizard, WizardDataPackage
from sl1fw.wizard.wizards.generic import ShowResultsGroup
from sl1fw.errors.errors import UnknownPrinterModel

class DisplayTestCheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        if package.hw.printer_model == PrinterModel.SL1:
            uvled_test = UVLEDsTest_SL1(package.hw)
        elif package.hw.printer_model == PrinterModel.SL1S:
            uvled_test = UVLEDsTest_SL1S(package.hw)
        else:
            raise UnknownPrinterModel()
        super().__init__(
            Configuration(TankSetup.REMOVED, None),
            [uvled_test, TowerHome(package.hw), TiltLevelTest(package.hw), DisplayTest(package.hw, package.exposure_image, package.runtime_config)],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.prepare_displaytest_done, WizardState.PREPARE_DISPLAY_TEST)


class DisplayTestWizard(Wizard):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(
            hw=hw,
            exposure_image=weakref.proxy(exposure_image),
            runtime_config=runtime_config
        )
        super().__init__(
            WizardId.DISPLAY,
            [
                DisplayTestCheckGroup(self._package),
                ShowResultsGroup(),
            ],
            self._package
        )

    @property
    def name(self) -> str:
        return "display_test"
