# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.errors.errors import TowerHomeFailure, TiltHomeFailure
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageControl(Page):
    Name = "control"

    def __init__(self, display):
        super(PageControl, self).__init__(display)
        self.pageUI = "control"
    #enddef


    def topButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Moving platform to the top"))
        pageWait.show()
        try:
            self.display.hw.tower_home()
        except TowerHomeFailure:
            self.logger.exception("Tower homing failed")
            self.display.pages['error'].setParams(text=_("Tower homing failed!\n\nCheck the printer's hardware."))
            return "error"
        return "_SELF_"
    #enddef


    def tankresButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Tank reset"))
        pageWait.show()
        try:
            self.display.hw.tilt_home()
        except TiltHomeFailure:
            self.logger.exception("Tank homing failed")
            self.display.pages['error'].setParams(text=_("Tank homing failed!\n\nCheck the printer's hardware."))
            return "error"
        return "_SELF_"
    #enddef


    def disablesteppersButtonRelease(self):
        self.display.hw.motorsRelease()
    #enddef

#endclass
