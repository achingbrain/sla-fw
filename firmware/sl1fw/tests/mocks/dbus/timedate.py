# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from pydbus.generic import signal

from sl1fw.api.decorators import dbus_api, auto_dbus


@dbus_api
class TimeDate:
    __INTERFACE__ = "org.freedesktop.timedate1"

    PropertiesChanged = signal()

    def __init__(self):
        self._ntp = True
        self._tz = 'America/Vancouver'

    @auto_dbus
    @property
    def Timezone(self) -> str:
        return self._tz

    @auto_dbus
    def SetTimezone(self, tz: str, _: bool):
        self._tz = tz

    @auto_dbus
    @property
    def NTP(self) -> bool:
        return self._ntp

    @auto_dbus
    def SetNTP(self, state: bool, _: bool) -> None:
        self._ntp = state
