# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import pydbus

from sl1fw import defines
from sl1fw.errors.errors import FailedUpdateChannelGet, FailedUpdateChannelSet
from sl1fw.errors.exceptions import ConfigException
from sl1fw.functions.system import save_factory_mode, get_update_channel, set_update_channel, FactoryMountedRW
from sl1fw.pages import page
from sl1fw.pages.base import Page

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageTools(Page):
    Name = "tools"

    SYSTEMD_DBUS = ".systemd1"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "admin"
        self.serial_enabled = False
        self.ssh_enabled = False
        self.systemd = None

    def show(self):
        self.systemd = pydbus.SystemBus().get(self.SYSTEMD_DBUS)
        self.ssh_enabled = defines.ssh_service_enabled.exists()
        self.serial_enabled = defines.serial_service_enabled.exists()

        try:
            channel = get_update_channel()
        except FailedUpdateChannelGet:
            channel = ""

        self.items.update(
            {
                "button1": "Disable factory mode"
                if self.display.runtime_config.factory_mode
                else "Enable Factory mode",
                "button2": self._ssh_text,
                "button3": self._serial_text,
                "button5": "Fake printer setup",
                "button11": f"Switch to stable{'*' if channel == 'stable' else ''}",
                "button12": f"Switch to beta{'*' if channel == 'beta' else ''}",
                "button13": f"Switch to dev{'*' if channel == 'dev' else ''}",
            }
        )
        super().show()

    @property
    def _ssh_text(self) -> str:
        if self.display.runtime_config.factory_mode:
            return "#Factory on#"
        if self.ssh_enabled:
            return "Disable ssh"
        return "Enable ssh"

    @property
    def _serial_text(self) -> str:
        if self.display.runtime_config.factory_mode:
            return "#Factory on#"
        if self.serial_enabled:
            return "Disable serial"
        return "Enable serial"

    def button1ButtonRelease(self):
        with FactoryMountedRW():
            save_factory_mode(not self.display.runtime_config.factory_mode)
            if self.display.runtime_config.factory_mode:
                if defines.factory_enable.exists():
                    defines.factory_enable.unlink()
                # On factory disable, disable also ssh and serial to ensure
                # end users do not end up with serial, ssh enabled.
                if defines.ssh_service_enabled.exists():
                    defines.ssh_service_enabled.unlink()
                if defines.serial_service_enabled.exists():
                    defines.serial_service_enabled.unlink()
            else:
                defines.factory_enable.touch()
        self.display.runtime_config.factory_mode = not self.display.runtime_config.factory_mode
        if self.display.runtime_config.factory_mode:
            self.systemd.Reload()
            self._systemd_enable_service(defines.serial_service_service)
            self._systemd_enable_service(defines.ssh_service_service)

        return "_SELF_"

    def button2ButtonRelease(self):
        if not self.display.runtime_config.factory_mode:
            self._trigger_unit(defines.ssh_service_service, defines.ssh_service_enabled)
        return "_SELF_"

    def button3ButtonRelease(self):
        if not self.display.runtime_config.factory_mode:
            self._trigger_unit(defines.serial_service_service, defines.serial_service_enabled)
        return "_SELF_"

    def button5ButtonRelease(self):
        pageWait = self.display.makeWait(self.display, line1="Downloading examples")
        pageWait.show()
        if not self.downloadExamlpes():
            self.display.pages['error'].setParams(
                text="Examples fetch failed")
            return "error"
        pageWait.showItems(line1="Saving dummy calibration data")
        writer = self.display.hwConfig.get_writer()
        writer.calibrated = True
        writer.showWizard = False
        writer.showUnboxing = False
        writer.uvPwm = self.display.hw.getMinPwm()
        self.display.hw.uvLedPwm = writer.uvPwm
        try:
            writer.commit()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text="Cannot save configuration")
            return "error"

        if not self.writeToFactory(self.saveDefaultsFile):
            self.display.pages['error'].setParams(
                text = "!!! Failed to save factory defaults !!!")
            return "error"
        #else

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

    def _trigger_unit(self, service: str, enable_file: Path):
        if enable_file.exists():
            with FactoryMountedRW():
                enable_file.unlink()
            self._systemd_disable_service(service)
        else:
            with FactoryMountedRW():
                enable_file.touch()
            self._systemd_enable_service(service)

    def _systemd_enable_service(self, service: str):
        state = self.systemd.GetUnitFileState(service)
        if state == "masked":
            self.systemd.UnmaskUnitFiles([service], False)
        self.systemd.Reload()
        self.systemd.StartUnit(service, "replace")

    def _systemd_disable_service(self, service: str):
        self.systemd.Reload()
        self.systemd.StopUnit(service, "replace")
