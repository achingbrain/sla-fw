# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import subprocess
import signal

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageMotionController(Page):
    Name = "motioncontroller"

    def __init__(self, display):
        super(PageMotionController, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Motion Controller")
    #enddef


    def show(self):
        self.items.update({
                'button1' : _("Flash MC"),
                'button2' : _("Erase MC EEPROM"),
                'button3' : _("MC2Net (bootloader)"),
                'button4' : _("MC2Net (firmware)"),
                })
        super(PageMotionController, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button1Continue,
                text = _("This overwrites the motion controller with the selected firmware."))
        return "yesno"
    #enddef


    def button1Continue(self):
        pageWait = PageWait(self.display)
        pageWait.fill(line1=_("Forced update of the motion controller firmware"))
        pageWait.show()
        self.display.hw.flashMC()
        self.display.actualPage.show()
        return "_BACK_"
    #enddef


    def button2ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button2Continue,
                text = _("This will erase all profiles and other motion controller settings."))
        return "yesno"
    #enddef


    def button2Continue(self):
        pageWait = PageWait(self.display, line1 = _("Erasing EEPROM"))
        pageWait.show()
        self.display.hw.eraseEeprom()
        self.display.hw.initDefaults()
        return "_BACK_"
    #enddef


    def button3ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.mc2net,
                yesParams = { 'bootloader' : True },
                text = _("This will disable the GUI and connect the MC bootloader to TCP port."))
        return "yesno"
    #enddef


    def button4ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.mc2net,
                yesParams = { 'bootloader' : False },
                text = _("This will disable the GUI and connect the motion controller to TCP port."))
        return "yesno"
    #enddef


    def mc2net(self, bootloader = False):
        ip = self.display.inet.ip
        if ip == None:
            self.display.pages['error'].setParams(
                    text = _("Not connected to network"))
            return "error"
        #endif

        baudrate = 19200 if bootloader else 115200
        if bootloader:
            self.display.hw.mcc.reset()
        #endif

        self.display.hw.switchToDummy()

        pid = subprocess.Popen([
            defines.Mc2NetCommand,
            defines.motionControlDevice,
            str(defines.socatPort),
            str(baudrate)], preexec_fn=os.setsid).pid

        self.display.pages['confirm'].setParams(
                continueFce = self.mc2netStop,
                continueParams = { 'pid' : pid },
                backFce = self.mc2netStop,
                backParams = { 'pid' : pid },
                text = _("Baudrate is %(br)d.\n\n"
                    "Serial line is redirected to %(ip)s:%(port)d.\n\n"
                    "Press 'Continue' when done.") % { 'br' : baudrate, 'ip' : ip, 'port' : defines.socatPort })
        return "confirm"
    #enddef


    def mc2netStop(self, pid):
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        pageWait = PageWait(self.display)
        pageWait.fill(line1=_("Switching back to real MC"))
        pageWait.show()
        self.display.hw.switchToMC()
        self.display.actualPage.show()
        return "_BACK_"
    #enddef

#endclass
