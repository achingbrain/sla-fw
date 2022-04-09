# This file is part of the SLA firmware
# Copyright (C) 2020-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.libPrinter import Printer
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.hardware.tests import HardwareTestMenu
from slafw.admin.menus.hardware.display import ExposureDisplayMenu
from slafw.admin.menus.hardware.motion_controller import MotionControllerMenu
from slafw.admin.menus.hardware.tilt_and_tower import TiltAndTowerMenu


class HardwareRoot(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)

        self.add_back()
        self.add_items(
            (
                AdminAction("Exposure display", lambda: self.enter(ExposureDisplayMenu(self._control, printer)), "display_replacement"),
                # TODO separate Tilt and Tower
                AdminAction("Tilt and tower", lambda: self.enter(TiltAndTowerMenu(self._control, printer))),
                AdminAction(
                    "Motion controller",
                    lambda: self.enter(MotionControllerMenu(self._control, printer)),
                    "control_color"
                ),
                AdminAction("Hardware tests", lambda: self.enter(HardwareTestMenu(self._control, printer)), "limit_color"),
            ),
        )
