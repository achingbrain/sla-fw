# This file is part of the SLA firmware
# Copyright (C) 2020-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.libPrinter import Printer
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.settings.root import SettingsRoot
from slafw.admin.menus.hardware.root import HardwareRoot
from slafw.admin.menus.firmware.root import FirmwareRoot


class RootMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)

        self.add_items(
            (
                AdminAction("<b>Leave admin</b>", self.exit),
                AdminAction("Settings", lambda: self.enter(SettingsRoot(self._control, printer))),
                AdminAction("Hardware", lambda: self.enter(HardwareRoot(self._control, printer))),
                AdminAction("Firmware", lambda: self.enter(FirmwareRoot(self._control, printer))),
            ),
        )
