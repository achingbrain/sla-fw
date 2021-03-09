# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.functions.system import shut_down
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardId, WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.factory_reset import (
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
)
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.setup import Configuration
from sl1fw.wizard.wizard import Wizard


class ResetSettingsGroup(CheckGroup):
    def __init__(
        self,
        hw: Hardware,
        disable_unboxing: bool,
        erase_projects: bool = False,
        hard_errors: bool = False,
    ):
        checks = [
            ResetHostname(hard_errors=hard_errors),
            ResetAPIKey(hard_errors=hard_errors),
            ResetRemoteConfig(hard_errors=hard_errors),
            ResetHttpDigest(hard_errors=hard_errors),
            ResetWifi(hard_errors=hard_errors),
            ResetTimezone(hard_errors=hard_errors),
            ResetNTP(hard_errors=hard_errors),
            ResetLocale(hard_errors=hard_errors),
            ResetUVCalibrationData(hard_errors=hard_errors),
            RemoveSlicerProfiles(hard_errors=hard_errors),
            ResetHWConfig(hw.config, disable_unboxing=disable_unboxing, hard_errors=hard_errors),
            EraseMCEeprom(hw, hard_errors=hard_errors),
            ResetHomingProfiles(hw, hard_errors=hard_errors),
            DisableAccess(),
        ]
        if erase_projects:
            checks.append(EraseProjects(hard_errors=hard_errors))
        super().__init__(Configuration(None, None), checks)

    async def setup(self, actions: UserActionBroker):
        pass


class SendPrinterDataGroup(CheckGroup):
    def __init__(self, hw: Hardware):
        super().__init__(Configuration(None, None), [SendPrinterData(hw)])

    async def setup(self, actions: UserActionBroker):
        pass


class PackStage1(CheckGroup):
    def __init__(
        self, hw: Hardware, runtime_config: RuntimeConfig, packs_moves: bool = True,
    ):
        checks = [DisableFactory(hw, runtime_config)]
        if packs_moves:
            checks.append(InitiatePackingMoves(hw))
        super().__init__(Configuration(None, None), checks)

    async def setup(self, actions: UserActionBroker):
        pass


class PackStage2(CheckGroup):
    def __init__(self, hw: Hardware):
        super().__init__(Configuration(None, None), [FinishPackingMoves(hw)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.foam_inserted, WizardState.INSERT_FOAM)


class FactoryResetWizard(Wizard):
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        hw: Hardware,
        exposure_image: ExposureImage,
        runtime_config: RuntimeConfig,
        erase_projects: bool = False,
    ):
        super().__init__(
            WizardId.FACTORY_RESET,
            [ResetSettingsGroup(hw, True, erase_projects)],
            hw,
            exposure_image,
            runtime_config,
        )

    def run(self):
        super().run()
        shut_down(self._hw, reboot=True)


class PackingWizard(Wizard):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        groups = [
            SendPrinterDataGroup(hw),
            ResetSettingsGroup(hw, disable_unboxing=False, erase_projects=False, hard_errors=True),
        ]
        if hw.isKit:
            groups.append(PackStage1(hw, runtime_config, False))
        else:
            groups.append(PackStage1(hw, runtime_config, True))
            groups.append(PackStage2(hw))

        super().__init__(WizardId.FACTORY_RESET, groups, hw, exposure_image, runtime_config)

    def run(self):
        super().run()
        shut_down(self._hw)
