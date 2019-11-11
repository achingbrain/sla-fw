# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
from time import monotonic
from typing import Union, List, Callable, Any, Dict, Tuple, get_type_hints

from sl1fw.api.exceptions import NotAvailableInState, DBusMappingException
from sl1fw.api.states import Printer0State, Exposure0State


class DBusObjectPath(str):
    pass


def state_checked(allowed_state: Union[Printer0State, Exposure0State, List[Printer0State], List[Exposure0State]]):
    """
    Decorator restricting method call based on allowed state

    :param allowed_state: State in which the method is available, or list of such states
    :return: Method decorator
    """

    def decor(function):
        @functools.wraps(function)
        def func(self, *args, **kwargs):
            if isinstance(allowed_state, list):
                allowed = [state.value for state in allowed_state]
            else:
                allowed = [allowed_state.value]
            if self.state in allowed:
                return function(self, *args, **kwargs)
            else:
                raise NotAvailableInState

        return func

    return decor


def range_checked(minimum, maximum):
    """
    Raises value error if the only method param is not in [min, max] range

    :param minimum: Minimal allowed value
    :param maximum: Maximal allowed value
    :return: Decorathed method
    """
    def decor(func):
        @functools.wraps(func)
        def wrap(self, value):
            if value < minimum or value > maximum:
                raise ValueError(f"Value: {value} out of range: [{minimum}, {maximum}]")
            return func(self, value)
        return wrap
    return decor


def cached(validity_s: float = None):
    """
    Decorator limiting calls to property by using a cache with defined validity.
    This does not support passing arguments other than self to decorated method!

    :param validity_s: Cache validity in seconds, None means valid forever
    :return: Method decorator
    """

    def decor(function):
        cache = {}

        @functools.wraps(function)
        def func(self):
            if (
                "value" not in cache
                or "last" not in cache
                or (validity_s is not None and monotonic() - cache["last"] > validity_s)
            ):
                cache["value"] = function(self)
                cache["last"] = monotonic()
            return cache["value"]
        return func
    return decor


def dbus_api(cls):
    records: List[str] = []
    for var in vars(cls):
        obj = getattr(cls, var)
        if isinstance(obj, property):
            obj = obj.fget
        if hasattr(obj, "__dbus__"):
            record = obj.__dbus__
            assert isinstance(record, str)
            records.append(record)
    cls.dbus = f"<node><interface name='{cls.__INTERFACE__}'>{''.join(records)}</interface></node>"
    return cls


def manual_dbus(dbus: str):
    def decor(func):
        if func.__doc__ is None:
            func.__doc__ = ""
        func.__doc__ += f"\nD-Bus interface:: \n\n\t" + "\n\t".join(dbus.splitlines())
        if isinstance(func, property):
            func.fget.__dbus__ = dbus
        else:
            func.__dbus__ = dbus
        return func

    return decor


def auto_dbus(func):
    try:
        if isinstance(func, property):
            name = func.fget.__name__
        else:
            name = func.__name__
    except:
        raise DBusMappingException(f"Failed to obtain name for {func}")

    dbus = gen_method_dbus_spec(func, name)
    return manual_dbus(dbus)(func)


def python_to_dbus_type(python_type: Any) -> str:
    type_map = {
        int: "i",
        float: "d",
        bool: "b",
        str: "s",
        List[str]: "as",
        List[int]: "ai",
        List[DBusObjectPath]: "ao",
        List[List[int]]: "aai",
        Dict[str, int]: "a{si}",
        Dict[str, str]: "a{ss}",
        Dict[str, float]: "a{sd}",
        Dict[str, Dict[str, int]]: "a{sa{si}}",
        Tuple[int, int]: "(ii)",
        Tuple[int, str, int]: "(isi)",
        DBusObjectPath: "o",
        List[Tuple[str, Dict[str, Any]]]: "a(sa{sv})",
    }

    if python_type in type_map:
        return type_map[python_type]
    else:
        raise ValueError(f"Type: {python_type} has no defined mapping to dbus")


def gen_method_dbus_spec(obj: Any, name: str) -> str:
    try:
        if isinstance(obj, property):
            access = "read"
            get_type = python_to_dbus_type(get_type_hints(obj.fget)["return"])
            if obj.fset:
                access = "readwrite"
            return f'<property name="{name}" type="{get_type}" access="{access}"></property>'
        elif isinstance(obj, Callable):
            args = []
            for n, t in get_type_hints(obj).items():
                if t == type(None):
                    continue
                direction = "out" if n == "return" else "in"
                args.append(f"<arg type='{python_to_dbus_type(t)}' name='{n}' direction='{direction}'/>")
            return f"<method name='{name}'>{''.join(args)}</method>"
        else:
            raise ValueError(f"Unsupported dbus mapping type: {type(obj)}")
    except Exception as exception:
        raise DBusMappingException(f"Failed to generate dbus specification for {name}") from exception
