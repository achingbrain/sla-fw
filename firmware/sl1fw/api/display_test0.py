# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from enum import unique, Enum

from PySignal import Signal
from gi.repository.GLib import timeout_add_seconds
from pydbus.generic import signal

from sl1fw.api.decorators import dbus_api, auto_dbus, state_checked
from sl1fw.functions import display_test
from sl1fw.libConfig import RuntimeConfig, HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen


@unique
class DisplayTest0State(Enum):
    INIT = 0
    COVER_OPEN = 1
    DISPLAY = 2
    FINISHED = 3


@dbus_api
class DisplayTest0:
    __INTERFACE__ = "cz.prusa3d.sl1.displaytest0"
    DBUS_PATH = "/cz/prusa3d/sl1/displaytest0"

    PropertiesChanged = signal()

    def __init__(self, hw: Hardware, hw_config: HwConfig, screen: Screen, runtime_config: RuntimeConfig):
        self.logger = logging.getLogger(__name__)
        self._hw = hw
        self._screen = screen
        self._runtime_config = runtime_config
        self._hw_config = hw_config
        self._state = DisplayTest0State.INIT
        self.change = Signal()
        self.change.connect(self._state_changed)

    @auto_dbus
    @property
    def state(self) -> int:
        return self._state.value

    @auto_dbus
    @state_checked(DisplayTest0State.INIT)
    def start(self) -> None:
        self.logger.info("Starting display test")
        self._state = DisplayTest0State.COVER_OPEN
        self.change.emit()
        display_test.start(self._hw, self._screen, self._runtime_config)
        timeout_add_seconds(1, self._update_cover)

    @auto_dbus
    @state_checked(DisplayTest0State.DISPLAY)
    def finish(self, logo_seen: bool) -> None:
        self.logger.info("Display test finished with logo seen: %s", logo_seen)
        display_test.end(self._hw, self._screen, self._runtime_config)
        self._state = DisplayTest0State.FINISHED
        self.change.emit()

    def _update_cover(self):
        if self._state == DisplayTest0State.FINISHED:
            return False

        old = self._state
        if display_test.cover_check(self._hw, self._hw_config):
            self._state = DisplayTest0State.DISPLAY
            self.change.emit()
        else:
            self._state = DisplayTest0State.COVER_OPEN
        if old != self._state:
            self.change.emit()

        return True

    def _state_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"state": self.state}, [])
