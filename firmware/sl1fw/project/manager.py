# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from queue import Queue
from typing import Optional

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
        self._exposure_dbus_objects = Queue()
        self._system_bus = SystemBus()

    def new_exposure(self, config: HwConfig, hw: Hardware, screen: Screen, runtime_config: RuntimeConfig) -> Exposure:
        self._current = Exposure(config, hw, screen, runtime_config)
        path = Exposure0.dbus_path(self._current.instance_id)
        registration = self._system_bus.register_object(path, Exposure0(self._current), None)
        self._exposure_dbus_objects.put(registration)
        self.logger.info("New exposure registered as: %s", path)

        while self._exposure_dbus_objects.qsize() > self.MAX_EXPOSURES:
            self._exposure_dbus_objects.get().unregister()

        return self._current

    @property
    def exposure(self) -> Optional[Exposure]:
        return self._current

    def exit(self):
        while not self._exposure_dbus_objects.empty():
            self._exposure_dbus_objects.get().unregister()
