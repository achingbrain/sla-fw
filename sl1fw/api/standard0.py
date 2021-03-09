# This file is part of the SL1 firmware
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

"""Dbus API for ui standard communication."""

# pylint: disable=too-many-public-methods
# pylint: disable=protected-access

from __future__ import annotations

import functools
import weakref
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Union, TYPE_CHECKING
import hashlib

import distro
from pydbus import SystemBus
from pydbus.generic import signal

from sl1fw.states.printer import PrinterState, Printer0State
from sl1fw.api.exposure0 import Exposure0, Exposure0State
from sl1fw.errors.exceptions import NotAvailableInState
from sl1fw.api.decorators import auto_dbus, dbus_api, last_error, wrap_dict_data, wrap_exception, DBusObjectPath

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
        "calibration_regions": False,
        "exposure_time_calibrate_ms": True,
    }

    PROPERTIES_GROUP = {
        "exposure_times": {
            "exposure_time_ms",
            "exposure_time_first_ms",
            "calibration_regions",
            "exposure_time_calibrate_ms",
        }
    }

    def __init__(self, printer: Printer):
        self._last_exception: Optional[Exception] = None
        # Avoid keeping printer alive by API object. Printer object shares lifecycle with the whole application.
        self._printer = weakref.proxy(printer)
        self.__info_mac = None
        self.__info_uuid = None
        self._last_state = None
        self._printer.display.state_changed.connect(self._state_update)
        self._printer.state_changed.connect(self._state_update)
        self._printer.action_manager.exposure_change.connect(self._state_update)
        self._printer.http_digest_changed.connect(self._on_http_digest_changed)
        self._printer.api_key_changed.connect(self._on_api_key_changed)

    def _on_http_digest_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"net_authorization": self.net_authorization}, [])

    def _on_api_key_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"net_authorization": self.net_authorization}, [])

    def _state_update(self, *args):  # pylint: disable=unused-argument
        state = self._state
        if self._last_state != state:
            self.PropertiesChanged(self.__INTERFACE__, {"state": state}, [])
            self._last_state = state

    @property
    def _printer_state(self) -> Printer0State:
        state = self._printer.state.to_state0()
        if state:
            return state

        state = self._printer.display.state.to_state0()
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
    def _state(self) -> str:
        state = self._printer_state

        try:
            substate = Exposure0State.from_exposure(self._printer.action_manager.exposure.state)
        except Exception:
            substate = None

        result = "BUSY"
        if state == Printer0State.IDLE:
            if substate in [Exposure0State.FAILURE, Exposure0State.STUCK]:
                result = "ATTENTION"
            else:
                result = "READY"
        elif state == Printer0State.PRINTING:
            if substate == Exposure0State.PRINTING:
                result = "PRINTING"
            elif substate in [
                Exposure0State.COVER_OPEN,
                Exposure0State.FEED_ME,
                Exposure0State.CHECK_WARNING,
                Exposure0State.CONFIRM,
            ]:
                result = "ATTENTION"
            elif substate in [Exposure0State.DONE, Exposure0State.CANCELED, Exposure0State.FINISHED]:
                result = "FINISHED"
            elif substate in [Exposure0State.FAILURE, Exposure0State.STUCK]:
                result = "ERROR"
        elif state == Printer0State.EXCEPTION:
            result = "ERROR"

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
    def state(self) -> str:
        """
        Return a generic state
        """
        return self._state

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
    def job(self) -> Dict[str, float]:
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
        data = {
            "current_layer": exposure.actual_layer,
            "total_layers": exposure.project.total_layers,
            "remaining_material": exposure.remain_resin_ml if exposure.remain_resin_ml else -1,
            "consumed_material": exposure.resin_count,
            "progress": 100 * exposure.progress,
            "remaining_time": exposure.countRemainTime() * 60000,
        }
        if exposure.printStartTime.microsecond == 0:
            data["time_elapsed"] = 0
        else:
            data["time_elapsed"] = (datetime.now(tz=timezone.utc) - exposure.printStartTime).total_seconds()

        return data

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
                "state": self._state,
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
                "calibrate_time_ms": 1000
            })

        :raises KeyError: If the property does not exists.
        """
        exposure = self._current_expo
        for p, v in properties_dict.items():
            if self.PROPERTIES_ALLOWED.get(p, False):
                setattr(exposure.project, p, v)
            else:
                raise KeyError(f"key: {p} has no defined for write in the project.")

    @auto_dbus
    @property
    @last_error
    def project_selected(self) -> Dict[str, Any]:
        """
        return a dictionary to show on confirming screen

        .. code-block:: python

            sl1:
            {
                "path": "path/to/project.sl1",
                "exposure_times": "1.5/1.5/1.5 s",
                "last_modified": 123132132132,       # ms
                "total_layers": 20
            }
        """
        exposure = self._current_expo
        return wrap_dict_data(
            {
                "path": str(exposure.project.path),
                "exposure_times": "{0:.3g}/{1:.3g}/{2:.3g} s".format(
                    exposure.project.exposure_time_first_ms / 1000,
                    exposure.project.exposure_time_ms / 1000,
                    exposure.project.calibrate_time_ms / 1000,
                ),
                "last_modified": exposure.project.modification_time * 1000,
                "total_layers": exposure.project.total_layers,
            }
        )

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
            # check if printer is Idle
            printer_state = self._printer_state
            if printer_state != Printer0State.IDLE:
                raise NotAvailableInState(printer_state.value, [Printer0State.IDLE.value])

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

            # start print automaticaly
            if auto_advance:
                expo.confirm_print_start()

            return Exposure0.dbus_path(expo.instance_id)
        except Exception:
            if not ignore_errors:
                raise

    @auto_dbus
    @last_error
    @state_checked([Exposure0State.CONFIRM])
    def cmd_confirm(self) -> None:
        """
        Confirm print project

        sl1: Confirm exposure start

        :return: None
        """
        self._current_expo.confirm_print_start()

    @auto_dbus
    @last_error
    @state_checked([Exposure0State.PRINTING, Exposure0State.CHECKS, Exposure0State.CONFIRM, Exposure0State.COVER_OPEN])
    def cmd_cancel(self) -> None:
        """
        Cancel print

        :return: None
        """
        self._current_expo.cancel()

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.PRINTING)
    def cmd_pause(self, motivation: str) -> None:
        """
        pause printer, it must informe the motivation
        """
        if motivation == "feed_me":
            self._current_expo.doFeedMe()
        else:
            raise TypeError(f"Unknoun motivation: {motivation}")

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.FEED_ME)
    def cmd_continue(self) -> None:
        """
        Continue printing after a pause
        """
        self._current_expo.doContinue()

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.FEED_ME)
    def cmd_back(self) -> None:
        """
        Useful to back manual, e.g.feedme
        """
        self._current_expo.doBack()

    ## NETWORK ##

    @auto_dbus
    @property
    def net_hostname(self) -> str:
        return self._printer.inet.hostname

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
        return wrap_dict_data(wrap_exception(self._last_exception))
