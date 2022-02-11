# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction
from slafw.admin.menus.admin_api_test import TestMenu
from slafw.admin.menus.tests.test_errors import TestErrorsMenu, TestWarningsMenu
from slafw.admin.menus.tests.test_hardware import TestHardwareMenu
from slafw.admin.menus.tests.test_wizards import TestWizardsMenu
from slafw.admin.safe_menu import SafeAdminMenu
from slafw.configs.runtime import RuntimeConfig
from slafw.hardware.base import BaseHardware
from slafw.libPrinter import Printer
from slafw.states.wizard import WizardId
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.factory_reset import SendPrinterData
from slafw.wizard.group import CheckGroup
from slafw.wizard.setup import Configuration
from slafw.wizard.wizard import Wizard, WizardDataPackage
from slafw.errors.errors import UnknownPrinterModel


class SendPrinterDataGroup(CheckGroup):
    async def setup(self, actions: UserActionBroker):
        pass

    def __init__(self, hw: BaseHardware):
        super().__init__(Configuration(None, None), (SendPrinterData(hw),))


class SendPrinterDataWizard(Wizard):
    def __init__(self, hw: BaseHardware, runtime_config: RuntimeConfig):
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
                AdminAction("Simulate disconnected display", self.simulate_disconnected_display),
                AdminAction("Wizards", lambda: self.enter(TestWizardsMenu(self._control, self._printer))),
                AdminAction("Hardware", lambda: self.enter(TestHardwareMenu(self._control, self._printer))),
                AdminAction("Admin API test", lambda: self.enter(TestMenu(self._control))),
                AdminAction("Touchscreen test", self._control.touchscreen_test),
                AdminAction("Send wizard data", self.send_printer_data),
            )
        )

    def simulate_disconnected_display(self):
        self._printer.exception_occurred.emit(UnknownPrinterModel())

    @SafeAdminMenu.safe_call
    def send_printer_data(self):
        self._printer.action_manager.start_wizard(SendPrinterDataWizard(self._printer.hw, self._printer.runtime_config))
