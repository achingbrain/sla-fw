# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardId
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.display import RecordExpoPanelLog
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.setup import Configuration
from sl1fw.wizard.wizard import Wizard, WizardDataPackage


class NewExpoPanelCheckGroup(CheckGroup):
    def __init__(self, hw: Hardware):
        super().__init__(Configuration(None, None), (RecordExpoPanelLog(hw),))

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.new_expo_panel_done, WizardState.PREPARE_NEW_EXPO_PANEL)


class NewExpoPanelWizard(Wizard):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardId.NEW_EXPO_PANEL,
            (NewExpoPanelCheckGroup(hw),),
            WizardDataPackage(hw),
            cancelable=False)
