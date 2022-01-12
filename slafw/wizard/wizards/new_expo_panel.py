# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.libHardware import Hardware
from slafw.states.wizard import WizardId
from slafw.states.wizard import WizardState
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.display import RecordExpoPanelLog
from slafw.wizard.group import CheckGroup
from slafw.wizard.setup import Configuration
from slafw.wizard.wizard import Wizard, WizardDataPackage


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
