# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.pages import page
from sl1fw.states.display import DisplayState
from sl1fw.pages.base import Page


@page
class PageUvDispSettings(Page):
    Name = "uvdispsettings"

    def __init__(self, display):
        super(PageUvDispSettings, self).__init__(display)
        self.pageUI = "uvdispsettings"
    #enddef


    def displaytestButtonRelease(self):
        self.display.state = DisplayState.DISPLAY_TEST
        self.display.pages['confirm'].setParams(
            continueFce = self.displaytestContinue,
            pageTitle = _("Display test"),
            imageName = "selftest-remove_tank.jpg",
            text = _("Please unscrew and remove the resin tank."))
        return "confirm"
    #enddef


    def displaytestContinue(self):
        self.display.pages['confirm'].setParams(
            continueFce = self.displaytest,
            pageTitle = _("Display test"),
            imageName = "close_cover_no_tank.jpg",
            text = _("Please close the orange lid."))
        return "confirm"
    #enddef


    @staticmethod
    def displaytest():
        return "displaytest"
    #endif


    def uvcalibrationButtonRelease(self):
        self.display.pages['uvcalibrationconfirm'].setParams(
            writeDataToFactory = False,
            resetLedCounter = False,
            resetDisplayCounter = False)
        return "uvcalibration"
    #enddef


    def newdisplayButtonRelease(self):
        self.display.pages['confirm'].setParams(
            continueFce = self.newDisplayContinue,
            pageTitle = _("UV calibration"),
            text = _("WARNING! This procedure will rewrite the factory calibration data. Continue ONLY if you installed new print display.\n\n"
                "Do you want to proceed?"))
        return "confirm"
    #enddef

    def newDisplayContinue(self):
        self.display.pages['uvcalibrationconfirm'].setParams(
            writeDataToFactory = True,
            resetDisplayCounter = True)
        return "uvcalibration"

    def newledsetButtonRelease(self):
        self.display.pages['confirm'].setParams(
            continueFce = self.newLedSetContinue,
            pageTitle = _("UV calibration"),
            text = _("WARNING! This procedure will rewrite the factory calibration data. Continue ONLY if you installed new UV LED set.\n\n"
                "Do you want to proceed?"))
        return "confirm"
    #enddef

    def newLedSetContinue(self):
        self.display.pages['uvcalibrationconfirm'].setParams(
            writeDataToFactory = True,
            resetLedCounter = True)
        return "uvcalibration"

#endclass
