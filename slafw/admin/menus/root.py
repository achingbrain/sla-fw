# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.display import DisplayRootMenu
from slafw.admin.menus.fans_and_uvled import FansAndUVLedMenu
from slafw.admin.menus.motion_controller import MotionControllerMenu
from slafw.admin.menus.setup import HardwareSetupMenu, ExposureSetupMenu
from slafw.admin.menus.hwconfig import HwConfigMenu
from slafw.admin.menus.logging import LoggingMenu
from slafw.admin.menus.net_update import NetUpdate
from slafw.admin.menus.system_info import SystemInfoMenu
from slafw.admin.menus.system_tools import SystemToolsMenu
from slafw.admin.menus.tests.tests import TestsMenu
from slafw.admin.menus.tilt_and_tower import TiltAndTowerMenu
from slafw.libPrinter import Printer


class RootMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_items(
            (
                AdminAction("<b>Leave admin</b>", self.exit),
                AdminAction("Fans & UV LED", lambda: self.enter(FansAndUVLedMenu(self._control, self._printer))),
                AdminAction("Hardware setup", lambda: self.enter(HardwareSetupMenu(self._control, self._printer))),
                AdminAction("Exposure setup", lambda: self.enter(ExposureSetupMenu(self._control, self._printer))),
                AdminAction("Net update", lambda: self.enter(NetUpdate(self._control, self._printer))),
                AdminAction("hardware.cfg", lambda: self.enter(HwConfigMenu(self._control, self._printer.hw.config))),
                AdminAction("Tests", lambda: self.enter(TestsMenu(self._control, self._printer))),
                AdminAction("Logging", lambda: self.enter(LoggingMenu(self._control, self._printer))),
                AdminAction("System tools", lambda: self.enter(SystemToolsMenu(self._control, self._printer))),
                AdminAction("System information", lambda: self.enter(SystemInfoMenu(self._control, self._printer))),
                AdminAction("Display", lambda: self.enter(DisplayRootMenu(self._control, self._printer))),
                AdminAction(
                    "Motion controller", lambda: self.enter(MotionControllerMenu(self._control, self._printer))
                ),
                AdminAction("Tilt and tower", lambda: self.enter(TiltAndTowerMenu(self._control, self._printer))),
            ),
        )