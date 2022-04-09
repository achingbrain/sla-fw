# This file is part of the SLA firmware
# Copyright (C) 2020-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.libPrinter import Printer
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminIntValue, AdminBoolValue
from slafw.admin.menus.settings.base import SettingsMenu

from slafw.hardware.base.fan import FanState


class FansMenu(SettingsMenu):

    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control, printer)
        self._printer = printer

        self._init_uv_led_fan = FanState(self._printer.hw.uv_led_fan)
        self._init_blower_fan = FanState(self._printer.hw.blower_fan)
        self._init_rear_fan = FanState(self._printer.hw.rear_fan)

        uv_led_fan_rpm_item = AdminIntValue.from_value("UV LED fan RPM", self._temp, "fan1Rpm", 100, "limit_color")
        uv_led_fan_rpm_item.changed.connect(self._uv_led_fan_changed)
        blower_fan_rpm_item = AdminIntValue.from_value("Blower fan RPM", self._temp, "fan2Rpm", 100, "limit_color")
        blower_fan_rpm_item.changed.connect(self._blower_fan_changed)
        rear_fan_rpm_item = AdminBoolValue.from_value("Rear fan", self, "rear_fan", "fan_color")
        rear_fan_rpm_item.changed.connect(self._rear_fan_changed)

        self.add_items(
            (
                AdminBoolValue.from_value("UV LED fan", self, "uv_led_fan", "fan_color"),
                uv_led_fan_rpm_item,
                AdminBoolValue.from_value("Blower fan", self, "blower_fan", "fan_color"),
                blower_fan_rpm_item,
                rear_fan_rpm_item,
                AdminIntValue.from_value("Rear fan RPM", self._temp, "fan3Rpm", 100, "limit_color"),
            )
        )

    def on_leave(self):
        self._init_uv_led_fan.restore()
        self._init_blower_fan.restore()
        self._init_rear_fan.restore()

    @property
    def uv_led_fan(self) -> bool:
        return self._printer.hw.uv_led_fan.enabled

    @uv_led_fan.setter
    def uv_led_fan(self, value: bool):
        self._printer.hw.uv_led_fan.enabled = value

    @property
    def blower_fan(self) -> bool:
        return self._printer.hw.blower_fan.enabled

    @blower_fan.setter
    def blower_fan(self, value: bool):
        self._printer.hw.blower_fan.enabled = value

    @property
    def rear_fan(self) -> bool:
        return self._printer.hw.rear_fan.enabled

    @rear_fan.setter
    def rear_fan(self, value: bool):
        self._printer.hw.rear_fan.enabled = value

    @property
    def uv_led(self) -> bool:
        return self._printer.hw.uv_led.active

    def _uv_led_fan_changed(self):
        self.uv_led_fan = True
        self._printer.hw.fans[0].target_rpm = self._temp.fan1Rpm

    def _blower_fan_changed(self):
        self.blower_fan = True
        self._printer.hw.fans[1].target_rpm = self._temp.fan2Rpm

    def _rear_fan_changed(self):
        self.rear_fan = True
        self._printer.hw.fans[2].target_rpm = self._temp.fan3Rpm
