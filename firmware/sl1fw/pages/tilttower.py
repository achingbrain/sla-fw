# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from time import sleep

from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageTiltTower(Page):
    Name = "tilttower"

    def __init__(self, display):
        super(PageTiltTower, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Tilt & Tower"
    #enddef


    def show(self):
        self.items.update({
                'button1' : "Tilt home",
                'button2' : "Tilt move",
                'button3' : "Tilt test",
                'button4' : "Tilt profiles",
                'button5' : "Tilt home calib.",

                'button6' : "Tower home",
                'button7' : "Tower move",
                'button8' : "Tower test",
                'button9' : "Tower profiles",
                'button10' : "Tower home calib.",

                'button11' : "Turn motors off",
                'button12' : "Tune tilt",
                'button13' : "",
                'button14' : "Tower offset",
                'button15' : "",
                })
        super(PageTiltTower, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = "Tilt home")
        pageWait.show()
        retc = self._syncTilt()
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def button2ButtonRelease(self):
        return "tiltmove"
    #enddef


    def button3ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = "Tilt sync")
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = "Tilt up")
        self.display.hw.tiltLayerUpWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = "Tilt down")
        self.display.hw.tiltLayerDownWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = "Tilt up")
        self.display.hw.tiltLayerUpWait()
        self.display.hw.beepEcho()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button4ButtonRelease(self):
        return "tiltprofiles"
    #enddef


    def button5ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = "Tilt home calibration")
        pageWait.show()
        self.display.hw.tiltHomeCalibrateWait()
        self.display.hw.motorsRelease()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button6ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = "Moving platform to the top")
        pageWait.show()
        retc = self._syncTower()
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def button7ButtonRelease(self):
        return "towermove"
    #enddef


    def button8ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = "Moving platform to the top")
        pageWait.show()
        retc = self._syncTower()
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line1 = "Moving platform to zero")
        self.display.hw.towerToZero()
        while not self.display.hw.isTowerOnZero():
            sleep(0.25)
            pageWait.showItems(line2 = self.display.hw.getTowerPosition())
        #endwhile
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button9ButtonRelease(self):
        return "towerprofiles"
    #enddef


    def button10ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = "Tower home calibration")
        pageWait.show()
        self.display.hw.towerHomeCalibrateWait()
        self.display.hw.motorsRelease()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button11ButtonRelease(self):
        self.display.hw.motorsRelease()
    #enddef


    def button12ButtonRelease(self):
        return "tunetilt"
    #enddef


    def button13ButtonRelease(self):
        pass
    #enddef


    def button14ButtonRelease(self):
        return "toweroffset"
    #enddef

#endclass
