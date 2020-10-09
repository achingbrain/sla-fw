# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.fans_and_uvled import FansAndUVLedMenu
from sl1fw.admin.menus.hardware_setup import HardwareSetupMenu
from sl1fw.admin.menus.hwconfig import HwConfigMenu
from sl1fw.admin.menus.net_update import NetUpdate
from sl1fw.admin.menus.test import TestMenu
from sl1fw.libPrinter import Printer


class RootMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_item(AdminAction("Leave admin", self.exit))
        self.add_item(AdminAction("Fans & UV LED", lambda: self.enter(FansAndUVLedMenu(self._control, self._printer))))
        self.add_item(
            AdminAction("Hardware setup", lambda: self.enter(HardwareSetupMenu(self._control, self._printer)))
        )
        self.add_item(AdminAction("Net update", lambda: self.enter(NetUpdate(self._control, self._printer))))
        self.add_item(
            AdminAction("hardware.cfg", lambda: self.enter(HwConfigMenu(self._control, self._printer.hwConfig)))
        )

        self.add_item(AdminAction("admin api test", lambda: self.enter(TestMenu(self._control))))
