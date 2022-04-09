# This file is part of the SLA firmware
# Copyright (C) 2020-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.libPrinter import Printer
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminIntValue, AdminBoolValue, AdminFloatValue, AdminFixedValue
from slafw.admin.menus.settings.base import SettingsMenu


class ExposureSettingsMenu(SettingsMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control, printer)
        self.add_items(
            (
                AdminBoolValue.from_value("Per-partes exposure", self._temp, "perPartes", "display_test_color"),
                AdminBoolValue.from_value("Use tilt", self._temp, "tilt", "tank_reset_color"),
                AdminFixedValue.from_value("Force slow tilt height [mm]", self._temp, "forceSlowTiltHeight", 10000, 6, "move_resin_tank_color"),
                AdminIntValue.from_value("Limit for fast tilt [%]", self._temp, "limit4fast", 1, "limit_color"),
                AdminBoolValue.from_value("Up&Down UV on", self._temp, "upAndDownUvOn", "tower_offset_color"),
                AdminFixedValue.from_value("Layer tower hop [mm]", self._temp, "layer_tower_hop_nm", 1, 6, "calibration_color"),
                AdminFloatValue("Delay before expos. [s]", self.get_delay_before_expo, self.set_delay_before_expo, 0.1, "exposure_times_color"),
                AdminFloatValue("Delay after expos. [s]", self.get_delay_after_expo, self.set_delay_after_expo, 0.1, "exposure_times_color"),
                AdminIntValue.from_value("Up&down wait [s]", self._temp, "upanddownwait", 1, "exposure_times_color"),
                AdminIntValue.from_value("Up&down every n-th l.", self._temp, "upanddowneverylayer", 1, "tower_offset_color"),
                AdminFixedValue.from_value("Up&down Z offset [mm]", self._temp, "up_and_down_z_offset_nm", 1, 6, "calibration_color"),
                AdminFixedValue.from_value("Up&down expo comp [s]", self._temp, "upAndDownExpoComp", 1, 1, "exposure_times_color"),
            )
        )

    def set_delay_before_expo(self, value):
        self._temp.delayBeforeExposure = int(round(value * 10, ndigits=1))

    def get_delay_before_expo(self):
        return self._temp.delayBeforeExposure / 10

    def set_delay_after_expo(self, value):
        self._temp.delayafterexposure = int(round(value * 10, ndigits=1))

    def get_delay_after_expo(self):
        return self._temp.delayafterexposure / 10
