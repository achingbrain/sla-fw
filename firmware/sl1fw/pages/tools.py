# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Optional

import pydbus

from sl1fw.errors.errors import FailedUpdateChannelGet, FailedUpdateChannelSet
from sl1fw.functions.system import save_factory_mode, get_update_channel, set_update_channel
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

        try:
            channel = get_update_channel()
        except FailedUpdateChannelGet:
            channel = ""

        self.items.update(
            {
                "button1": "Disable factory mode"
                if self.display.runtime_config.factory_mode
                else "Enable Factory mode",
                "button2": "Disable ssh" if self.ssh_enabled else "Enable ssh",
                "button3": "Disable serial" if self.serial_enabled else "Enable serial",
                "button11": f"Switch to stable{'*' if channel == 'stable' else ''}",
                "button12": f"Switch to beta{'*' if channel == 'beta' else ''}",
                "button13": f"Switch to dev{'*' if channel == 'dev' else ''}",
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

    def button11ButtonRelease(self):
        return self._switch_channel("stable")

    def button12ButtonRelease(self):
        return self._switch_channel("beta")

    def button13ButtonRelease(self):
        return self._switch_channel("dev")

    def _switch_channel(self, channel: str) -> Optional[str]:
        try:
            set_update_channel(channel)
        except FailedUpdateChannelSet:
            self.logger.exception("Failed to set update channel")
            self.display.pages["error"].setParams(text="Cannot set update channel")
            return "error"
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
