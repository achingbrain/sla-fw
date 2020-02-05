# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.advancedsettings import PageAdvancedSettings
from sl1fw.pages.calibration import PageCalibrationStart


@page
class PageSettings(Page):
    Name = "settings"

    def __init__(self, display):
        super(PageSettings, self).__init__(display)
        self.pageUI = "settings"
    #enddef


    def networkButtonRelease(self):
        return "network"
    #enddef


    def recalibrationButtonRelease(self):
        self.display.pages['yesno'].setParams(
            yesFce = self.calibrateContinue,
            text = _("Calibrate printer now?"))
        return "yesno"
    #enddef


    @staticmethod
    def advancedsettingsButtonRelease():
        return PageAdvancedSettings.Name
    #enddef


    @staticmethod
    def supportButtonRelease():
        return "support"
    #enddef


    @staticmethod
    def calibrateContinue():
        return PageCalibrationStart.Name
    #enddef

#endclass
