# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from sl1fw.states.display import DisplayState
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.calibration import PageCalibrationStart
from sl1fw.pages.uvcalibration import PageUvCalibrationStart


@page
class PageHome(Page):
    Name = "home"

    def __init__(self, display):
        super(PageHome, self).__init__(display)
        self.pageUI = "home"
        # meni se i z PageFinished!
        self.readyBeep = True
    #enddef


    def show(self):
        super(PageHome, self).show()

        # This is admin leave detection
        self.display.state = DisplayState.IDLE

        if self.readyBeep:
            self.display.hw.beepRepeat(2)
            self.readyBeep = False
        #endif
    #enddef


    @staticmethod
    def controlButtonRelease():
        return "control"
    #enddef


    @staticmethod
    def settingsButtonRelease():
        return "settings"
    #enddef


    def printButtonRelease(self):
# FIXME temporaily disabled until it works perfectly on all printers
#       if self.display.hwConfig.showWizard:
#           return PageWizardInit.Name
        #endif
        if self.display.hwConfig.uvPwm <= self.getMinPwm():
            return PageUvCalibrationStart.Name
        #endif
        if not self.display.hwConfig.calibrated:
            return PageCalibrationStart.Name
        #endif
        if not self.display.doMenu("sourceselect"):
            return "_EXIT_"
        #endif

        return "printpreviewswipe"
    #enddef

#endclass
