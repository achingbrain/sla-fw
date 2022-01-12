# This file is part of the SLA firmware
# Copyright (C) 2020-2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from abc import abstractmethod

from slafw import defines
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminIntValue, AdminBoolValue, AdminAction, AdminFloatValue, AdminFixedValue
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.dialogs import Error, Info
from slafw.errors.errors import ConfigException
from slafw.functions.files import get_save_path, usb_remount
from slafw.libPrinter import Printer


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
            return

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
            return

        self._control.enter(Info(self._control, "Configuration imported"))


class HardwareSetupMenu(SetupMenu):
    def configure_items(self):
        def set_stirring_delay(value):
            self._temp.stirringDelay = int(round(value * 10, ndigits=1))

        def get_stirring_delay():
            return self._temp.stirringDelay / 10

        self.add_items(
            (
                AdminBoolValue.from_value("Fan check", self._temp, "fanCheck"),
                AdminBoolValue.from_value("Cover check", self._temp, "coverCheck"),
                AdminBoolValue.from_value("MC version check", self._temp, "MCversionCheck"),
                AdminBoolValue.from_value("Use resin sensor", self._temp, "resinSensor"),
                AdminBoolValue.from_value("Auto power off", self._temp, "autoOff"),
                AdminBoolValue.from_value("Mute (no beeps)", self._temp, "mute"),
                AdminIntValue.from_value("Screw [mm/rot]", self._temp, "screwMm", 1),
                AdminIntValue.from_value("Tilt msteps", self._temp, "tiltHeight", 1),
                AdminIntValue.from_value("Measuring moves count", self._temp, "measuringMoves", 1),
                AdminIntValue.from_value("Stirring moves count", self._temp, "stirringMoves", 1),
                AdminFloatValue("Delay after stirring [s]", get_stirring_delay, set_stirring_delay, 0.1),
                AdminIntValue.from_value("Power LED intensity", self._temp, "pwrLedPwm", 1),
                AdminIntValue.from_value("MC board version", self._temp, "MCBoardVersion", 1),
            )
        )


class ExposureSetupMenu(SetupMenu):
    def configure_items(self):
        def set_layer_tower_hop(value):
            self._temp.layerTowerHop = self._printer.hw.config.nm_to_tower_microsteps(value)

        def get_layer_tower_hop():
            return self._printer.hw.config.tower_microsteps_to_nm(self._temp.layerTowerHop)

        def set_delay_before_expo(value):
            self._temp.delayBeforeExposure = int(round(value * 10, ndigits=1))

        def get_delay_before_expo():
            return self._temp.delayBeforeExposure / 10

        def set_delay_after_expo(value):
            self._temp.delayafterexposure = int(round(value * 10, ndigits=1))

        def get_delay_after_expo():
            return self._temp.delayafterexposure / 10

        def set_up_and_down_z_offset(value):
            self._temp.upAndDownZoffset = self._printer.hw.config.nm_to_tower_microsteps(value)

        def get_up_and_down_z_offset():
            return self._printer.hw.config.tower_microsteps_to_nm(self._temp.upAndDownZoffset)

        self.add_items(
            (
                AdminBoolValue.from_value("Per-partes exposure", self._temp, "perPartes"),
                AdminBoolValue.from_value("Use tilt", self._temp, "tilt"),
                AdminFixedValue.from_value("Force slow tilt height [mm]", self._temp, "forceSlowTiltHeight", 10000, 6),
                AdminIntValue.from_value("Limit for fast tilt [%]", self._temp, "limit4fast", 1),
                AdminBoolValue.from_value("Up&Down UV on", self._temp, "upAndDownUvOn"),
                AdminFixedValue(
                    "Layer tower hop [mm]",
                    get_layer_tower_hop,
                    set_layer_tower_hop,
                    self._printer.hw.config.tower_microsteps_to_nm(1),
                    6,
                ),
                AdminFloatValue("Delay before expos. [s]", get_delay_before_expo, set_delay_before_expo, 0.1),
                AdminFloatValue("Delay after expos. [s]", get_delay_after_expo, set_delay_after_expo, 0.1),
                AdminIntValue.from_value("Up&down wait [s]", self._temp, "upanddownwait", 1),
                AdminIntValue.from_value("Up&down every n-th l.", self._temp, "upanddowneverylayer", 1),
                AdminFixedValue(
                    "Up&down Z offset [mm]",
                    get_up_and_down_z_offset,
                    set_up_and_down_z_offset,
                    self._printer.hw.config.tower_microsteps_to_nm(1),
                    6,
                ),
                AdminFixedValue.from_value("Up&down expo comp [s]", self._temp, "upAndDownExpoComp", 1, 1),
            )
        )
