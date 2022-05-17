# This file is part of the SLA firmware
# Copyright (C) 2020-2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from functools import partial, wraps
from typing import Callable, Any, Optional, List

from PySignal import Signal


class AdminItem:
    # pylint: disable=too-few-public-methods
    def __init__(self, name: str, icon: str=""):
        self.name = name
        self.icon = icon


class AdminAction(AdminItem):
    # pylint: disable=too-few-public-methods
    def __init__(self, name: str, action: Callable, icon: str=""):
        super().__init__(name, icon)
        self._action = action

    def execute(self):
        self._action()


class AdminValue(AdminItem):
    def __init__(self, name: str, getter: Callable, setter: Callable, icon: str=""):
        super().__init__(name, icon)
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
    # pylint: disable = too-many-arguments
    def __init__(
        self, name: str, getter: Callable, setter: Callable, step: int, icon: str = "", unit: type = None
    ):
        super().__init__(name, getter, setter, icon)
        self._step = step
        self._unit = unit

    @classmethod
    def from_value(
            cls, name: str, obj: object, prop: str, step: int, icon: str = "", unit: type = None
    ) -> AdminIntValue:
        def g():
            return getattr(obj, prop)

        def s(value):
            if unit:
                value = unit(value)
            setattr(obj, prop, value)

        return AdminIntValue(name, g, s, step, icon)

    @classmethod
    def from_property(cls, obj: object, prop: property, step: int, icon: str="") -> AdminIntValue:
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminIntValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj), step, icon)
        cls._map_prop(obj, prop, value, prop_name)
        return value

    @property
    def step(self) -> int:
        return self._step


class AdminFixedValue(AdminValue):
    # pylint: disable = too-many-arguments
    def __init__(self, name: str, getter: Callable, setter: Callable, step: int, fractions: int, icon: str=""):
        super().__init__(name, getter, setter, icon)
        self._step = step
        self._fractions = fractions

    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, step: int, fractions: int, icon: str="") -> AdminFixedValue:
        def g():
            return getattr(obj, prop)

        def s(value):
            setattr(obj, prop, value)

        return AdminFixedValue(name, g, s, step, fractions, icon)

    @classmethod
    def from_property(cls, obj: object, prop: property, step: int, fractions: int, icon: str="") -> AdminFixedValue:
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminFixedValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj), step, fractions, icon)
        cls._map_prop(obj, prop, value, prop_name)
        return value

    @property
    def step(self) -> int:
        return self._step

    @property
    def fractions(self) -> int:
        return self._fractions


class AdminFloatValue(AdminValue):
    # pylint: disable = too-many-arguments
    def __init__(self, name: str, getter: Callable, setter: Callable, step: float, icon: str=""):
        super().__init__(name, getter, setter, icon)
        self._step = step

    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, step: float, icon: str="") -> AdminFloatValue:
        def g():
            return getattr(obj, prop)

        def s(value):
            setattr(obj, prop, value)

        return AdminFloatValue(name, g, s, step, icon)

    @classmethod
    def from_property(cls, obj: object, prop: property, step: float, icon: str="") -> AdminFloatValue:
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminFloatValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj), step, icon)
        cls._map_prop(obj, prop, value, prop_name)
        return value

    @property
    def step(self) -> float:
        return self._step


class AdminBoolValue(AdminValue):
    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, icon: str="") -> AdminBoolValue:
        return AdminBoolValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop), icon)

    @classmethod
    def from_property(cls, obj: object, prop: property, icon: str="") -> AdminBoolValue:
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminBoolValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj), icon)
        cls._map_prop(obj, prop, value, prop_name)
        return value


class AdminTextValue(AdminValue):
    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, icon: str=""):
        return AdminTextValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop), icon)

    @classmethod
    def from_property(cls, obj: object, prop: property, icon: str=""):
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminTextValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj), icon)
        cls._map_prop(obj, prop, value, prop_name)
        return value


class AdminLabel(AdminTextValue):
    INSTANCE_COUNTER = 0

    def __init__(self, initial_text: Optional[str] = None, icon: str=""):
        super().__init__(f"Admin label {AdminLabel.INSTANCE_COUNTER}", self.label_get_value, self.set, icon)
        AdminLabel.INSTANCE_COUNTER += 1
        self._label_value = initial_text if initial_text is not None else self.name

    def label_get_value(self) -> str:
        return self._label_value

    def set(self, value: str):
        self._label_value = value
        self.changed.emit()


class AdminSelectionValue(AdminValue):
    """Allow selection of an item from a preset list, value is an index in the list"""
    # pylint: disable = too-many-arguments
    def __init__(self, name: str, getter: Callable, setter: Callable, selection: List[str], wrap_around=False, icon: str=""):
        super().__init__(name, getter, setter, icon)
        self._selection = selection
        self._wrap_around = wrap_around

    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, selection: List[str], icon: str="") -> AdminSelectionValue:
        def g():
            return getattr(obj, prop)

        def s(value):
            setattr(obj, prop, value)

        return AdminSelectionValue(name, g, s, selection, icon)

    @classmethod
    def from_property(cls, obj: object, prop: property, selection: List[str], icon: str="") -> AdminSelectionValue:
        prop_name = cls._get_prop_name(obj, prop)
        value = AdminSelectionValue(prop_name, partial(prop.fget, obj), partial(prop.fset, obj), selection, icon)
        cls._map_prop(obj, prop, value, prop_name)
        return value

    @property
    def selection(self) -> List[str]:
        return self._selection

    @property
    def wrap_around(self) -> bool:
        return self._wrap_around
