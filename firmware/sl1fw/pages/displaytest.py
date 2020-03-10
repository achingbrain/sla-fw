# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-instance-attributes

from sl1fw.states.display import DisplayState
from sl1fw.functions import display_test
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageDisplayTest(Page):
    Name = "displaytest"

    def __init__(self, display):
        super(PageDisplayTest, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Display test")
        self.stack = False
        self.checkPowerbutton = False
        self.checkCover = True
        self.checkCoverWarnOnly = False
        self.checkCoverUVOn = True
        self.checkCooling = True
    #enddef


    def show(self):
        display_test.start(self.display)
        self.items.update({
            'imageName' : "selftest-prusa_logo.jpg",
            'text' : _("Can you see the company logo on the exposure display through the orange cover?\n\n"
                       "Tip: The logo is best seen when you look from above.\n\n"
                       "DO NOT open the cover!")})
        if display_test.cover_check(self.display):
            super(PageDisplayTest, self).show()
        #endif
    #enddef


    def yesButtonRelease(self):
        self.display.state = DisplayState.IDLE
        return "_OK_"
    #enddef


    def noButtonRelease(self):
        self.display.state = DisplayState.IDLE
        self.display.pages['error'].setParams(
            text = _("Your display is probably broken.\n\n"
                     "Please contact tech support!"))
        return "error"
    #enddef


    def leave(self):
        display_test.end(self.display)
    #enddef

#endclass
