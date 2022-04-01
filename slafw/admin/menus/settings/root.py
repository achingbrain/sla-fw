# This file is part of the SLA firmware
# Copyright (C) 2020-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.libPrinter import Printer
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.settings.fans_and_uvled import FansAndUVLedMenu
from slafw.admin.menus.settings.setup import HardwareSetupMenu, ExposureSetupMenu
from slafw.admin.menus.settings.hwconfig import HwConfigMenu


class SettingsRoot(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_items(
            (
                AdminAction("Fans & UV LED", lambda: self.enter(FansAndUVLedMenu(self._control, self._printer))),
                AdminAction("Hardware setup", lambda: self.enter(HardwareSetupMenu(self._control, self._printer))),
                AdminAction("Exposure setup", lambda: self.enter(ExposureSetupMenu(self._control, self._printer))),
                AdminAction("hardware.cfg", lambda: self.enter(HwConfigMenu(self._control, self._printer.hw.config))),
            ),
        )
