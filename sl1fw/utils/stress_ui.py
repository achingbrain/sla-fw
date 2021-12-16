# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Thread
from time import sleep

import pydbus
from gi.repository import GLib

from sl1fw.api.exposure0 import Exposure0
from sl1fw.api.printer0 import Printer0
from sl1fw.states.exposure import ExposureState
from sl1fw.tests.mocks.exposure import Exposure
from sl1fw.tests.mocks.printer import Printer

bus = pydbus.SystemBus()

exposure = Exposure()
printer = Printer(exposure)

bus.publish(Printer0.__INTERFACE__, Printer0(printer))
bus.publish(Exposure0.__INTERFACE__, (Exposure0.dbus_path(exposure.instance_id), Exposure0(exposure)))

Thread(target=GLib.MainLoop().run, daemon=True).start()  # type: ignore[attr-defined]

while True:
    for state in ExposureState:
        sleep(0.5)
        print(f"Setting exposure state to {state}")
        exposure.set_state(state)
