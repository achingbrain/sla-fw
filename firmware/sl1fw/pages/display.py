# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=inconsistent-return-statements
# pylint: disable=too-many-public-methods

import os

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.uvcalibration import PageUvDataShowFactory, PageUvDataShow, PageUvCalibration


@page
class PageDisplay(Page):
    Name = "display"

    def __init__(self, display):
        super(PageDisplay, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Display"
        self.checkCooling = True
    #enddef


    def show(self):
        state = self.display.hw.getUvLedState()[0]
        self.items.update({
                'button1' : "Chess 8",
                'button2' : "Chess 16",
                'button3' : "Grid 8",
                'button4' : "Grid 16",
                'button5' : "Maze",

                'button6' : "USB:/test.png",
                'button7' : "Prusa logo",
                'button8' : "Black",
                'button9' : "Inverse",
                'button10' : "UV off" if state else "UV on",

                'button11' : "Erase UV LED counter",
                'button13' : "Show factory UV c.d.",
                'button14' : "Show UV calib. data",
                'button15' : "UV (re)calibration",
                })
        super(PageDisplay, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice8_1440x2560.png"))
    #enddef


    def button2ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice16_1440x2560.png"))
    #enddef


    def button3ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "mrizka8_1440x2560.png"))
    #enddef


    def button4ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "mrizka16_1440x2560.png"))
    #enddef


    def button5ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "bludiste_1440x2560.png"))
    #enddef


    def button6ButtonRelease(self):
        savepath = self.getSavePath()
        if savepath is None:
            self.display.pages['error'].setParams(
                text = "No USB storage present")
            return "error"
        #endif

        test_file = os.path.join(savepath, "test.png")

        if not os.path.isfile(test_file):
            self.display.pages['error'].setParams(
                text = "Cannot find the test image")
            return "error"
        #endif

        try:
            self.display.screen.getImg(filename = test_file)
        except Exception:
            # TODO: This is not reached. Exceptions from screen do not propagate here
            self.logger.exception("Error displaying test image")
            self.display.pages['error'].setParams(
                text = "Cannot display the test image")
            return "error"
        #endtry

    #enddef


    def button7ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "logo_1440x2560.png"))
    #enddef


    def button8ButtonRelease(self):
        self.display.screen.getImgBlack()
    #enddef


    def button9ButtonRelease(self):
        self.display.screen.inverse()
    #enddef


    def button10ButtonRelease(self):
        state = not self.display.hw.getUvLedState()[0]
        self.showItems(button10 = "UV off" if state else "UV on")
        if state:
            self.display.hw.startFans()
            self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
        else:
            self.display.hw.stopFans()
        #endif

        self.display.hw.uvLed(state)
    #enddef


    def button11ButtonRelease(self):
        seconds = self.display.hw.getUvStatistics()[0]
        self.logger.debug("seconds %s", self.display.hw.getUvStatistics())
        self.display.pages['confirm'].setParams(
            continueFce = self.continueClearUvCounter,
            pageTitle = "Erase UV LED counter",
            text = "Do you really want to clear the UV LED counter?\n\n"
                "UV counter: %(hours).0fh %(minutes).0fm\n"
                "Serial number: %(sn)s\n"
                "IP address: %(ip)s" % {
                    "hours" : seconds / 3600,
                    "minutes": (seconds % 3600) / 60,
                    "sn" : self.display.hw.cpuSerialNo,
                    "ip" : self.display.inet.ip})
        return "confirm"
    #enddef


    def continueClearUvCounter(self):
        self.display.hw.clearUvStatistics()
        seconds = self.display.hw.getUvStatistics()[0]
        self.display.pages['confirm'].setParams(
            pageTitle = "Erase UV LED counter",
            text = "UV counter has been erased.\n\n"
                "UV counter: %(hours).0fh %(minutes).0fm\n"
                "Serial number: %(sn)s\n"
                "IP address: %(ip)s" % {
                    "hours" : seconds / 3600,
                    "minutes": (seconds % 3600) / 60,
                    "sn" : self.display.hw.cpuSerialNo,
                    "ip" : self.display.inet.ip})
        return "confirm"
    #enddef



    @staticmethod
    def success():
        return "_BACK_"
    #enddef


    def button13ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return PageUvDataShowFactory.Name
    #enddef


    def button14ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return PageUvDataShow.Name
    #enddef


    def button15ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return PageUvCalibration.Name
    #enddef


    def backButtonRelease(self):
        self.display.hw.saveUvStatistics()
        self.allOff()
        return super(PageDisplay, self).backButtonRelease()
    #enddef

#endclass
