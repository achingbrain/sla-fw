# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from sl1fw.libHardware import MotionControllerException
from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageException(Page):
    Name = "exception"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "exception"
        self.pageTitle = N_("System Error")
        self.callbackPeriod = 1
    #enddef


    def show(self) -> None:
        super().show()
        try:
            self.display.hw.powerLed("error")
        except MotionControllerException:
            self.logger.exception("Failed to set power LED mode")
        #endtry
    #enddef


    def callback(self) -> None:
        if self.display.expo and self.display.expo.inProgress():
            return
        #endif

        self.display.hw.uvLed(False)
        self.display.hw.stopFans()
        self.display.hw.motorsRelease()

        if self.display.hw.getPowerswitchState():
            self.display.shutDown(True)
        #endif

        super().show()
    #enddef


    def setParams(self, **kwargs):
        self.items = kwargs
    #enddef


    def exportlogstoflashdiskButtonRelease(self):
        self.saveLogsToUSB()
        return self.Name
    #enddef


    def backButtonRelease(self):
        return self.Name
    #enddef

#endclass
