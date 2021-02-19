# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Dict

from pydbus.generic import signal

from sl1fw.api.decorators import dbus_api, auto_dbus, DBusObjectPath


@dbus_api
class NetworkManager:
    __INTERFACE__ = "org.freedesktop.NetworkManager"

    PropertiesChanged = signal()

    def __init__(self):
        self._connections = ['ethernet', 'wifi0', 'wifi1']
        self.connections = self._connections.copy()
        self.iter = iter(self._connections)
        self.currentItem = ''

    @auto_dbus
    def GetAllDevices(self) -> List[DBusObjectPath]: # pylint: disable=no-self-use
        return []

    @auto_dbus
    @property
    def PrimaryConnection(self) -> DBusObjectPath:
        return DBusObjectPath("/")

    @auto_dbus
    def state(self) -> int: # pylint: disable=no-self-use
        return 0

    @auto_dbus
    def ListConnections(self) -> List[str]:
        return self.connections

    @auto_dbus
    def Delete(self) -> None:
        # TODO: improve. This relies on the fact that connections are deleted while iterating over them.
        self.connections.remove(self.currentItem)

    @auto_dbus
    def GetSettings(self) -> Dict[str, Dict[str, str]]:
        try:
            self.currentItem = next(self.iter)
            connectionType = '802-11-wireless'
            if self.currentItem == 'ethernet':
                connectionType = '802-3-ethernet'
            return { 'connection' : {'type': connectionType}}
        except StopIteration:
            return  {}
