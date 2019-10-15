# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum, auto
from pathlib import Path

from gi.repository.GLib import timeout_add_seconds
from pydbus.generic import signal

from sl1fw import defines


class DisplayTest0:
    INTERFACE = "cz.prusa3d.sl1.printer0"

    dbus = """
        <node>
            <interface name='%s'>
                <!-- State -->
                <property name="state" type="s" access="read">
                    <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
                </property>
                <method name="finish"/>
            </interface>
        </node>
    """ % INTERFACE

    class State(Enum):
        def _generate_next_value_(self, start, count, last_values):
            return self

        COVER_OPEN = auto()
        DISPLAY = auto()
        FINISHED = auto()

    PropertiesChanged = signal()

    def __init__(self, printer0):
        self.printer0 = printer0
        self._state = self.State.COVER_OPEN
        self.printer0.printer.hw.startFans()
        self.printer0.printer.display.fanErrorOverride = True
        self.printer0.printer.display.screen.getImg(filename=str(Path(defines.dataPath) / "logo_1440x2560.png"))
        timeout_add_seconds(1, self.update_cover)

    def update_cover(self):
        if self._state == self.State.FINISHED:
            return False

        old = self._state
        if not self.printer0.printer.hwConfig.coverCheck or self.printer0.printer.hw.isCoverClosed():
            self.printer0.printer.hw.uvLed(True)
            self._state = self.State.DISPLAY
        else:
            self.printer0.printer.hw.uvLed(False)
            self._state = self.State.COVER_OPEN
        if old != self._state:
            self.PropertiesChanged(self.INTERFACE, {"state": self.state}, [])

        return True

    @property
    def state(self) -> str:
        return self._state.name

    def finish(self) -> None:
        self.printer0.printer.display.fanErrorOverride = False
        self.printer0.printer.hw.saveUvStatistics()  # TODO: Why ???
        # can't call allOff(), motorsRelease() is harmful for the wizard
        self.printer0.printer.screen.getImgBlack()
        self.printer0.printer.hw.uvLed(False)
        self.printer0.printer.hw.stopFans()

        self._state = self.State.FINISHED
        self.printer0._display_test_registration.unregister()
        self.printer0._display_test_registration = None
        self.printer0._display_test = None
