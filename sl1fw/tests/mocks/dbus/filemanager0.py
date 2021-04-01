# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from pydbus.generic import signal

from sl1fw.api.decorators import dbus_api, auto_dbus, auto_dbus_signal

# TODO replace for real file manager

@dbus_api
class FileManager0:
    """Dbus mock api for share file system data"""

    __INTERFACE__ = "cz.prusa3d.sl1.filemanager0"

    PropertiesChanged = signal()

    @auto_dbus_signal
    def MediaInserted(self, path) -> str:
        pass

    @auto_dbus_signal
    def MediaEjected(self, root_path) -> str:
        pass

    @auto_dbus
    def remove(self, path: str) -> None:
        pass
