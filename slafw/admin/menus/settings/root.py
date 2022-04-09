# This file is part of the SLA firmware
# Copyright (C) 2020-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.libPrinter import Printer
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.settings.fans import FansMenu
from slafw.admin.menus.settings.uvled import UVLedMenu
from slafw.admin.menus.settings.hardware import HardwareSettingsMenu
from slafw.admin.menus.settings.exposure import ExposureSettingsMenu
from slafw.admin.menus.settings.hwconfig import HwConfigMenu
from slafw.admin.menus.dialogs import Confirm, Error, Info
from slafw.functions.system import FactoryMountedRW, get_configured_printer_model
from slafw.errors.errors import ConfigException


class SettingsRoot(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer
        self.add_back()
        self.add_items(
            (
                AdminAction("Fans", lambda: self.enter(FansMenu(self._control, self._printer)), "fan_color"),
                AdminAction("UV LED", lambda: self.enter(UVLedMenu(self._control, self._printer)), "led_set_replacement"),
                AdminAction("Hardware setup", lambda: self.enter(HardwareSettingsMenu(self._control, self._printer)), "firmware-icon"),
                AdminAction("Exposure setup", lambda: self.enter(ExposureSettingsMenu(self._control, self._printer)), "change_color"),
                AdminAction("All config items", lambda: self.enter(HwConfigMenu(self._control, self._printer)), "edit_white"),
                AdminAction("Restore configuration to factory defaults", self.reset_to_defaults, "factory_color"),
                AdminAction("Save configuration as factory defaults", self.save_as_defaults, "save_color"),
            ),
        )

    def reset_to_defaults(self):
        self._control.enter(
            Confirm(self._control, self._do_reset_to_defaults, text="Restore configuration to factory defaults?")
        )

    def _do_reset_to_defaults(self) -> None:
        self.logger.info("Restoring configuration to factory defaults")
        try:
            config = self._printer.hw.config
            config.read_file()
            config.factory_reset()
            config.showUnboxing = False
            config.vatRevision = get_configured_printer_model().options.vat_revision
            self._printer.hw.uv_led.pwm = self._printer.hw.config.uvPwmPrint
            config.write()
        except ConfigException:
            self._control.enter(Error(self._control, text="Save configuration failed", pop=1))
            return
        self._control.enter(Info(self._control, "Configuration restored to default values"))

    def save_as_defaults(self):
        self._control.enter(
            Confirm(self._control, self._do_save_as_defaults, text="Save configuration as factory defaults?")
        )

    def _do_save_as_defaults(self):
        self.logger.info("Saving configuration as factory defaults")
        try:
            self._printer.hw.config.write()
            with FactoryMountedRW():
                self._printer.hw.config.write_factory()
        except ConfigException:
            self._control.enter(Error(self._control, text="Save configuration as defaults failed", pop=1))
            return
        self._control.enter(Info(self._control, "Configuration saved as factory defaults"))
