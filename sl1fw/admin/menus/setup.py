# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from abc import abstractmethod

from sl1fw import defines
from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminIntValue, AdminBoolValue, AdminAction, AdminFloatValue
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Error, Info
from sl1fw.errors.exceptions import ConfigException
from sl1fw.functions.files import get_save_path, usb_remount
from sl1fw.libPrinter import Printer


class SetupMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self.logger = logging.getLogger(__name__)
        self._printer = printer
        self._temp = self._printer.hw.config.get_writer()
        self.add_back()
        self.configure_items()
        self.add_item(AdminAction("save", self.save))
        self.add_item(AdminAction("export", self.export_config))
        self.add_item(AdminAction("import", self.import_config))

    @abstractmethod
    def configure_items(self):
        ...

    def save(self):
        self._temp.commit()
        self._control.enter(Info(self._control, "Configuration saved"))

    def export_config(self):
        save_path = get_save_path()
        if save_path is None:
            self._control.enter(Error(self._control, text="No USB storage present", pop=1))
            return

        config_file = save_path / defines.hwConfigFileName

        try:
            usb_remount(config_file)
            self._printer.hw.config.write(file_path=config_file)
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self._control.enter(Error(self._control, text="Cannot save configuration", pop=1))
        self._control.enter(Info(self._control, "Configuration exported"))

    def import_config(self):
        save_path = get_save_path()
        if save_path is None:
            self._control.enter(Error(self._control, text="No USB storage present", pop=1))
            return

        config_file = save_path / defines.hwConfigFileName

        if not config_file.is_file():
            self._control.enter(Error(self._control, text="Cannot find configuration to import", pop=1))
            return

        try:
            self._printer.hw.config.read_file(config_file)
        except ConfigException:
            self._control.enter(Error(self._control, text="Cannot import configuration", pop=1))
            return
        try:
            self._printer.hw.config.write()
        except ConfigException:
            self._control.enter(Error(self._control, text="Cannot save configuration", pop=1))
        self._control.enter(Info(self._control, "Configuration imported"))


class HardwareSetupMenu(SetupMenu):
    def configure_items(self):
        self.add_item(AdminBoolValue.from_value("Fan check", self._temp, "fanCheck"))
        self.add_item(AdminBoolValue.from_value("Cover check", self._temp, "coverCheck"))
        self.add_item(AdminBoolValue.from_value("MC version check", self._temp, "MCversionCheck"))
        self.add_item(AdminBoolValue.from_value("Use resin sensor", self._temp, "resinSensor"))
        self.add_item(AdminBoolValue.from_value("Auto power off", self._temp, "autoOff"))
        self.add_item(AdminBoolValue.from_value("Mute (no beeps)", self._temp, "mute"))

        self.add_item(AdminIntValue.from_value("Screw [mm/rot]", self._temp, "screwMm", 1))
        self.add_item(AdminIntValue.from_value("Tilt msteps", self._temp, "tiltHeight", 1))
        self.add_item(AdminIntValue.from_value("Measuring moves count", self._temp, "measuringMoves", 1))
        self.add_item(AdminIntValue.from_value("Stirring moves count", self._temp, "stirringMoves", 1))

        def set_stirring_delay(value):
            self._temp.stirringDelay = int(round(value * 10, ndigits=1))

        def get_stirring_delay():
            return self._temp.stirringDelay / 10

        self.add_item(AdminFloatValue("Delay after stirring [s]", get_stirring_delay, set_stirring_delay, 0.1))
        self.add_item(AdminIntValue.from_value("Power LED intensity", self._temp, "pwrLedPwm", 1))
        self.add_item(AdminIntValue.from_value("MC board version", self._temp, "MCBoardVersion", 1))


class ExposureSetupMenu(SetupMenu):
    def configure_items(self):
        self.add_item(AdminBoolValue.from_value("Blink exposure", self._temp, "blinkExposure"))
        self.add_item(AdminBoolValue.from_value("Per-partes exposure", self._temp, "perPartes"))
        self.add_item(AdminBoolValue.from_value("Use tilt", self._temp, "tilt"))
        self.add_item(AdminBoolValue.from_value("Up&Down UV on", self._temp, "upAndDownUvOn"))

        self.add_item(AdminIntValue.from_value("Layer trigger [s]", self._temp, "trigger", 1))

        def set_layer_tower_hop(value):
            self._temp.layerTowerHop = int(self._printer.hw.config.nm_to_tower_microsteps(value * 1000))

        def get_layer_tower_hop():
            return self._printer.hw.config.tower_microsteps_to_nm(self._temp.layerTowerHop) / 1000

        self.add_item(AdminIntValue("Layer tower hop [μm]", get_layer_tower_hop, set_layer_tower_hop, 100))

        def set_delay_before_expo(value):
            self._temp.delayBeforeExposure = int(round(value * 10, ndigits=1))

        def get_delay_before_expo():
            return self._temp.delayBeforeExposure / 10

        self.add_item(AdminFloatValue("Delay before expos. [s]", get_delay_before_expo, set_delay_before_expo, 0.1))

        def set_delay_after_expo(value):
            self._temp.delayafterexposure = int(round(value * 10, ndigits=1))

        def get_delay_after_expo():
            return self._temp.delayafterexposure / 10

        self.add_item(AdminFloatValue("Delay after expos. [s]", get_delay_after_expo, set_delay_after_expo, 0.1))

        self.add_item(AdminIntValue.from_value("Up&down wait [s]", self._temp, "upanddownwait", 1))
        self.add_item(AdminIntValue.from_value("Up&down every n-th l.", self._temp, "upanddowneverylayer", 1))

        def set_up_and_down_z_offset(value):
            self._temp.upAndDownZoffset = int(self._printer.hw.config.nm_to_tower_microsteps(value * 1000))

        def get_up_and_down_z_offset():
            return self._printer.hw.config.tower_microsteps_to_nm(self._temp.upAndDownZoffset) / 1000

        self.add_item(AdminIntValue("Up&down Z offset [μm]", get_up_and_down_z_offset, set_up_and_down_z_offset, 10))

        def set_up_and_down_expo_comp(value):
            self._temp.upAndDownExpoComp = int(round(value / 100))

        def get_up_and_down_expo_comp():
            return self._temp.upAndDownExpoComp * 100

        self.add_item(
            AdminIntValue("Up&down expo comp [ms]", get_up_and_down_expo_comp, set_up_and_down_expo_comp, 100)
        )
