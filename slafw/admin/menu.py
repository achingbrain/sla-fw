# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from collections import OrderedDict
from typing import Dict, Optional, Iterable

from PySignal import Signal

from slafw.admin.base_menu import AdminMenuBase
from slafw.admin.control import AdminControl
from slafw.admin.items import (
    AdminItem,
    AdminValue,
    AdminAction,
    AdminLabel,
)


class AdminMenu(AdminMenuBase):
    def __init__(self, control: AdminControl):
        self.logger = logging.getLogger(__name__)
        self._control = control
        self.items_changed = Signal()
        self.value_changed = Signal()
        self._items: Dict[str, AdminItem] = OrderedDict()

    @property
    def items(self) -> Dict[str, AdminItem]:
        return self._items

    def enter(self, menu: AdminMenuBase):
        self._control.enter(menu)

    def exit(self):
        self._control.exit()

    def add_item(self, item: AdminItem, emit_changed=True):
        if isinstance(item, AdminValue):
            item.changed.connect(self.value_changed.emit)
        self._items[item.name] = item
        if emit_changed:
            self.items_changed.emit()

    def add_items(self, items: Iterable[AdminItem]):
        for item in items:
            self.add_item(item, emit_changed=False)
        self.items_changed.emit()

    def add_label(self, initial_text: Optional[str] = None):
        label = AdminLabel(initial_text)
        self.add_item(label)
        return label

    def add_back(self, bold=True):
        text = "<b>Back</b>" if bold else "Back"
        self.add_item(AdminAction(text, self._control.pop))

    def del_item(self, item: AdminItem):
        del self._items[item.name]
        self.items_changed.emit()
