# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.pages import page
from sl1fw.libPages import Page
from sl1fw.pages.advancedsettings import PageAdvancedSettings


@page
class PageSettings(Page):
    Name = "settings"

    def __init__(self, display):
        super(PageSettings, self).__init__(display)
        self.pageUI = "settings"
        self.pageTitle = N_("Settings")
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


    def advancedsettingsButtonRelease(self):
        return PageAdvancedSettings.Name
    #enddef


    def supportButtonRelease(self):
        return "support"
    #enddef


    def calibrateContinue(self):
        return "calibration1"
    #enddef

#endclass
