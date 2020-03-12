# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import pydbus

from sl1fw.functions.system import save_factory_mode
from sl1fw.pages import page
from sl1fw.pages.base import Page

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageTools(Page):
    Name = "tools"

    SYSTEMD_DBUS = ".systemd1"
    SSH_SERVICE = "sshd.socket"
    SERIAL_SERVICE = "serial-getty@ttyS0.service"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "admin"
        self.serial_enabled = False
        self.ssh_enabled = False
        self.systemd = None

    def show(self):
        self.systemd = pydbus.SystemBus().get(self.SYSTEMD_DBUS)
        self.ssh_enabled = self.systemd.GetUnitFileState(self.SSH_SERVICE) == "enabled"
        self.serial_enabled = self.systemd.GetUnitFileState(self.SERIAL_SERVICE) == "enabled"
        self.items.update(
            {
                "button1": "Disable factory mode"
                if self.display.runtime_config.factory_mode
                else "Enable Factory mode",
                "button2": "Disable ssh" if self.ssh_enabled else "Enable ssh",
                "button3": "Disable serial" if self.serial_enabled else "Enable serial",
            }
        )
        super().show()

    def button1ButtonRelease(self):
        if self.writeToFactory(functools.partial(save_factory_mode, not self.display.runtime_config.factory_mode)):
            self.display.runtime_config.factory_mode = not self.display.runtime_config.factory_mode
        return "_SELF_"

    def button2ButtonRelease(self):
        self._trigger_unit(self.SSH_SERVICE)
        return "_SELF_"

    def button3ButtonRelease(self):
        self._trigger_unit(self.SERIAL_SERVICE)
        return "_SELF_"

    def _trigger_unit(self, name: str):
        state = self.systemd.GetUnitFileState(name)
        if state == "enabled":
            self.systemd.StopUnit(name, "replace")
            self.systemd.DisableUnitFiles([name], False)
        else:
            if state == "masked":
                self.systemd.UnmaskUnitFiles([name], False)
                self.systemd.Reload()
            self.systemd.EnableUnitFiles([name], False, False)
            self.systemd.StartUnit(name, "replace")
