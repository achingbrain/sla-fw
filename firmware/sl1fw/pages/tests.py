# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.pages import page
from sl1fw.libPages import Page, PageWait


@page
class PageTests(Page):
    Name = "tests"

    def __init__(self, display):
        super(PageTests, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Tests")
    #enddef


    def show(self):
        self.items.update({
                'button1' : _("Resin sensor test"),
                'button2' : _("Fan test"),

                'button15' : _("Raise exception"),
                })
        super(PageTests, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button1Continue,
                text = _("Is there the correct amount of resin in the tank?\n\n"
                    "Is the tank secured with both screws?"))
        return "yesno"
    #enddef


    def button1Continue(self):
        # TODO vyzadovat zavreny kryt po celou dobu!
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Moving platform to the top"))
        pageWait.show()
        retc = self._syncTower()
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line1 = _("Tilt home"), line2 = "")
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.setTiltProfile('layerMoveSlow')
        self.display.hw.tiltUpWait()

        pageWait.showItems(line1 = _("Measuring"), line2 = _("Do NOT TOUCH the printer"))
        volume = self.display.hw.getResinVolume()
        self.display.hw.powerLed("normal")
        if not volume:
            self.display.pages['error'].setParams(
                    text = _("Resin measuring failed!\n\n"
                        "Is there the correct amount of resin in the tank?\n\n"
                        "Is the tank secured with both screws?"))
            return "error"
        #endif

        self.display.pages['confirm'].setParams(
                continueFce = self.backButtonRelease,
                text = _("Measured resin volume: %d ml") % volume)
        return "confirm"
    #enddef


    def button2ButtonRelease(self):
        return "fantest"
    #enddef


    def button15ButtonRelease(self):
        raise Exception("Test problem")
    #enddef

#endclass
