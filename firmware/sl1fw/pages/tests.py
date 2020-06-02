# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait
from sl1fw.pages.infinitetest import PageInfiniteTest


@page
class PageTests(Page):
    Name = "tests"

    def __init__(self, display):
        super(PageTests, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Tests"
    #enddef


    def show(self):
        self.items.update({
                'button1' : "Resin sensor test",
                'button2' : "UV & Fan test",
                'button3' : "Tower sensitivity",

                'button6' : "Infinite test",
                'button15' : "Raise exception",
                })
        super(PageTests, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button1Continue,
                text = "Is there the correct amount of resin in the tank?\n\n"
                    "Is the tank secured with both screws?")
        return "yesno"
    #enddef


    def button1Continue(self):
        # TODO vyzadovat zavreny kryt po celou dobu!
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = "Moving platform to the top")
        pageWait.show()
        retc = self._syncTower()
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line1 = "Tilt home", line2 = "")
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.setTiltProfile('layerMoveSlow')
        self.display.hw.tiltUpWait()

        pageWait.showItems(line1 = "Measuring", line2 = "Do NOT TOUCH the printer")
        volume = self.display.hw.getResinVolume()
        self.display.hw.powerLed("normal")
        if not volume:
            self.display.pages['error'].setParams(
                    text = "Resin measuring failed!\n\n"
                        "Is there the correct amount of resin in the tank?\n\n"
                        "Is the tank secured with both screws?")
            return "error"
        #endif

        self.display.pages['confirm'].setParams(
                continueFce = self.backButtonRelease,
                text = "Measured resin volume: %d ml" % volume)
        return "confirm"
    #enddef


    @staticmethod
    def button2ButtonRelease():
        return "uvfanstest"
    #enddef


    def button6ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return PageInfiniteTest.Name
    #enddef


    @staticmethod
    def button15ButtonRelease():
        raise Exception("Test problem")
    #enddef

#endclass
