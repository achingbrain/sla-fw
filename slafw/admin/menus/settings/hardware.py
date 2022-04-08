# This file is part of the SLA firmware
# Copyright (C) 2020-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.libPrinter import Printer
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminIntValue, AdminBoolValue, AdminFloatValue
from slafw.admin.menus.settings.base import SettingsMenu


class HardwareSettingsMenu(SettingsMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control, printer)
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
                AdminFloatValue("Delay after stirring [s]", self.get_stirring_delay, self.set_stirring_delay, 0.1),
                AdminIntValue.from_value("Power LED intensity", self._temp, "pwrLedPwm", 1),
                AdminIntValue.from_value("MC board version", self._temp, "MCBoardVersion", 1),
            )
        )

    def set_stirring_delay(self, value):
        self._temp.stirringDelay = int(round(value * 10, ndigits=1))

    def get_stirring_delay(self):
        return self._temp.stirringDelay / 10
