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

    @staticmethod
    def uvcalibrationButtonRelease():
        return "uvcalibration"
    #enddef
#endclass
