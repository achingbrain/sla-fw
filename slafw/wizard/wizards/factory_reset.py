# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.configs.runtime import RuntimeConfig
from slafw.functions.system import shut_down
from slafw.hardware.base import BaseHardware
from slafw.states.wizard import WizardId, WizardState
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.factory_reset import (
    DisableFactory,
    ResetHostname,
    ResetAPIKey,
    ResetRemoteConfig,
    ResetHttpDigest,
    ResetWifi,
    ResetTimezone,
    ResetNTP,
    ResetLocale,
    ResetUVCalibrationData,
    RemoveSlicerProfiles,
    ResetHWConfig,
    EraseMCEeprom,
    ResetHomingProfiles,
    EraseProjects,
    SendPrinterData,
    InitiatePackingMoves,
    FinishPackingMoves,
    DisableAccess,
    ResetTouchUI,
)
from slafw.wizard.group import CheckGroup
from slafw.wizard.setup import Configuration
from slafw.wizard.wizard import Wizard, WizardDataPackage


class ResetSettingsGroup(CheckGroup):
    def __init__(
        self,
        package: WizardDataPackage,
        disable_unboxing: bool,
        erase_projects: bool = False,
        hard_errors: bool = False,
    ):
        checks = [
            ResetHostname(package.model, hard_errors=hard_errors),
            ResetAPIKey(hard_errors=hard_errors),
            ResetRemoteConfig(hard_errors=hard_errors),
            ResetHttpDigest(hard_errors=hard_errors),
            ResetWifi(hard_errors=hard_errors),
            ResetTimezone(hard_errors=hard_errors),
            ResetNTP(hard_errors=hard_errors),
            ResetLocale(hard_errors=hard_errors),
            ResetUVCalibrationData(hard_errors=hard_errors),
            RemoveSlicerProfiles(hard_errors=hard_errors),
            ResetHWConfig(package.hw, disable_unboxing=disable_unboxing, hard_errors=hard_errors),
            EraseMCEeprom(package.hw, hard_errors=hard_errors),
            ResetHomingProfiles(package.hw, hard_errors=hard_errors),
            DisableAccess(),
            ResetTouchUI(),
        ]
        if erase_projects:
            checks.append(EraseProjects(hard_errors=hard_errors))
        super().__init__(Configuration(None, None), checks)

    async def setup(self, actions: UserActionBroker):
        pass


class SendPrinterDataGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(Configuration(None, None), [SendPrinterData(package.hw)])

    async def setup(self, actions: UserActionBroker):
        pass


class PackStage1(CheckGroup):
    def __init__(
        self, package: WizardDataPackage, packs_moves: bool = True,
    ):
        checks = [DisableFactory(package.hw, package.runtime_config)]
        if packs_moves:
            checks.append(InitiatePackingMoves(package.hw))
        super().__init__(Configuration(None, None), checks)

    async def setup(self, actions: UserActionBroker):
        pass


class PackStage2(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(Configuration(None, None), [FinishPackingMoves(package.hw)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.foam_inserted, WizardState.INSERT_FOAM)


class FactoryResetWizard(Wizard):
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        hw: BaseHardware,
        runtime_config: RuntimeConfig,
        erase_projects: bool = False,
    ):
        self._package = WizardDataPackage(
            hw=hw,
            runtime_config=runtime_config
        )
        super().__init__(
            WizardId.FACTORY_RESET,
            [ResetSettingsGroup(self._package, True, erase_projects)],
            self._package
        )

    def run(self):
        super().run()
        shut_down(self._hw, reboot=True)


class PackingWizard(Wizard):
    def __init__(self, hw: BaseHardware, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(
            hw=hw,
            runtime_config=runtime_config
        )
        groups = [
            SendPrinterDataGroup(self._package),
            ResetSettingsGroup(self._package, disable_unboxing=False, erase_projects=False, hard_errors=True),
        ]
        if self._package.hw.isKit:
            groups.append(PackStage1(self._package, False))
        else:
            groups.append(PackStage1(self._package, True))
            groups.append(PackStage2(self._package))

        super().__init__(WizardId.PACKING, groups, self._package)

    def run(self):
        super().run()
        if self.state == WizardState.DONE:
            shut_down(self._hw)
