# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.wizard.checks.sysinfo import SystemInfoTest

from slafw.configs.runtime import RuntimeConfig
from slafw.libHardware import Hardware
from slafw.states.wizard import WizardId
from slafw.states.wizard import WizardState
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.tilt import (
    TiltHomeTest,
    TiltCalibrationStartTest,
    TiltAlignTest,
    TiltTimingTest,
)
from slafw.wizard.checks.tower import TowerAlignTest, TowerHomeTest
from slafw.wizard.group import CheckGroup
from slafw.wizard.setup import Configuration, TankSetup, PlatformSetup
from slafw.wizard.wizard import Wizard, WizardDataPackage
from slafw.wizard.wizards.generic import ShowResultsGroup


class PlatformTankInsertCheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(None, None),
            [
                TiltHomeTest(package.hw),
                TowerHomeTest(package.hw, package.config_writer),
                TiltCalibrationStartTest(package.hw),
                SystemInfoTest(package.hw),
            ],
        )
        self._package = package

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions,
            actions.prepare_calibration_platform_tank_done,
            WizardState.PREPARE_CALIBRATION_INSERT_PLATFORM_TANK,
        )


class TiltAlignCheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.REMOVED, None),
            [TiltAlignTest(package.hw, package.config_writer)],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions,
            actions.prepare_calibration_tilt_align_done,
            WizardState.PREPARE_CALIBRATION_TILT_ALIGN,
        )


class PlatformAlignCheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [TowerAlignTest(package.hw, package.config_writer)],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions,
            actions.prepare_calibration_platform_align_done,
            WizardState.PREPARE_CALIBRATION_PLATFORM_ALIGN,
        )


class CalibrationFinishCheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [TiltTimingTest(package.hw, package.config_writer)],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(
            actions,
            actions.prepare_calibration_finish_done,
            WizardState.PREPARE_CALIBRATION_FINISH,
        )


class CalibrationWizard(Wizard):
    def __init__(self, hw: Hardware, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(hw=hw, config_writer=hw.config.get_writer(), runtime_config=runtime_config)
        super().__init__(
            WizardId.CALIBRATION,
            [
                PlatformTankInsertCheckGroup(self._package),
                TiltAlignCheckGroup(self._package),
                PlatformAlignCheckGroup(self._package),
                CalibrationFinishCheckGroup(self._package),
                ShowResultsGroup(),
            ],
            self._package,
        )

    @classmethod
    def get_name(cls) -> str:
        return "calibration"

    def wizard_finished(self):
        self._package.config_writer.calibrated = True

    def wizard_failed(self):
        writer = self._package.hw.config.get_writer()
        writer.calibrated = False
        writer.commit()
