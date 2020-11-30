# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.test_errors import TestErrors
from sl1fw.libPrinter import Printer


class TestsMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self.logger = logging.getLogger(__name__)
        self._printer = printer

        self.add_item(AdminAction("Test Errors", lambda: self.enter(TestErrors(self._control, self._printer))))
        self.add_item(AdminAction("Back", self._control.pop))
