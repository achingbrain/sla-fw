# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Iterable

from slafw.configs.runtime import RuntimeConfig
from slafw.hardware.base.hardware import BaseHardware
from slafw.states.wizard import WizardId
from slafw.states.wizard import WizardState
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.unboxing import MoveToTank, MoveToFoam
from slafw.wizard.group import CheckGroup
from slafw.wizard.setup import Configuration
from slafw.wizard.wizard import Wizard, WizardDataPackage
from slafw.wizard.wizards.generic import ShowResultsGroup


class RemoveSafetyStickerCheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(Configuration(None, None), [MoveToFoam(package.hw)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.safety_sticker_removed, WizardState.REMOVE_SAFETY_STICKER)


class RemoveSideFoamCheckGroup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(Configuration(None, None), [MoveToTank(package.hw)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.side_foam_removed, WizardState.REMOVE_SIDE_FOAM)


class RemoveTankFoamCheckGroup(CheckGroup):
    def __init__(self):
        super().__init__(Configuration(None, None), [])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.tank_foam_removed, WizardState.REMOVE_TANK_FOAM)


class RemoveDisplayFoilCheckGroup(CheckGroup):
    def __init__(self):
        super().__init__(Configuration(None, None), [])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.display_foil_removed, WizardState.REMOVE_DISPLAY_FOIL)


class UnboxingWizard(Wizard):
    # pylint: disable = too-many-arguments
    def __init__(self, identifier, groups: Iterable[CheckGroup], package: WizardDataPackage):
        self._package = package
        super().__init__(identifier, groups, self._package, cancelable=False)

    def wizard_finished(self):
        self._package.config_writer.showUnboxing = False


class CompleteUnboxingWizard(UnboxingWizard):
    def __init__(self, hw: BaseHardware, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(hw=hw, config_writer=hw.config.get_writer(), runtime_config=runtime_config)
        super().__init__(
            WizardId.COMPLETE_UNBOXING,
            [
                RemoveSafetyStickerCheckGroup(self._package),
                RemoveSideFoamCheckGroup(self._package),
                RemoveTankFoamCheckGroup(),
                RemoveDisplayFoilCheckGroup(),
                ShowResultsGroup(),
            ],
            self._package,
        )

    @classmethod
    def get_name(cls) -> str:
        return "complete_unboxing"


class KitUnboxingWizard(UnboxingWizard):
    def __init__(self, hw: BaseHardware, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(hw=hw, config_writer=hw.config.get_writer(), runtime_config=runtime_config)
        super().__init__(WizardId.KIT_UNBOXING, [RemoveDisplayFoilCheckGroup(), ShowResultsGroup()], self._package)

    @classmethod
    def get_name(cls) -> str:
        return "kit_unboxing"
