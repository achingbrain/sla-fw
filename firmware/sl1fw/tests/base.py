# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import sys
import tempfile
import threading
from pathlib import Path

import pydbus
from PIL import Image, ImageChops
from dbusmock import DBusTestCase
from gi.repository import GLib
from mock import Mock

import sl1fw.tests.mocks.mc_port
from sl1fw import defines
from sl1fw.tests import samples
from sl1fw.tests.mocks.dbus.hostname import Hostname
from sl1fw.tests.mocks.dbus.locale import Locale
from sl1fw.tests.mocks.dbus.networkmanager import NetworkManager
from sl1fw.tests.mocks.dbus.rauc import Rauc
from sl1fw.tests.mocks.dbus.timedate import TimeDate
from sl1fw.tests.mocks.gettext import fake_gettext

fake_gettext()
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.DEBUG)

sys.modules['gpio'] = Mock()
sys.modules['serial'] = sl1fw.tests.mocks.mc_port


class Sl1fwTestCase(DBusTestCase):
    SL1FW_DIR = Path(sl1fw.__file__).parent
    SAMPLES_DIR = Path(samples.__file__).parent
    TEMP_DIR = Path(tempfile.gettempdir())
    EEPROM_FILE = Path.cwd() / "EEPROM.dat"

    dbus_mocks = []
    event_loop = GLib.MainLoop()
    event_thread: threading.Thread = None

    @classmethod
    def setUpClass(cls):
        defines.testing = True
        defines.ramdiskPath = str(cls.TEMP_DIR)
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(system_bus=True)

        bus = pydbus.SystemBus()
        nm = NetworkManager()
        cls.dbus_mocks = [
            bus.publish(NetworkManager.__INTERFACE__, nm, ("Settings", nm), ("test1", nm), ("test2", nm), ("test3", nm)),
            bus.publish(Hostname.__INTERFACE__, Hostname()),
            bus.publish(Rauc.__OBJECT__, ("/", Rauc())),
            bus.publish(Locale.__INTERFACE__, Locale()),
            bus.publish(TimeDate.__INTERFACE__, TimeDate()),
        ]

        cls.event_thread = threading.Thread(target=cls.event_loop.run)
        cls.event_thread.start()

    @classmethod
    def tearDownClass(cls):
        for dbus_mock in cls.dbus_mocks:
            dbus_mock.unpublish()

        cls.event_loop.quit()
        cls.event_thread.join()

    @staticmethod
    def compareImages(path1: str, path2: str) -> bool:
        one = Image.open(path1)
        two = Image.open(path2)
        diff = ImageChops.difference(one, two)
        return diff.getbbox() is not None
