# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from enum import unique, Enum
from typing import Callable, TYPE_CHECKING

from gi.repository.GLib import timeout_add_seconds
from pydbus.generic import signal

from sl1fw.api.decorators import dbus_api, auto_dbus
from sl1fw.functions import display_test

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


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

    def __init__(self, display: Display, on_exit: Callable[[], None]):
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.exit = on_exit
        self._state = DisplayTest0State.INIT

    @auto_dbus
    @property
    def state(self) -> int:
        return self._state.value

    @auto_dbus
    def start(self) -> None:
        self.logger.debug("Starting display test")
        self._state = DisplayTest0State.COVER_OPEN
        display_test.start(self.display)
        timeout_add_seconds(1, self._update_cover)

    @auto_dbus
    def finish(self, logo_seen: bool) -> None:
        self.logger.info("Display test finished with logo seen: %s", logo_seen)
        display_test.end(self.display)
        self._state = DisplayTest0State.FINISHED
        self.exit()

    def _update_cover(self):
        if self._state == DisplayTest0State.FINISHED:
            return False

        old = self._state
        if display_test.cover_check(self.display):
            self._state = DisplayTest0State.DISPLAY
        else:
            self._state = DisplayTest0State.COVER_OPEN
        if old != self._state:
            self.PropertiesChanged(self.__INTERFACE__, {"state": self.state}, [])

        return True
