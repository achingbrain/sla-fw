# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from sl1fw.display_state import DisplayState
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.calibration import PageCalibrationStart


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
#        if self.display.hwConfig.showWizard:
#            self.display.pages['yesno'].setParams(
#                    pageTitle = N_("Go through wizard?"),
#                    yesFce = self.showWizard,
#                    text = _("Printer needs to be set up!\n\n"
#                        "Go through wizard now?"))
#            return "yesno"
        #endif
        if not self.display.hwConfig.calibrated:
            self.display.pages['yesno'].setParams(
                    pageTitle = N_("Calibrate now?"),
                    yesFce = self.printContinue,
                    text = _("Printer is not calibrated!\n\n"
                        "Calibrate now?"))
            return "yesno"
        #endif

        if not self.display.doMenu("sourceselect"):
            return "_EXIT_"
        #endif

        return "printpreviewswipe"
    #enddef


    @staticmethod
    def showWizard():
        return "wizardinit"
    #enddef


    @staticmethod
    def printContinue():
        return PageCalibrationStart.Name
    #enddef

#endclass
