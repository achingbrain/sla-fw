# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.pages import page
from sl1fw.libPages import Page
from sl1fw.pages.calibration import PageCalibrationStart


@page
class PageHome(Page):
    Name = "home"

    def __init__(self, display):
        super(PageHome, self).__init__(display)
        self.pageUI = "home"
        self.pageTitle = N_("Home")
        # meni se i z PageFinished!
        self.readyBeep = True
    #enddef


    def show(self):
        super(PageHome, self).show()
        if self.readyBeep:
            self.display.hw.beepRepeat(2)
            self.readyBeep = False
        #endif
    #enddef


    def controlButtonRelease(self):
        return "control"
    #enddef


    def settingsButtonRelease(self):
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

        return "sourceselect"
    #enddef


    def showWizard(self):
        return "wizardinit"
    #enddef


    def printContinue(self):
        return PageCalibrationStart.Name
    #enddef

#endclass
