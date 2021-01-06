# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from abc import abstractmethod

from sl1fw import defines
from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminIntValue, AdminBoolValue, AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Error, Info
from sl1fw.errors.exceptions import ConfigException
from sl1fw.functions.files import get_save_path
from sl1fw.libPrinter import Printer


class SetupMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self.logger = logging.getLogger(__name__)
        self._printer = printer
        self._temp = self._printer.hwConfig.get_writer()
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
            self._printer.hwConfig.write(file_path=config_file)
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
            self._printer.hwConfig.read_file(config_file)
        except ConfigException:
            self._control.enter(Error(self._control, text="Cannot import configuration", pop=1))
            return
        try:
            self._printer.hwConfig.write()
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
        self.add_item(AdminIntValue.from_value("Stirring moves count", self._temp, "stirringDelay", 1))
        self.add_item(AdminIntValue.from_value("Delay after stirring [s]", self._temp, "tiltHeight", 1))
        self.add_item(AdminIntValue.from_value("Power LED intensity", self._temp, "pwrLedPwm", 1))
        self.add_item(AdminIntValue.from_value("MC board version", self._temp, "MCBoardVersion", 1))


class ExposureSetupMenu(SetupMenu):
    def configure_items(self):
        self.add_item(AdminBoolValue.from_value("Blink exposure", self._temp, "blinkExposure"))
        self.add_item(AdminBoolValue.from_value("Per-partes exposure", self._temp, "perPartes"))
        self.add_item(AdminBoolValue.from_value("Use tilt", self._temp, "tilt"))
        self.add_item(AdminBoolValue.from_value("Up&Down UV on", self._temp, "upAndDownUvOn"))

        self.add_item(AdminIntValue.from_value("Layer trigger [s]", self._temp, "trigger", 1))
        self.add_item(AdminIntValue.from_value("Layer tower hop [mm]", self._temp, "layertowerhop", 1))
        self.add_item(AdminIntValue.from_value("Delay before expos. [s]", self._temp, "delaybeforeexposure", 1))
        self.add_item(AdminIntValue.from_value("Delay after expos. [s]", self._temp, "delayafterexposure", 1))
        self.add_item(AdminIntValue.from_value("Up&down wait [s]", self._temp, "upanddownwait", 1))
        self.add_item(AdminIntValue.from_value("Up&down every n-th l.", self._temp, "upanddowneverylayer", 1))
        self.add_item(AdminIntValue.from_value("Up&down Z offset [mm]", self._temp, "upanddownzoffset", 1))
        self.add_item(AdminIntValue.from_value("Up&down expo comp [s]", self._temp, "upanddownexpocomp", 1))
