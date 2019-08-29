# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageDisplay(Page):
    Name = "display"

    def __init__(self, display):
        super(PageDisplay, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Display")
        self.checkCooling = True
    #enddef


    def show(self):
        state = self.display.hw.getUvLedState()[0]
        self.items.update({
                'button1' : _("Chess 8"),
                'button2' : _("Chess 16"),
                'button3' : _("Grid 8"),
                'button4' : _("Grid 16"),
                'button5' : _("Maze"),

                'button6' : "USB:/test.png",
                'button7' : _("Prusa logo"),
                'button8' : "",
                'button9' : "",
                'button10' : _("Infinite test"),

                'button11' : _("Black"),
                'button12' : _("Inverse"),
                'button13' : "",
                'button14' : _("UV off") if state else _("UV on"),
                'button15' : _("UV calibration"),
                })
        super(PageDisplay, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice8_1440x2560.png"))
    #enddef


    def button2ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice16_1440x2560.png"))
    #enddef


    def button3ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "mrizka8_1440x2560.png"))
    #enddef


    def button4ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "mrizka16_1440x2560.png"))
    #enddef


    def button5ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "bludiste_1440x2560.png"))
    #enddef


    def button6ButtonRelease(self):
        savepath = self.getSavePath()
        if savepath is None:
            self.display.pages['error'].setParams(
                text = _("No USB storage present"))
            return "error"
        #endif

        test_file = os.path.join(savepath, "test.png")

        if not os.path.isfile(test_file):
            self.display.pages['error'].setParams(
                text = _("Cannot find the test image"))
            return "error"
        #endif

        try:
            self.display.screen.getImg(filename = test_file)
        except Exception:
            # TODO: This is not reached. Exceptions from screen do not propagate here
            self.logger.exception("Error displaying test image")
            self.display.pages['error'].setParams(
                text = _("Cannot display the test image"))
            return "error"
        #endtry

    #enddef


    def button7ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "logo_1440x2560.png"))
    #enddef


    def button10ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return "infinitetest"
    #enddef


    def button11ButtonRelease(self):
        self.display.screen.getImgBlack()
    #enddef


    def button12ButtonRelease(self):
        self.display.screen.inverse()
    #enddef


    def button14ButtonRelease(self):
        state = not self.display.hw.getUvLedState()[0]
        self.showItems(button14 = _("UV off") if state else _("UV on"))
        if state:
            self.display.hw.startFans()
            self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
        else:
            self.display.hw.stopFans()
        #endif

        self.display.hw.uvLed(state)
    #enddef


    def button15ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return "uvcalibrationtest"
    #enddef


    def backButtonRelease(self):
        self.display.hw.saveUvStatistics()
        self.allOff()
        return super(PageDisplay, self).backButtonRelease()
    #enddef

#endclass
