from sl1fw.libPages import page, Page
from sl1fw.libPages import PageWait


@page
class PageControl(Page):
    Name = "control"

    def __init__(self, display):
        super(PageControl, self).__init__(display)
        self.pageUI = "control"
        self.pageTitle = N_("Control")
    #enddef


    def show(self):
        self.moving = False
        super(PageControl, self).show()
    #enddef


    def topButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = _("Moving platform to the top"))
        pageWait.show()
        retc = self._syncTower(pageWait)
        self.display.hw.motorsHold()
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def tankresButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = _("Tank reset"))
        pageWait.show()
        # assume tilt is up (there may be error from print)
        self.display.hw.setTiltPosition(self.display.hw._tiltEnd)
        self.display.hw.tiltLayerDownWait(True)
        self.display.hw.tiltSyncWait()
        self.display.hw.tiltLayerUpWait()
        self.display.hw.motorsHold()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def disablesteppersButtonRelease(self):
        self.display.hw.motorsRelease()
    #enddef

#endclass