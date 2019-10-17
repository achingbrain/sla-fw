# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageFeedMe(Page):
    Name = "feedme"

    def __init__(self, display):
        super(PageFeedMe, self).__init__(display)
        self.pageUI = "feedme"
        self.pageTitle = N_("Feed me")
        self.manual = False
        self.checkCoverOveride = True
    #enddef


    def show(self):
        super(PageFeedMe, self).show()
        self.display.hw.powerLed("error")
    #enddef


    def backButtonRelease(self):
        self.display.hw.powerLed("normal")
        if not self.manual:
            self.display.expo.setResinVolume(None)
        #endif
        self.display.expo.doBack()
        return "_SELF_"
    #enddef


    def refilledButtonRelease(self):
        self.display.hw.powerLed("normal")
        self.display.expo.setResinVolume(defines.resinFilled)
        self.display.expo.doContinue()
        return "_SELF_"
    #enddef

#endclass
