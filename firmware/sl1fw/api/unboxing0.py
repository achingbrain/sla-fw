# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from enum import unique, Enum
from typing import TYPE_CHECKING

from pydbus.generic import signal

from sl1fw.api.decorators import dbus_api, state_checked, auto_dbus
from sl1fw.states.unboxing import UnboxingState

if TYPE_CHECKING:
    from sl1fw.state_actions.unboxing import Unboxing


@unique
class Unboxing0State(Enum):
    INIT = 0  # Before start
    STICKER = 1  # Remove safety sticker, open the cover
    COVER_CLOSED = 2  # Wait for cover open
    MOVING_TO_FOAM = 3  # Printer moving for easier manipulation
    SIDE_FOAM = 4  # Remove black fom on the side of the printer
    MOVING_TO_TANK = 5  # Printer moving for easier manipulation
    TANK_FOAM = 6  # Remove resin tank
    DISPLAY_FOIL = 7  # Peel off exposure display foil
    FINISHED = 8
    CANCELED = 9

    @staticmethod
    def from_unboxing(state: UnboxingState) -> Unboxing0State:
        return {
            UnboxingState.INIT: Unboxing0State.INIT,
            UnboxingState.STICKER: Unboxing0State.STICKER,
            UnboxingState.COVER_CLOSED: Unboxing0State.COVER_CLOSED,
            UnboxingState.MOVING_TO_FOAM: Unboxing0State.MOVING_TO_FOAM,
            UnboxingState.SIDE_FOAM: Unboxing0State.SIDE_FOAM,
            UnboxingState.MOVING_TO_TANK: Unboxing0State.MOVING_TO_TANK,
            UnboxingState.TANK_FOAM: Unboxing0State.TANK_FOAM,
            UnboxingState.DISPLAY_FOIL: Unboxing0State.DISPLAY_FOIL,
            UnboxingState.FINISHED: Unboxing0State.FINISHED,
            UnboxingState.CANCELED: Unboxing0State.CANCELED,
        }[state]


@dbus_api
class Unboxing0:
    """
    Unboxing D-Bus interface
    """

    __INTERFACE__ = "cz.prusa3d.sl1.unboxing0"
    DBUS_PATH = "/cz/prusa3d/sl1/unboxing0"
    PropertiesChanged = signal()

    def __init__(self, unboxing: Unboxing):
        self._unboxing = unboxing
        self._unboxing.state_changed.connect(self._state_changed)
        self._state: Unboxing0State = Unboxing0State.from_unboxing(self._unboxing.state)

    @auto_dbus
    @property
    def state(self) -> int:
        return self._state.value

    @auto_dbus
    @state_checked(Unboxing0State.STICKER)
    def sticker_removed_cover_open(self) -> None:
        self._unboxing.sticker_removed_cover_open()

    @auto_dbus
    @state_checked(Unboxing0State.SIDE_FOAM)
    def side_foam_removed(self) -> None:
        self._unboxing.side_foam_removed()

    @auto_dbus
    @state_checked(Unboxing0State.TANK_FOAM)
    def tank_foam_removed(self) -> None:
        self._unboxing.tank_foam_removed()

    @auto_dbus
    @state_checked(Unboxing0State.DISPLAY_FOIL)
    def display_foil_removed(self) -> None:
        self._unboxing.display_foil_removed()

    @auto_dbus
    def cancel(self) -> None:
        self._unboxing.cancel()

    def _state_changed(self) -> None:
        new = Unboxing0State.from_unboxing(self._unboxing.state)
        if new != self._state:
            self._state = new
            self.PropertiesChanged(self.__INTERFACE__, {"state": self._state.value}, [])
