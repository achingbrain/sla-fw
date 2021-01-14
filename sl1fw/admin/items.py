# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from functools import partial, wraps
from typing import Callable, Any, Optional

from PySignal import Signal


class AdminItem:
    # pylint: disable=too-few-public-methods
    def __init__(self, name: str):
        self.name = name


class AdminAction(AdminItem):
    # pylint: disable=too-few-public-methods
    def __init__(self, name: str, action: Callable):
        super().__init__(name)
        self._action = action

    def execute(self):
        self._action()


class AdminValue(AdminItem):
    def __init__(self, name: str, getter: Callable, setter: Callable):
        super().__init__(name)
        self._getter = getter
        self._setter = setter
        self.changed = Signal()

    def get_value(self) -> Any:
        return self._getter()

    def set_value(self, value: Any) -> None:
        self._setter(value)
        self.changed.emit()

    def wrap_setter(self, setter: Callable[[Any], None]):
        if not setter:
            return setter

        @wraps(setter)
        def wrap(*args, **kwargs):
            ret = setter(*args, **kwargs)
            self.changed.emit()
            return ret

        return wrap

    @classmethod
    def _get_prop_name(cls, obj: object, prop: property):
        for name in dir(type(obj)):
            if getattr(type(obj), name) == prop:
                return name
        raise ValueError("Failed to map value to property")

    @classmethod
    def _map_prop(cls, obj: object, prop: property, value: AdminValue, prop_name: str):
        new_prop = property(prop.fget, value.wrap_setter(prop.fset), prop.fdel, prop.__doc__)
        setattr(type(obj), prop_name, new_prop)


class AdminIntValue(AdminValue):
    def __init__(self, name: str, getter: Callable, setter: Callable, step: int):
        super().__init__(name, getter, setter)
        self._step = step

    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, step: int) -> AdminIntValue:
        return AdminIntValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop), step)

    @classmethod
    def from_property(cls, obj: object, prop: property, step: int) -> AdminIntValue:
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminIntValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj), step)
        cls._map_prop(obj, prop, value, prop_name)
        return value

    @property
    def step(self) -> int:
        return self._step


class AdminFloatValue(AdminValue):
    def __init__(self, name: str, getter: Callable, setter: Callable, step: float):
        super().__init__(name, getter, setter)
        self._step = step

    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, step: float) -> AdminFloatValue:
        return AdminFloatValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop), step)

    @classmethod
    def from_property(cls, obj: object, prop: property, step: float) -> AdminFloatValue:
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminFloatValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj), step)
        cls._map_prop(obj, prop, value, prop_name)
        return value

    @property
    def step(self) -> float:
        return self._step


class AdminBoolValue(AdminValue):
    @classmethod
    def from_value(cls, name: str, obj: object, prop: str) -> AdminBoolValue:
        return AdminBoolValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop))

    @classmethod
    def from_property(cls, obj: object, prop: property) -> AdminBoolValue:
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminBoolValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj))
        cls._map_prop(obj, prop, value, prop_name)
        return value


class AdminTextValue(AdminValue):
    @classmethod
    def from_value(cls, name: str, obj: object, prop: str):
        return AdminTextValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop))

    @classmethod
    def from_property(cls, obj: object, prop: property):
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminTextValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj))
        cls._map_prop(obj, prop, value, prop_name)
        return value


class AdminLabel(AdminTextValue):
    INSTANCE_COUNTER = 0

    def __init__(self, initial_text: Optional[str] = None):
        super().__init__(f"Admin label {AdminLabel.INSTANCE_COUNTER}", self.label_get_value, self.set)
        AdminLabel.INSTANCE_COUNTER += 1
        self._label_value = initial_text if initial_text is not None else self.name

    def label_get_value(self) -> str:
        return self._label_value

    def set(self, value: str):
        self._label_value = value
        self.changed.emit()
