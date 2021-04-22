# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Iterable

from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardId
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.unboxing import MoveToTank, MoveToFoam
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.setup import Configuration
from sl1fw.wizard.wizard import Wizard


class RemoveSafetyStickerCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware):
        super().__init__(Configuration(None, None), [MoveToFoam(hw)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.safety_sticker_removed, WizardState.REMOVE_SAFETY_STICKER)


class RemoveSideFoamCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware):
        super().__init__(Configuration(None, None), [MoveToTank(hw)])

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
    def __init__(
        self,
        identifier,
        groups: Iterable[CheckGroup],
        hw: Hardware,
        runtime_config: RuntimeConfig,
    ):
        super().__init__(identifier, groups, hw, runtime_config, cancelable=False)

    def run(self):
        super().run()
        if self.state == WizardState.DONE:
            self._logger.info("Unboxing wizard finished without errors, setting show unboxing to false")
            writer = self._hw.config.get_writer()
            writer.showUnboxing = False
            writer.commit()


class CompleteUnboxingWizard(UnboxingWizard):
    def __init__(self, hw: Hardware, runtime_config: RuntimeConfig):
        super().__init__(
            WizardId.COMPLETE_UNBOXING,
            [
                RemoveSafetyStickerCheckGroup(hw),
                RemoveSideFoamCheckGroup(hw),
                RemoveTankFoamCheckGroup(),
                RemoveDisplayFoilCheckGroup(),
            ],
            hw,
            runtime_config,
        )

    @property
    def name(self) -> str:
        return "complete_unboxing"


class KitUnboxingWizard(UnboxingWizard):
    def __init__(self, hw: Hardware, runtime_config: RuntimeConfig):
        super().__init__(
            WizardId.KIT_UNBOXING, [RemoveDisplayFoilCheckGroup()], hw, runtime_config
        )

    @property
    def name(self) -> str:
        return "kit_unboxing"
