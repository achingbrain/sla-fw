# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminIntValue, AdminFloatValue, AdminBoolValue, AdminAction
from sl1fw.admin.menu import AdminMenu, part
from sl1fw.admin.menus.dialogs import Info
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
        self._headline = self.add_label("<h2>HwConfig edit</h2>")
        self._warning = self.add_label("Dragons ahead !!! This is unrestricted raw edit of all config values.")
        self.add_back()
        self.add_item(AdminAction("Save", self.save))
        self._add_config_items()

    def save(self):
        self._config.write()
        self._control.enter(Info(self._control, "hardware.cfg saved"))

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
