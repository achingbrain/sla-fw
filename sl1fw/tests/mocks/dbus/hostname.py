# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from pydbus.generic import signal

from sl1fw.api.decorators import dbus_api, auto_dbus


@dbus_api
class Hostname:
    __INTERFACE__ = "org.freedesktop.hostname1"

    PropertiesChanged = signal()

    def __init__(self):
        self.hostname_set = False

    @auto_dbus
    def SetStaticHostname(self, _: str, __: bool) -> None:
        pass

    @auto_dbus
    def SetHostname(self, _: str, __: bool) -> None:
        self.hostname_set = True

    @auto_dbus
    @property
    def StaticHostname(self) -> str:
        return "prusa-sl1"
