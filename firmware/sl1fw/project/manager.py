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

    def new_exposure(self, config: HwConfig, hw: Hardware, screen: Screen, runtime_config: RuntimeConfig) -> Exposure:
        # Create new exposure object
        self._current = Exposure(config, hw, screen, runtime_config)

        # Register exposure on DBus using the API wrapper
        path = Exposure0.dbus_path(self._current.instance_id)
        registration = self._system_bus.register_object(path, Exposure0(self._current), None)
        self._exposure_dbus_objects.put(registration)
        self.logger.info("New exposure registered as: %s", path)

        # Maintain history exposure registrations
        while self._exposure_dbus_objects.qsize() > self.MAX_EXPOSURES:
            self._exposure_dbus_objects.get().unregister()

        # Register properties changed signal of the new exposure as current exposure signal source
        if self._current_change_registration:
            self._current_change_registration.unsubscribe()
        exposure_dbus = self._system_bus.get("cz.prusa3d.sl1.printer0", path)
        self._current_change_registration = exposure_dbus.PropertiesChanged.connect(self._on_change)

        return self._current

    @property
    def exposure(self) -> Optional[Exposure]:
        return self._current

    def exit(self):
        while not self._exposure_dbus_objects.empty():
            self._exposure_dbus_objects.get().unregister()

    def _on_change(self, __, changed, ___):
        if "state" in changed:
            self.exposure_change.emit()
