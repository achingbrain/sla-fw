# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
from dataclasses import is_dataclass, asdict
from enum import Enum
from time import monotonic
from typing import Union, List, Callable, Any, Dict, Tuple, get_type_hints, Optional  # pylint: disable=unused-import

from pydbus import Variant
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw.errors.exceptions import NotAvailableInState, DBusMappingException, PrinterException
from sl1fw.errors.warnings import PrinterWarning


class DBusObjectPath(str):
    pass


def state_checked(allowed_state: Union[Enum, List[Enum]]):
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

            if isinstance(self.state, Enum):
                current = self.state.value
            else:
                current = self.state

            if current not in allowed:
                raise NotAvailableInState(self.state, allowed)
            return function(self, *args, **kwargs)

        return func

    return decor


def range_checked(minimum, maximum):
    """
    Raises value error if the only method param is not in [min, max] range

    :param minimum: Minimal allowed value
    :param maximum: Maximal allowed value
    :return: Decorated method
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
        func.__doc__ += "\nD-Bus interface:: \n\n\t" + "\n\t".join(dbus.splitlines())
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
    except Exception as e:
        raise DBusMappingException(f"Failed to obtain name for {func}") from e

    dbus = gen_method_dbus_spec(func, name)
    return manual_dbus(dbus)(func)


PYTHON_TO_DBUS_TYPE = {
    int: "i",
    float: "d",
    bool: "b",
    str: "s",
    DBusObjectPath: "o",
    Any: "v",
}


def python_to_dbus_type(python_type: Any) -> str:
    # TODO: Use typing.get_args and typing.get_origin once we adopt python 3.8
    if python_type in PYTHON_TO_DBUS_TYPE:
        return PYTHON_TO_DBUS_TYPE[python_type]

    if hasattr(python_type, "__origin__"):
        if python_type.__origin__ is dict:
            key = python_to_dbus_type(python_type.__args__[0])
            val = python_to_dbus_type(python_type.__args__[1])
            return "a{" + key + val + "}"

        if python_type.__origin__ is list:
            return "a" + python_to_dbus_type(python_type.__args__[0])

        if python_type.__origin__ is tuple:
            items = [python_to_dbus_type(arg) for arg in python_type.__args__]
            return "(" + "".join(items) + ")"

    raise ValueError(f"Type: {python_type} has no defined mapping to dbus")


def gen_method_dbus_spec(obj: Any, name: str) -> str:
    try:
        if isinstance(obj, property):
            access = "read"
            get_type = python_to_dbus_type(get_type_hints(obj.fget)["return"])
            if obj.fset:
                access = "readwrite"
            return f'<property name="{name}" type="{get_type}" access="{access}"></property>'
        if isinstance(obj, Callable):
            args = []
            for n, t in get_type_hints(obj).items():
                if t == type(None):
                    continue
                direction = "out" if n == "return" else "in"
                args.append(f"<arg type='{python_to_dbus_type(t)}' name='{n}' direction='{direction}'/>")
            return f"<method name='{name}'>{''.join(args)}</method>"
        raise ValueError(f"Unsupported dbus mapping type: {type(obj)}")
    except Exception as exception:
        raise DBusMappingException(f"Failed to generate dbus specification for {name}") from exception


def python_to_dbus_value_type(data: Any):
    # pylint: disable = unidiomatic-typecheck
    if type(data) in PYTHON_TO_DBUS_TYPE:
        return PYTHON_TO_DBUS_TYPE[type(data)]

    if isinstance(data, tuple):
        items = [python_to_dbus_value_type(item) for item in data]
        return "(" + "".join(items) + ")"

    if isinstance(data, list):
        dbus_type = "v"
        try:
            if data:
                childType = python_to_dbus_value_type(data[0])
                allEqual = True
                for child in data:
                    allEqual = allEqual and (childType == python_to_dbus_value_type(child))
                if allEqual:
                    dbus_type = childType
        except Exception:
            pass
        return f"a{dbus_type}"

    raise DBusMappingException(f"Failed to get value {data} dbus type")


def wrap_value(data: Any) -> Variant:
    # pylint: disable = unidiomatic-typecheck
    if type(data) in PYTHON_TO_DBUS_TYPE:
        return Variant(PYTHON_TO_DBUS_TYPE[type(data)], data)

    if isinstance(data, dict):
        return wrap_dict_value(data)

    if isinstance(data, tuple):
        return Variant(python_to_dbus_value_type(data), data)

    if isinstance(data, list):
        dbus_type = python_to_dbus_value_type(data)
        if dbus_type[1] == 'v':
            dbus_value = Variant(dbus_type, [wrap_value(d) for d in data])
        else:
            dbus_value = Variant(dbus_type, data)
        return dbus_value

    if isinstance(data, Enum):
        return wrap_value(data.value)

    raise DBusMappingException(f"Failed to wrap dbus value {data}")


def wrap_dict_value(data):
    if data:
        first_key, _ = list(data.items())[0]
        if isinstance(first_key, int):
            signature = "a{iv}"
        else:
            signature = "a{sv}"
    else:
        signature = "a{iv}"

    return Variant(signature, {key: wrap_value(val) for key, val in data.items()})


def wrap_dict_data(data: Dict[str, Any]):
    if isinstance(data, Dict):
        return {key: wrap_value(val) for key, val in data.items()}
    return wrap_value(data)


def wrap_dict_data_recursive(data: Dict[str, Any]):
    if isinstance(data, Dict):
        return {key: wrap_dict_data(val) for key, val in data.items()}
    return wrap_value(data)


LAST_EXCEPTION_ATTR = "_last_exception"


def last_error(method):
    @functools.wraps(method)
    def wrap(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            assert hasattr(self, LAST_EXCEPTION_ATTR)
            setattr(self, LAST_EXCEPTION_ATTR, e)
            raise e

    return wrap


def wrap_exception(e: Optional[Exception]) -> Dict[str, Any]:
    """
    Wrap exception in dictionary

    Exception is represented as dictionary str -> variant
    {
        "code": error code
        "code_specific_feature1": value1
        "code_specific_feature2": value2
        ...
    }

    :return: Exception dictionary
    """
    if not e:
        return {"code": Sl1Codes.NONE.code}

    if isinstance(e, PrinterException):
        ret = {"code": e.CODE.code, "name": type(e).__name__, "text": str(e)}
        if is_dataclass(e):
            ret.update(asdict(e))
        return ret

    return {"code": Sl1Codes.UNKNOWN.code, "name": type(e).__name__, "text": str(e)}


def wrap_warning(warning: Warning) -> Dict[str, Any]:
    """
    Wrap warning in dictionary

    Warning is represented as dictionary str -> variant
    {
        "code": warning code
        "code_specific_feature1": value1
        "code_specific_feature2": value2
        ...
    }

    :param warning: Warning to wrap
    :return: Warning dictionary
    """
    if not warning:
        return {"code": Sl1Codes.NONE_WARNING.code}

    if isinstance(warning, PrinterWarning):
        ret = {"code": warning.CODE.code, "name": type(warning).__name__, "text": str(warning)}
        if is_dataclass(warning):
            ret.update(asdict(warning))
        return ret

    return {"code": Sl1Codes.UNKNOWN_WARNING.code, "name": type(warning).__name__, "text": str(warning)}
