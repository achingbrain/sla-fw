# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Iterable

from slafw.configs.runtime import RuntimeConfig
from slafw.hardware.base.hardware import BaseHardware
from slafw.image.exposure_image import ExposureImage
from slafw.states.wizard import WizardId
from slafw.states.wizard import WizardState
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.calibration_info import CalibrationInfo
from slafw.wizard.checks.display import DisplayTest
from slafw.wizard.checks.resin import ResinSensorTest
from slafw.wizard.checks.sn import SerialNumberTest
from slafw.wizard.checks.speaker import SpeakerTest
from slafw.wizard.checks.sysinfo import SystemInfoTest
from slafw.wizard.checks.temperature import TemperatureTest
from slafw.wizard.checks.tilt import TiltRangeTest, TiltHomeTest
from slafw.wizard.checks.tower import TowerHomeTest, TowerRangeTest
from slafw.wizard.checks.uvfans import UVFansTest
from slafw.wizard.checks.uvleds import UVLEDsTest
from slafw.wizard.group import CheckGroup
from slafw.wizard.setup import Configuration, TankSetup, PlatformSetup
from slafw.wizard.wizard import Wizard, WizardDataPackage
from slafw.wizard.wizards.generic import ShowResultsGroup


class SelfTestPart1CheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        self._package = package
        super().__init__(
            Configuration(TankSetup.REMOVED, PlatformSetup.PRINT),
            [
                SerialNumberTest(package.hw),
                SystemInfoTest(package.hw),
                TemperatureTest(package.hw),
                SpeakerTest(),
                TiltHomeTest(package.hw),
                TiltRangeTest(package.hw),
                TowerHomeTest(package.hw, package.config_writer),
                UVLEDsTest(package.hw),
                UVFansTest(package.hw),
                DisplayTest(package.hw, package.exposure_image, package.runtime_config),
                CalibrationInfo(package.hw.config),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.prepare_wizard_part_1_done, WizardState.PREPARE_WIZARD_PART_1)


class SelfTestPart2CheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.RESIN_TEST),
            [
                ResinSensorTest(package.hw)
            ]
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.prepare_wizard_part_2_done, WizardState.PREPARE_WIZARD_PART_2)


class SelfTestPart3CheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [
                TowerRangeTest(package.hw)
            ]
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.prepare_wizard_part_3_done, WizardState.PREPARE_WIZARD_PART_3)


class SelfTestWizard(Wizard):
    def __init__(self, hw: BaseHardware, exposure_image: ExposureImage,
                 runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(
            hw=hw,
            config_writer=hw.config.get_writer(),
            exposure_image=exposure_image,
            runtime_config=runtime_config
        )
        super().__init__(
            WizardId.SELF_TEST,
            [
                SelfTestPart1CheckGroup(self._package),
                SelfTestPart2CheckGroup(self._package),
                SelfTestPart3CheckGroup(self._package),
                ShowResultsGroup(),
            ],
            self._package
        )

    @classmethod
    def get_name(cls) -> str:
        return "self_test"

    @classmethod
    def get_alt_names(cls) -> Iterable[str]:
        names = ["wizard_data.toml", "thewizard_data.toml", "wizard_data"]
        names.extend(super().get_alt_names())
        return names

    def wizard_finished(self):
        self._package.config_writer.showWizard = False

    def wizard_failed(self):
        writer = self._package.hw.config.get_writer()
        writer.showWizard = True
        writer.commit()
