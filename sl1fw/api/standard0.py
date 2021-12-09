# This file is part of the SL1 firmware
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

"""Dbus API for ui standard communication."""

# pylint: disable=too-many-public-methods
# pylint: disable=protected-access
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes

from __future__ import annotations

import functools
import weakref
from enum import unique, Enum
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Union, TYPE_CHECKING
import hashlib

import distro
from pydbus import SystemBus
from pydbus.generic import signal

from sl1fw import defines
from sl1fw.functions.system import get_hostname
from sl1fw.states.printer import PrinterState, Printer0State
from sl1fw.states.exposure import ExposureState
from sl1fw.api.exposure0 import Exposure0, Exposure0State
from sl1fw.errors.warnings import ResinLow, PrinterWarning
from sl1fw.errors.errors import NotAvailableInState, PrinterException
from sl1fw.api.decorators import (
    auto_dbus,
    dbus_api,
    last_error,
    wrap_dict_data,
    DBusObjectPath,
    auto_dbus_signal,
)

if TYPE_CHECKING:
    from sl1fw.libPrinter import Printer
    from sl1fw.exposure.exposure import Exposure


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

            # ToDo use sl1fw.api.decorators.state_checked instead
            current = Exposure0State.from_exposure(self._current_expo.state).value
            if current not in allowed:
                raise NotAvailableInState(current, allowed)
            return function(self, *args, **kwargs)

        return func

    return decor


@unique
class Standard0State(Enum):
    """
    General printer state enumeration
    """
    READY = 0
    SELECTED = 1
    PRINTING = 2
    POUR_IN_RESIN = 3
    BUSY = 5
    FEED_ME = 6
    ERROR = 9


@dbus_api
class Standard0:
    """
    This class provides a standard printer external interface.
    """

    __INTERFACE__ = "cz.prusa3d.sl1.standard0"

    PropertiesChanged = signal()

    # Mode R | Mode W: bool
    PROPERTIES_ALLOWED = {
        "exposure_time_ms": True,
        "exposure_time_first_ms": True,
        "exposure_user_profile": True,
        "calibration_regions": False,
        "calibrate_time_ms": True,
    }

    PROPERTIES_GROUP = {
        "exposure_times": {
            "exposure_time_ms",
            "exposure_time_first_ms",
            "exposure_user_profile",
            "calibration_regions",
            "calibrate_time_ms",
        }
    }

    def __init__(self, printer: Printer):
        self._last_exception: Optional[Exception] = None
        # Avoid keeping printer alive by API object. Printer object shares lifecycle with the whole application.
        self._printer: Printer = weakref.proxy(printer)
        self.__info_mac = None
        self.__info_uuid = None
        self._last_state = None
        self._printer.exception_occurred.connect(self._on_exception_changed)
        self._printer.state_changed.connect(self._state_update)
        self._printer.action_manager.exposure_change.connect(self._exposure_changed)
        self._printer.http_digest_changed.connect(self._on_http_digest_changed)
        self._printer.api_key_changed.connect(self._on_api_key_changed)
        self._old_expo = None
        self._last_error_or_warn = None

    @auto_dbus_signal
    def LastErrorOrWarn(self, value: Dict[str, Any]):
        pass

    def _on_http_digest_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"net_authorization": self.net_authorization}, [])

    def _on_api_key_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"net_authorization": self.net_authorization}, [])

    def _state_update(self, *args):  # pylint: disable=unused-argument

        state = self._state
        if self._last_state != state:
            self.PropertiesChanged(self.__INTERFACE__, {"state": state.value}, [])
            self._last_state = state

    def _exposure_changed(self, *args):
        """Exposure change, It might connect/disconnect a handle for property change"""
        self._state_update(*args)
        if id(self._old_expo) != id(self._printer.action_manager.exposure):
            if self._old_expo:
                self._old_expo.change.disconnect(self._exposure_values_changed)
            self._old_expo = weakref.proxy(self._printer.action_manager.exposure)
            self._old_expo.change.connect(self._exposure_values_changed)

    def _exposure_values_changed(self, key, value):
        """Property value change in Exposure it should check if are warnings or errors"""
        if key == "exception":
            self.LastErrorOrWarn(wrap_dict_data(PrinterException.as_dict(value)))
        if key == "warning":
            self.LastErrorOrWarn(wrap_dict_data(PrinterWarning.as_dict(value)))
        if key =='warn_resin':
            if value:
                warn = ResinLow()
                self.LastErrorOrWarn(wrap_dict_data(PrinterWarning.as_dict(warn)))
            else:
                self.LastErrorOrWarn(wrap_dict_data(PrinterWarning.as_dict(None)))
        if key == "last_warn":
            self.LastErrorOrWarn(wrap_dict_data(PrinterWarning.as_dict(value)))

    def _on_exception_changed(self, exception: Exception):
        self.LastErrorOrWarn(wrap_dict_data(PrinterException.as_dict(exception)))

    @property
    def _printer_state(self) -> Printer0State:
        state = self._printer.state.to_state0()
        if state:
            return state

        return Printer0State.IDLE

    @property
    def _current_expo(self) -> Exposure:
        """
        Return current exposure if exist
        """
        if self._printer.state == PrinterState.PRINTING:
            return self._printer.action_manager.exposure

        raise NotAvailableInState(self._printer_state, [Printer0State.PRINTING])

    @property
    def _state(self) -> Standard0State:
        state = self._printer_state
        exposure = self._printer.action_manager.exposure
        substate = None
        if exposure:
            substate = Exposure0State.from_exposure(exposure.state)

        result = Standard0State.BUSY
        if state == Printer0State.IDLE:
            result = Standard0State.READY
        elif state == Printer0State.PRINTING:
            if substate == Exposure0State.POUR_IN_RESIN:
                result = Standard0State.POUR_IN_RESIN
            elif substate == Exposure0State.PRINTING:
                result = Standard0State.PRINTING
            elif substate == Exposure0State.FEED_ME:
                result = Standard0State.FEED_ME
            elif substate == Exposure0State.CONFIRM:
                result = Standard0State.SELECTED
            elif substate == Exposure0State.STUCK:
                result = Standard0State.ERROR
            else:
                result = Standard0State.BUSY
        elif state == Printer0State.EXCEPTION:
            result = Standard0State.ERROR

        return result

    def _info_populate(self):
        network = SystemBus().get("org.freedesktop.NetworkManager")
        for device_path in network.Devices:
            dev = SystemBus().get("org.freedesktop.NetworkManager", device_path)
            if dev.Interface == "eth0":
                mac_eth0 = dev.HwAddress
            elif dev.Interface == "wlan0":
                mac_wlan0 = dev.HwAddress

        uuid_hash = hashlib.blake2b(digest_size=16)
        uuid_hash.update(mac_eth0.encode())
        uuid_hash.update(self._printer.hw.cpuSerialNo.encode())
        uuid_hash.update(mac_wlan0.encode())
        self.__info_mac = mac_eth0
        self.__info_uuid = uuid_hash.hexdigest()

    @property
    def _info_mac(self):
        if not self.__info_mac:
            self._info_populate()
        return self.__info_mac

    @property
    def _info_uuid(self):
        if not self.__info_uuid:
            self._info_populate()
        return self.__info_uuid

    ## TELEMETRY ##

    @auto_dbus
    @property
    def state(self) -> int:
        """
        Return a generic state
        """
        return self._state.value

    @auto_dbus
    @property
    def hw_temperatures(self) -> Dict[str, float]:
        """
        :return: Return a python dict with the temperatures.

        unit: Grade Celsius

        .. code-block:: python

            sl1:
            {
                'temp_led': 29.2,
                'temp_amb': 27.7,
                'cpu_temp': 40.0
            }
        """
        return self._printer.hw.getTemperaturesDict()

    @auto_dbus
    @property
    def hw_fans(self) -> Dict[str, int]:
        """
        :return: Return a python dict with the fans measures

        .. code-block:: python

            unit: RPM
            sl1:
            {
                "uv_led": 1000,
                "blower": 1000,
                "rear": 1000,
            }

        """
        return self._printer.hw.getFansRpmDict()

    @auto_dbus
    @property
    @last_error
    def job(self) -> Dict[str, Any]:
        """
        Printing progress.

        .. code-block:: python

            sl1:
            {
                "current_layer": 10,
                "total_layers": 20,
                "remaining_material" : 200.0,     # ml
                "consumed_material": 200.0,       # ml
                "progress": 50,                   # 1-100
                "time_elapsed": 131321322123000,  # ms
                "remaining_time": 131321322123000 # ms
            }
        """
        exposure = self._current_expo
        project = exposure.project
        data = {
            "current_layer": exposure.actual_layer + 1,
            "total_layers": project.total_layers,
            "remaining_material": exposure.remain_resin_ml if exposure.remain_resin_ml else -1,
            "consumed_material": exposure.resin_count,
            "progress": exposure.progress,
            "estimatedPrintTime": exposure.estimated_total_time_ms / 1000,
            "remaining_time": exposure.estimate_remain_time_ms() / 1000,
            "exposureTime": project.exposure_time_ms,
            "exposureTimeFirst": project.exposure_time_first_ms,
            "exposureUserProfile": project.exposure_user_profile,
            "path": str(project.path),
        }
        if exposure.printStartTime.microsecond == 0:
            data["time_elapsed"] = 0
        else:
            data["time_elapsed"] = (datetime.now(tz=timezone.utc) - exposure.printStartTime).total_seconds()
        if project.calibrate_regions > 0:
            data["exposureTimeCalibration"] = project.calibrate_time_ms

        return wrap_dict_data(data)

    @auto_dbus
    @property
    def hw_telemetry(self) -> Dict[str, Any]:
        """
        Printer telemetry

        .. code-block:: python

            sl1:
            {
                "cover_closed": true, # bool
                "temperatures": {
                    uv_led: 11,
                    ambient: 22,
                    cpu_a64: 33
                },
                "fans" : {
                    "blower": 1000,
                    "uv_led": 1000,
                    "rear": 1000,
                },
                "state": {
                    "state": 1,
                    "substate": 1,
                    "error_code": 500
                },
            }
        """
        return wrap_dict_data(
            {
                "cover_closed": self._printer.hw.isCoverClosed(),
                "temperatures": self._printer.hw.getTemperaturesDict(),
                "fans": self._printer.hw.getFansRpmDict(),
                "state": self._state.value,
            }
        )

    ## PROJECT PROPERTIES ##
    @auto_dbus
    @property
    @last_error
    def project_path(self) -> str:
        """
        Full path to the project being printed

        make sure don't' try to delete a file that is printing

        :return: Project file with path
        """
        exposure = self._current_expo
        return str(exposure.project.path)

    @auto_dbus
    @last_error
    def project_get_properties(self, properties_list: List[str]) -> Dict[str, Any]:
        """
        Given a list of project properties, return a python dict with their values.
        It's possible a group of values like all the exposure times: "exposure_times".

        .. code-block:: python

            sl1: properties_get(["exposure_times"])
            {
                "exposure_time_ms": 1000,
                "exposure_time_first_ms": 1000,
                "calibrate_regions": 1,
                "calibrate_time_ms": 1000,
            }

        """
        exposure = self._current_expo
        properties = {}
        for p in properties_list:
            if p in self.PROPERTIES_GROUP:
                properties_list.extend(self.PROPERTIES_GROUP[p])
            elif p not in properties and p in self.PROPERTIES_ALLOWED:
                properties[p] = getattr(exposure.project, p)
            else:
                raise KeyError(f"key: {p} has no defined for read in the project.")

        return wrap_dict_data(properties)

    @auto_dbus
    @last_error
    def project_set_properties(self, properties_dict: Dict[str, Any]) -> None:
        """
        Change project properties passing by a python dict with their values.

        .. code-block:: python

            sl1:
            properties_set({
                "exposure_time_ms": 1000,
                "exposure_time_first_ms": 1000,
                "calibrate_time_ms": 1000,
                "exposure_user_profile": 1
            })

        :raises KeyError: If the property does not exists.
        """
        exposure = self._current_expo
        for p, v in properties_dict.items():
            if self.PROPERTIES_ALLOWED.get(p, False):
                setattr(exposure.project, p, v)
            else:
                raise KeyError(f"key: {p} has no defined for write in the project.")

    ## PRINTER COMMANDS ##

    @auto_dbus
    @last_error
    def cmd_select(self, project_path: str, auto_advance: bool, ignore_errors: bool) -> DBusObjectPath:
        """
        Open project preview

        sl1: same to printer0.print

        :param project_path: Path to project in printer filesystem
        :param auto_advance: Automatic start print
        :param ignore_errors: Don't throw errors, useful to try open the latest project when uploading a new file or
         plug an USB.

        :returns: Print task object
        """
        try:
            # close a project already opened
            last_exposure = self._printer.action_manager.exposure
            if last_exposure:
                last_exposure.try_cancel()

            # create a new exposure
            expo = self._printer.action_manager.new_exposure(
                self._printer.hw,
                self._printer.exposure_image,
                self._printer.runtime_config,
                project_path,
            )

            if expo.state == ExposureState.FAILURE:
                raise expo.fatal_error

            # start print automatically
            if auto_advance:
                expo.confirm_print_start()

            return Exposure0.dbus_path(expo.instance_id)
        except Exception:
            if not ignore_errors:
                raise
        return DBusObjectPath("/")

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.CONFIRM)
    def cmd_confirm(self) -> None:
        """
        Confirm print project

        sl1: Confirm exposure start

        :return: None
        """
        self._current_expo.confirm_print_start()

    @auto_dbus
    @last_error
    @state_checked([Exposure0State.PRINTING, Exposure0State.CONFIRM, Exposure0State.CHECKS, Exposure0State.CONFIRM,
                    Exposure0State.COVER_OPEN, Exposure0State.POUR_IN_RESIN])
    def cmd_cancel(self) -> None:
        """
        Cancel print

        :return: None
        """
        self._current_expo.cancel()

    @auto_dbus
    @last_error
    def cmd_try_cancel_by_path(self, path:str) -> None:
        """
        Cancel exposure if the paths are equals

        :return: None
        """
        self._printer.action_manager.try_cancel_by_path(path)

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.PRINTING)
    def cmd_pause(self) -> None:
        """
        Pauses current job. Currently used only for manual feedme
        """
        self._current_expo.doFeedMe()

    @auto_dbus
    @last_error
    @state_checked([Exposure0State.FEED_ME, Exposure0State.POUR_IN_RESIN])
    def cmd_continue(self) -> None:
        """
        Continue printing after a pause

        Standard0 cannot distinguish between initial resin fill and feedme. This fires appropriate action at the
        current state.
        """
        if self._current_expo.state == ExposureState.POUR_IN_RESIN:
            self._current_expo.confirm_resin_in()
        else:
            self._current_expo.doBack()

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.FEED_ME)
    def cmd_resin_refill(self) -> None:
        """
        Pauses current job to manual resin refill
        """
        self._current_expo.setResinVolume(defines.resinMaxVolume)

    ## NETWORK ##

    @auto_dbus
    @property
    @last_error
    def help_page_url(self) -> str:
        return self._printer.help_page_url

    @auto_dbus
    @property
    def net_hostname(self) -> str:
        return get_hostname()

    @auto_dbus
    @property
    def net_ip(self) -> str:
        ip = self._printer.inet.ip
        return ip if ip else ""

    @auto_dbus
    @property
    def net_authorization(self) -> Dict[str, Any]:
        """
        type: one of ["digest","api_key","tls", ...]
        options: Optional extra info

        .. code-block:: python

            sl1
            {
                "type": "digest",
                "options": { "api_key": "samebigstring" }
            }
        """
        if self._printer.http_digest:
            data = {"type": "digest", "password": self._printer.api_key}
        else:
            data = {"type": "api_key", "api_key": self._printer.api_key}
        return wrap_dict_data(data)

    ## SYSTEM ##

    @auto_dbus
    @property
    def info(self) -> Dict[str, str]:
        """
        Printer info

        .. code-block:: python

            sl1
            {
                'name': 'Original Prusa Sl1',
                'firmware': '1.5.0',
                'sn': 'CZPX1234X000XK0001',
                'mac': '10:00:10:00:10:00',
                'uuid': '2a2db92796ac6379dc981c2e0d6f2cff541eddf2'
            }
        """
        return {
            "name": "Original Prusa Sl1",
            "firmware": distro.version(),
            "sn": self._printer.hw.cpuSerialNo.lstrip(" *"),
            "mac": self._info_mac,
            "uuid": self._info_uuid,
        }

    # Error

    @auto_dbus
    @property
    def last_exception(self) -> Dict[str, Any]:
        return wrap_dict_data(PrinterException.as_dict(self._last_exception))
