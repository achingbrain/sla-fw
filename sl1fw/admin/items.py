# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum, auto
from functools import partial
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


class AdminIntValue(AdminValue):
    def __init__(self, name: str, getter: Callable, setter: Callable, step: int):
        super().__init__(name, getter, setter)
        self._step = step

    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, step: int):
        return AdminIntValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop), step)

    @property
    def step(self) -> int:
        return self._step


class AdminFloatValue(AdminValue):
    def __init__(self, name: str, getter: Callable, setter: Callable, step: float):
        super().__init__(name, getter, setter)
        self._step = step

    @classmethod
    def from_value(cls, name: str, obj: object, prop: str, step: float):
        return AdminFloatValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop), step)

    @property
    def step(self) -> float:
        return self._step


class AdminBoolValue(AdminValue):
    @classmethod
    def from_value(cls, name: str, obj: object, prop: str):
        return AdminBoolValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop))


class AdminTextValue(AdminValue):
    @classmethod
    def from_value(cls, name: str, obj: object, prop: str):
        return AdminTextValue(name, partial(getattr, obj, prop), partial(setattr, obj, prop))


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


class AdminItemType(Enum):
    ACTION = auto()
    INT_VALUE = auto()
    FLOAT_VALUE = auto()
    BOOL_VALUE = auto()
    TEXT_VALUE = auto()
    IMAGE = auto()


def admin_action(method: Callable):
    method.__admin_type__ = AdminItemType.ACTION
    return method


def admin_int(step=1):
    def decor(value: property):
        value.fget.__admin_type__ = AdminItemType.INT_VALUE
        value.fget.__admin_step__ = step
        return value

    return decor


def admin_float(step=0.1):
    def decor(value: property):
        value.fget.__admin_type__ = AdminItemType.FLOAT_VALUE
        value.fget.__admin_step__ = step
        return value

    return decor


def admin_bool(value: property):
    value.fget.__admin_type__ = AdminItemType.BOOL_VALUE
    return value


def admin_text(value: property):
    value.fget.__admin_type__ = AdminItemType.TEXT_VALUE
    return value
