# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.unboxing import MoveToTank, MoveToFoam
from sl1fw.wizard.groups.base import CheckGroup
from sl1fw.wizard.setup import Configuration


class RemoveSafetyStickerCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(Configuration(None, None), [MoveToFoam(hw, hw_config)])

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.safety_sticker_removed, WizardState.REMOVE_SAFETY_STICKER)


class RemoveSideFoamCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(Configuration(None, None), [MoveToTank(hw, hw_config)])

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
