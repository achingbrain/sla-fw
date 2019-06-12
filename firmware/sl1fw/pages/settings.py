from sl1fw.libPages import page, Page
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
        self.display.pages['confirm'].setParams(
            continueFce = self.calibrateContinue,
            text = _("Calibrate printer now?"))
        return "confirm"
    #enddef


    def advancedsettingsButtonRelease(self):
        return "advancedsettings"
    #enddef


    def supportButtonRelease(self):
        return "support"
    #enddef


    def calibrateContinue(self):
        return "calibration1"
    #enddef

#endclass