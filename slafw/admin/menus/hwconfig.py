# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Collection

from slafw.admin.control import AdminControl
from slafw.admin.items import AdminIntValue, AdminFloatValue, AdminBoolValue, AdminAction, AdminItem
from slafw.admin.menu import AdminMenu, part
from slafw.admin.menus.dialogs import Info
from slafw.configs.hw import HwConfig
from slafw.configs.value import IntValue, FloatValue, BoolValue


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
        self.add_items(self._get_config_items())

    def save(self):
        self._config.write()
        self._control.enter(Info(self._control, "hardware.cfg saved"))

    def _get_config_items(self) -> Collection[AdminItem]:
        for name, value in self._config.get_values().items():
            if isinstance(value, IntValue):
                step = self.NAME_STEP_MAP.get(name, 1)
                yield AdminIntValue(
                    name, part(value.value_getter, self._config), part(value.value_setter, self._config), step
                )
            if isinstance(value, FloatValue):
                step = self.NAME_STEP_MAP.get(name, 0.1)
                yield AdminFloatValue(
                    name, part(value.value_getter, self._config), part(value.value_setter, self._config), step
                )
            if isinstance(value, BoolValue):
                yield AdminBoolValue(
                    name, part(value.value_getter, self._config), part(value.value_setter, self._config)
                )
