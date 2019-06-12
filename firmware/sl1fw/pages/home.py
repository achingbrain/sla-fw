from sl1fw.libPages import Page, page


@page
class PageHome(Page):
    Name = "home"

    def __init__(self, display):
        super(PageHome, self).__init__(display)
        self.pageUI = "home"
        self.pageTitle = N_("Home")
        # meni se i z libPrinter!
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
#            self.display.pages['confirm'].setParams(
#                    continueFce = self.showWizard,
#                    text = _("""Printer needs to be set up!
#
#Go through wizard now?"""))
#            return "confirm"
        #endif
        if not self.display.hwConfig.calibrated:
            self.display.pages['confirm'].setParams(
                    continueFce = self.printContinue,
                    text = _("""Printer is not calibrated!

Calibrate now?"""))
            return "confirm"
        #endif

        return "sourceselect"
    #enddef


    def showWizard(self):
        return "wizard1"
    #enddef


    def printContinue(self):
        return "calibration1"
    #enddef

#endclass
