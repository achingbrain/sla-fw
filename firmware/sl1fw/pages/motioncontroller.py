# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageMotionController(Page):
    Name = "motioncontroller"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Motion Controller"
    #enddef


    def show(self):
        self.items.update({
                'button1' : "Flash MC",
                'button2' : "Erase MC EEPROM",
                'button3' : "MC2Net (bootloader)",
                'button4' : "MC2Net (firmware)",
                })
        super(PageMotionController, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button1Continue,
                text = "This overwrites the motion controller with the selected firmware.")
        return "yesno"
    #enddef


    def button1Continue(self):
        pageWait = PageWait(self.display)
        pageWait.fill(line1="Forced update of the motion controller firmware")
        pageWait.show()
        self.display.hw.flashMC()
        self.display.actualPage.show()
        return "_BACK_"
    #enddef


    def button2ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button2Continue,
                text = "This will erase all profiles and other motion controller settings.")
        return "yesno"
    #enddef


    def button2Continue(self):
        pageWait = PageWait(self.display, line1 = "Erasing EEPROM")
        pageWait.show()
        self.display.hw.eraseEeprom()
        self.display.hw.initDefaults()
        return "_BACK_"
    #enddef


    def button3ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.mc2net,
                yesParams = { 'bootloader' : True },
                text = "This will freeze the printer and connect the MC bootloader to TCP port.")
        return "yesno"
    #enddef


    def button4ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.mc2net,
                yesParams = { 'bootloader' : False },
                text = "This will connect the motion controller to TCP port.")
        return "yesno"
    #enddef


    def mc2net(self, bootloader=False):
        ip = self.display.inet.ip
        if ip is None:
            self.display.pages['error'].setParams(text="Not connected to network")
            return "error"

        self.display.hw.mcc.start_debugging(bootloader=bootloader)

        self.display.pages['confirm'].setParams(
            text="Listening for motion controller debugging connection.\n\n"
                 "Serial line is redirected to %(ip)s:%(port)d.\n\n"
                 "Press continue to use the printer. The debugging will begin with new connection"
                 "and will end as soon as the connection terminates." % {'ip': ip,
                                                                         'port': defines.mc_debug_port}
        )
        return "confirm"
    #enddef

#endclass
