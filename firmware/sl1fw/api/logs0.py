# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from pydbus.generic import signal

from sl1fw.api.decorators import dbus_api, auto_dbus, wrap_dict_data, wrap_exception
from sl1fw.libHardware import Hardware
from sl1fw.state_actions.logs import LogsExport, UsbExport, ServerUpload
from sl1fw.states.logs import LogsState, StoreType


@dbus_api
class Logs0:
    __INTERFACE__ = "cz.prusa3d.sl1.logs0"
    DBUS_PATH = "/cz/prusa3d/sl1/logs0"

    PropertiesChanged = signal()

    def __init__(self, hw: Hardware):
        self._logger = logging.getLogger(__name__)
        self._hw = hw
        self._exporter: Optional[LogsExport] = None

    @auto_dbus
    def usb_save(self) -> None:
        if self._exporter and self._exporter.state not in LogsState.finished_states():
            self._logger.warning("No starting another log export as it is already running")
            return

        self._start_exporter(UsbExport(self._hw))

    @auto_dbus
    def server_upload(self) -> None:
        if self._exporter and self._exporter.state not in LogsState.finished_states():
            self._logger.warning("No starting another log export as it is already running")
            return

        self._start_exporter(ServerUpload(self._hw))

    def _start_exporter(self, exporter: LogsExport):
        self._exporter = exporter
        self.PropertiesChanged(self.__INTERFACE__, {"type": exporter.type.value}, [])
        exporter.state_changed.connect(
            lambda value: self.PropertiesChanged(self.__INTERFACE__, {"state": value.value}, [])
        )
        exporter.export_progress_changed.connect(
            lambda value: self.PropertiesChanged(self.__INTERFACE__, {"export_progress": value}, [])
        )
        exporter.store_progress_changed.connect(
            lambda value: self.PropertiesChanged(self.__INTERFACE__, {"store_progress": value}, [])
        )
        exporter.log_upload_identifier_changed.connect(
            lambda value: self.PropertiesChanged(self.__INTERFACE__, {"log_upload_identifier": value}, [])
        )
        exporter.exception_changed.connect(
            lambda _: self.PropertiesChanged(self.__INTERFACE__, {"exception": self.exception}, [])
        )
        exporter.start()

    @auto_dbus
    def cancel(self) -> None:
        """
        Cancel currently running log export

        :return: None
        """
        if not self._exporter:
            self._logger.warning("No log export to cancel")
            return
        self._exporter.cancel()

    @auto_dbus
    @property
    def exception(self) -> Dict[str, Any]:
        if not self._exporter:
            return wrap_dict_data(wrap_exception(None))
        return wrap_dict_data(wrap_exception(self._exporter.exception))

    @auto_dbus
    @property
    def state(self) -> int:
        if not self._exporter:
            return LogsState.IDLE.value
        return self._exporter.state.value

    @auto_dbus
    @property
    def type(self) -> int:
        if not self._exporter:
            return StoreType.IDLE.value
        return self._exporter.type.value

    @auto_dbus
    @property
    def export_progress(self) -> float:
        """
        Log data export progress

        :return: 0-1 export progress
        """
        if not self._exporter:
            return 0
        return self._exporter.export_progress

    @auto_dbus
    @property
    def store_progress(self) -> float:
        """
        Log data upload progress

        :return: 0-1 upload progress
        """
        if not self._exporter:
            return 0
        return self._exporter.store_progress

    @auto_dbus
    @property
    def log_upload_identifier(self) -> str:
        if not self._exporter or not self._exporter.log_upload_identifier:
            return ""

        return self._exporter.log_upload_identifier
