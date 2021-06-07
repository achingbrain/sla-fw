# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menus.admin_api_test import TestMenu
from sl1fw.admin.menus.tests.test_errors import TestErrorsMenu, TestWarningsMenu
from sl1fw.admin.menus.tests.test_hardware import TestHardwareMenu
from sl1fw.admin.menus.tests.test_wizards import TestWizardsMenu
from sl1fw.admin.safe_menu import SafeAdminMenu
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.libPrinter import Printer
from sl1fw.states.wizard import WizardId
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.factory_reset import SendPrinterData
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.setup import Configuration
from sl1fw.wizard.wizard import Wizard, WizardDataPackage


class SendPrinterDataGroup(CheckGroup):
    async def setup(self, actions: UserActionBroker):
        pass

    def __init__(self, hw: Hardware):
        super().__init__(Configuration(None, None), (SendPrinterData(hw),))


class SendPrinterDataWizard(Wizard):
    def __init__(self, hw: Hardware, runtime_config: RuntimeConfig):
        super().__init__(
            WizardId.PACKING,
            (SendPrinterDataGroup(hw),),
            WizardDataPackage(hw, hw.config.get_writer(), runtime_config),
        )


class TestsMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self.logger = logging.getLogger(__name__)
        self._printer = printer

        self.add_back()
        self.add_items(
            (
                AdminAction("Errors", lambda: self.enter(TestErrorsMenu(self._control, self._printer))),
                AdminAction("Warnings", lambda: self.enter(TestWarningsMenu(self._control, self._printer))),
                AdminAction("Wizards", lambda: self.enter(TestWizardsMenu(self._control, self._printer))),
                AdminAction("Hardware", lambda: self.enter(TestHardwareMenu(self._control, self._printer))),
                AdminAction("Admin API test", lambda: self.enter(TestMenu(self._control))),
                AdminAction("Touchscreen test", self._control.touchscreen_test),
                AdminAction("Send wizard data", self.send_printer_data),
            )
        )

    @SafeAdminMenu.safe_call
    def send_printer_data(self):
        self._printer.action_manager.start_wizard(SendPrinterDataWizard(self._printer.hw, self._printer.runtime_config))
