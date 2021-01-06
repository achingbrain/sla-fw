# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from collections import OrderedDict
from functools import partial, wraps
from typing import Any, Dict, Iterable, Optional

from PySignal import Signal

from sl1fw.admin.base_menu import AdminMenuBase
from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import (
    AdminItem,
    AdminValue,
    AdminAction,
    AdminItemType,
    AdminIntValue,
    AdminTextValue,
    AdminFloatValue,
    AdminBoolValue, AdminLabel,
)


def part(func, *args, **kwargs):
    """
    None aware partial function

    :param func: Function, can be None
    :param obj: Parameters
    :return: Function with params fixed or None if no input function
    """
    if not func:
        return func

    return partial(func, *args, **kwargs)


class AdminMenu(AdminMenuBase):
    def __init__(self, control: AdminControl):
        self.logger = logging.getLogger(__name__)
        self._control = control
        self.items_changed = Signal()
        self.value_changed = Signal()
        self._items: Dict[str, AdminItem] = OrderedDict()
        self._fill_items()

    @property
    def items(self) -> Iterable[AdminItem]:
        return self._items.values()

    @property
    def values(self) -> Dict[str, Any]:
        return {name: item.get_value() for name, item in self._items.items() if isinstance(item, AdminValue)}

    def enter(self, menu: AdminMenuBase):
        self._control.enter(menu)

    def exit(self):
        self._control.exit()

    def get_item(self, name: str) -> AdminItem:
        return self._items[name]

    def get_value(self, name: str) -> Any:
        item = self.get_item(name)
        if not isinstance(item, AdminValue):
            raise ValueError("Not a value")
        return item.get_value()

    def set_value(self, name: str, value: Any) -> None:
        item = self.get_item(name)
        if not isinstance(item, AdminValue):
            raise ValueError("Not a value")
        item.set_value(value)

    def execute_action(self, name: str):
        item = self.get_item(name)
        if not isinstance(item, AdminAction):
            raise ValueError("Not an action")
        item.execute()

    def add_item(self, item: AdminItem):
        if isinstance(item, AdminValue):
            item.changed.connect(self.value_changed.emit)
        self._items[item.name] = item
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

    def _fill_items(self) -> None:
        for item in vars(type(self)):
            obj = getattr(type(self), item)
            if isinstance(obj, property):
                if not hasattr(obj.fget, "__admin_type__"):
                    continue
                admin_type = getattr(obj.fget, "__admin_type__")
                if not admin_type:
                    continue

                if admin_type == AdminItemType.INT_VALUE:
                    admin_step = getattr(obj.fget, "__admin_step__")
                    value = AdminIntValue(item, part(obj.fget, self), part(obj.fset, self), admin_step)
                elif admin_type == AdminItemType.FLOAT_VALUE:
                    admin_step = getattr(obj.fget, "__admin_step__")
                    value = AdminFloatValue(item, part(obj.fget, self), part(obj.fset, self), admin_step)
                elif admin_type == AdminItemType.BOOL_VALUE:
                    value = AdminBoolValue(item, part(obj.fget, self), part(obj.fset, self))
                elif admin_type == AdminItemType.TEXT_VALUE:
                    value = AdminTextValue(item, part(obj.fget, self), part(obj.fset, self))
                else:
                    raise ValueError("Unknown admin item reached")

                self.add_item(value)

                obj = property(obj.fget, self.wrap_setter(obj.fset, value), obj.fdel, obj.__doc__)
                setattr(type(self), item, obj)

            if callable(obj):
                if not hasattr(obj, "__admin_type__"):
                    continue

                admin_type = getattr(obj, "__admin_type__")

                if admin_type == AdminItemType.ACTION:
                    self.add_item(AdminAction(item, partial(obj, self)))

    def wrap_setter(self, setter, value: AdminValue):
        if not setter:
            return setter

        @wraps(setter)
        def wrap(*args, **kwargs):
            ret = setter(*args, **kwargs)
            self.value_changed.emit()
            value.changed.emit()
            return ret

        return wrap
