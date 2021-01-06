# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.admin_api_test import TestMenu
from sl1fw.admin.menus.tests.test_error_types import TestErrorTypesMenu
from sl1fw.admin.menus.tests.test_errors import TestErrorsMenu

from sl1fw.admin.menus.tests.test_hardware import TestHardwareMenu
from sl1fw.admin.menus.tests.test_wizards import TestWizardsMenu
from sl1fw.libPrinter import Printer


class TestsMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self.logger = logging.getLogger(__name__)
        self._printer = printer

        self.add_item(AdminAction("Back", self._control.pop))
        self.add_item(AdminAction("Error types", lambda: self.enter(TestErrorTypesMenu(self._control, self._printer))))
        self.add_item(AdminAction("Errors", lambda: self.enter(TestErrorsMenu(self._control, self._printer))))
        self.add_item(AdminAction("Wizards", lambda: self.enter(TestWizardsMenu(self._control, self._printer))))
        self.add_item(AdminAction("Hardware", lambda: self.enter(TestHardwareMenu(self._control, self._printer))))
        self.add_item(AdminAction("Admin API test", lambda: self.enter(TestMenu(self._control))))
        self.add_item(AdminAction("Touchscreen test", self._control.touchscreen_test))
