# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from time import sleep

from sl1fw.pages import page
from sl1fw.libPages import Page, PageWait


@page
class PageTiltTower(Page):
    Name = "tilttower"

    def __init__(self, display):
        super(PageTiltTower, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Tilt & Tower")
    #enddef


    def show(self):
        self.items.update({
                'button1' : _("Tilt home"),
                'button2' : _("Tilt move"),
                'button3' : _("Tilt test"),
                'button4' : _("Tilt profiles"),
                'button5' : _("Tilt home calib."),

                'button6' : _("Tower home"),
                'button7' : _("Tower move"),
                'button8' : _("Tower test"),
                'button9' : _("Tower profiles"),
                'button10' : _("Tower home calib."),

                'button11' : _("Turn motors off"),
                'button12' : _("Tune tilt"),
                'button13' : "",
                'button14' : _("Tower offset"),
                'button15' : "",
                })
        super(PageTiltTower, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tilt home"))
        pageWait.show()
        retc = self._syncTilt()
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def button2ButtonRelease(self):
        return "tiltmove"
    #enddef


    def button3ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tilt sync"))
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = _("Tilt up"))
        self.display.hw.tiltLayerUpWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = _("Tilt down"))
        self.display.hw.tiltLayerDownWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = _("Tilt up"))
        self.display.hw.tiltLayerUpWait()
        self.display.hw.beepEcho()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button4ButtonRelease(self):
        return "tiltprofiles"
    #enddef


    def button5ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tilt home calibration"))
        pageWait.show()
        self.display.hw.tiltHomeCalibrateWait()
        self.display.hw.motorsRelease()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button6ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Moving platform to the top"))
        pageWait.show()
        retc = self._syncTower(pageWait)
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def button7ButtonRelease(self):
        return "towermove"
    #enddef


    def button8ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Moving platform to the top"))
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line1 = _("Moving platform to zero"))
        self.display.hw.towerToZero()
        while not self.display.hw.isTowerOnZero():
            sleep(0.25)
            pageWait.showItems(line2 = self.display.hw.getTowerPosition())
        #endwhile
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button9ButtonRelease(self):
        return "towerprofiles"
    #enddef


    def button10ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tower home calibration"))
        pageWait.show()
        self.display.hw.towerHomeCalibrateWait()
        self.display.hw.motorsRelease()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button11ButtonRelease(self):
        self.display.hw.motorsRelease()
    #enddef


    def button12ButtonRelease(self):
        return "tunetilt"
    #enddef


    def button13ButtonRelease(self):
        pass
    #enddef


    def button14ButtonRelease(self):
        return "toweroffset"
    #enddef

#endclass
