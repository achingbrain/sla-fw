# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.admin.items import admin_action, AdminIntValue, AdminFloatValue, AdminBoolValue, admin_text
from sl1fw.admin.control import AdminControl
from sl1fw.admin.menu import AdminMenu, part
from sl1fw.libConfig import HwConfig, IntValue, FloatValue, BoolValue


class HwConfigMenu(AdminMenu):
    NAME_STEP_MAP = {
        "fan1Rpm": 100,
        "fan2Rpm": 100,
        "fan3Rpm": 100,
    }

    def __init__(self, control: AdminControl, config: HwConfig):
        super().__init__(control)
        self._config = config
        self._add_config_items()

    @admin_text
    @property
    def headline(self) -> str:
        return "<h2>HwConfig edit</h2>"

    @admin_text
    @property
    def warning(self) -> str:
        return "Dragons ahead !!! This is unrestricted raw edit of all config values."

    @admin_action
    def back(self):
        self._control.pop()

    @admin_action
    def save(self):
        self._config.write()

    def _add_config_items(self):
        for name, value in self._config.get_values().items():
            if isinstance(value, IntValue):
                step = self.NAME_STEP_MAP.get(name, 1)
                admin_value = AdminIntValue(
                    name, part(value.value_getter, self._config), part(value.value_setter, self._config), step
                )
                self.add_item(admin_value)
            if isinstance(value, FloatValue):
                step = self.NAME_STEP_MAP.get(name, 0.1)
                admin_value = AdminFloatValue(
                    name, part(value.value_getter, self._config), part(value.value_setter, self._config), step
                )
                self.add_item(admin_value)
            if isinstance(value, BoolValue):
                admin_value = AdminBoolValue(
                    name, part(value.value_getter, self._config), part(value.value_setter, self._config)
                )
                self.add_item(admin_value)
