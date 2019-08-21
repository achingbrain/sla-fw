# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageDisplayTest(Page):
    Name = "displaytest"

    def __init__(self, display):
        super(PageDisplayTest, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Display test")
        self.stack = False
        self.checkPowerbutton = False
        self.checkCover = True
        self.checkCoverWarnOnly = False
        self.checkCoverUVOn = True
        self.checkCooling = True
    #enddef


    def show(self):
        self.display.fanErrorOverride = True    #do not check fane. overheat check is sufficient
        self.items.update({
            'imageName' : "10_prusa_logo.jpg",
            'text' : _("Can you see company logo on the exposure display through the orange cover?\n\n"
                "Tip: The logo is best seen when you look from above.\n\n"
                "DO NOT open the cover!")})
        if not self.display.hwConfig.coverCheck or self.display.hw.isCoverClosed():
            self.display.hw.uvLed(True)
            super(PageDisplayTest, self).show()
        #endif
        self.display.screen.getImg(filename=os.path.join(defines.dataPath, "logo_1440x2560.png"))
        self.display.hw.startFans()
    #enddef


    def yesButtonRelease(self):
        return "_OK_"
    #enddef


    def noButtonRelease(self):
        self.display.pages['error'].setParams(
            text = _("Your display is probably broken.\n\n"
                "Please contact tech support!"))
        return "error"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def leave(self):
        self.display.fanErrorOverride = False
        self.display.hw.saveUvStatistics()
        # can't call allOff(), motorsRelease() is harmful for the wizard
        self.display.screen.getImgBlack()
        self.display.hw.uvLed(False)
        self.display.hw.stopFans()
    #enddef

#endclass
