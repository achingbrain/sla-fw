# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from queue import Queue
from typing import Optional

from PySignal import Signal
from pydbus import SystemBus

from sl1fw.api.exposure0 import Exposure0
from sl1fw.libConfig import HwConfig, RuntimeConfig
from sl1fw.libExposure import Exposure
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen


class ExposureManager:
    MAX_EXPOSURES = 3

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._current: Optional[Exposure] = None
        self._current_change_registration = None
        self._exposure_dbus_objects = Queue()
        self._system_bus = SystemBus()
        self.exposure_change = Signal()
        self._bus_name = None

    def new_exposure(
        self,
        config: HwConfig,
        hw: Hardware,
        screen: Screen,
        runtime_config: RuntimeConfig,
        project: str,
        exp_time_ms: Optional[int] = None,
        exp_time_first_ms: Optional[int] = None,
        exp_time_calibrate_ms: Optional[int] = None,
    ) -> Exposure:
        # Create new exposure object and apply passed settings
        exposure = self._create_exposure(
            config, hw, screen, runtime_config, project, exp_time_ms, exp_time_first_ms, exp_time_calibrate_ms
        )

        path = self._register_exposure(exposure)

        # Register properties changed signal of the new exposure as current exposure signal source
        if self._current_change_registration:
            self._current_change_registration.unsubscribe()
        exposure_dbus = self._system_bus.get(Exposure0.__INTERFACE__, path)
        self._current_change_registration = exposure_dbus.PropertiesChanged.connect(self._on_change)

        self._current = exposure
        self.exposure_change.emit()
        return exposure

    @staticmethod
    def _create_exposure(
        config: HwConfig,
        hw: Hardware,
        screen: Screen,
        runtime_config: RuntimeConfig,
        project: str,
        exp_time_ms: Optional[int] = None,
        exp_time_first_ms: Optional[int] = None,
        exp_time_calibrate_ms: Optional[int] = None,
    ):
        exposure = Exposure(config, hw, screen, runtime_config, project)
        if exp_time_ms:
            exposure.project.expTime = exp_time_ms / 1000
        if exp_time_first_ms:
            exposure.project.expTimeFirst = exp_time_first_ms / 1000
        if exp_time_calibrate_ms:
            exposure.project.calibrateTime = exp_time_calibrate_ms / 1000

        return exposure

    def _register_exposure(self, exposure: Exposure) -> str:
        """
        Register exposure on DBus using the API wrapper.

        :param exposure: Exposure to register
        :return: Registered path
        """
        # Register bus name if not already registered
        if not self._bus_name:
            self._bus_name = self._system_bus.request_name(Exposure0.__INTERFACE__)

        path = Exposure0.dbus_path(exposure.instance_id)
        exposure0 = Exposure0(exposure)
        registration = self._system_bus.register_object(path, exposure0, None)
        self._exposure_dbus_objects.put(registration)
        self.logger.info("New exposure registered as: %s", path)

        # Maintain history of exposure registrations
        while self._exposure_dbus_objects.qsize() > self.MAX_EXPOSURES:
            self._exposure_dbus_objects.get().unregister()

        return path

    @property
    def exposure(self) -> Optional[Exposure]:
        return self._current

    def exit(self):
        while not self._exposure_dbus_objects.empty():
            self._exposure_dbus_objects.get().unregister()
        if self._bus_name:
            self._bus_name.unown()

    def _on_change(self, __, changed, ___):
        if "state" in changed:
            self.exposure_change.emit()
