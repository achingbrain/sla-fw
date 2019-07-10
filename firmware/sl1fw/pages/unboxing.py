# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from time import sleep

from sl1fw.libPages import page, Page, PageWait


@page
class PageUnboxing1(Page):
    Name = "unboxing1"

    def __init__(self, display):
        super(PageUnboxing1, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing step 1/4")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "16_sticker_open_cover.jpg",
            'text' : _("Please remove the safety sticker on the right and open the orange cover.\n\n"
                "In case you assembled your printer, you can skip this wizard by hitting the Back button.")})
        super(PageUnboxing1, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display)
        pageWait.show()
        if self.display.hwConfig.coverCheck and self.display.hw.isCoverClosed():
            pageWait.showItems(
                    line1 = _("The cover is closed!"),
                    line2 = _("Please remove the safety sticker and open the orange cover."))
            self.display.hw.beepAlarm(3)
            while self.display.hw.isCoverClosed():
                sleep(0.5)
            #endwhile
        #endif
        pageWait.showItems(line1 = _("The printer is moving to allow for easier manipulation"), line2 = "")
        self.display.hw.setTowerPosition(0)
        self.display.hw.setTowerProfile("homingFast")
        self.display.hw.towerMoveAbsolute(self.display.hwConfig.calcMicroSteps(30))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.powerLed("normal")
        return "unboxing2"
    #endif


    def backButtonRelease(self):
        return "unboxingconfirm"
    #enddef


    def _BACK_(self):
        return "wizardinit"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageUnboxing2(Page):
    Name = "unboxing2"

    def __init__(self, display):
        super(PageUnboxing2, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing step 2/4")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "14_remove_foam.jpg",
            'text' : _("Remove the black foam from both sides of the platform.")})
        super(PageUnboxing2, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("The printer is moving to allow for easier manipulation"))
        pageWait.show()
        self.display.hw.towerSyncWait()
        self.display.hw.powerLed("normal")
        return "unboxing3"
    #enddef


    def backButtonRelease(self):
        return "unboxingconfirm"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageUnboxing3(Page):
    Name = "unboxing3"

    def __init__(self, display):
        super(PageUnboxing3, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing step 3/4")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "15_remove_bottom_foam.jpg",
            'text' : _("Unscrew and remove the resin tank and remove the black foam underneath it.")})
        super(PageUnboxing3, self).show()
    #enddef


    def contButtonRelease(self):
        return "unboxing4"
    #enddef


    def backButtonRelease(self):
        return "unboxingconfirm"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageUnboxing4(Page):
    Name = "unboxing4"

    def __init__(self, display):
        super(PageUnboxing4, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing step 4/4")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "17_remove_sticker_screen.jpg",
            'text' : _("Carefully peel off the orange protective foil from the exposition display.")})
        super(PageUnboxing4, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.hwConfig.update(showUnboxing = "no")
        if not self.display.hwConfig.writeFile():
            self.display.pages['error'].setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return "unboxing5"
    #enddef


    def backButtonRelease(self):
        return "unboxingconfirm"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageUnboxing5(Page):
    Name = "unboxing5"

    def __init__(self, display):
        super(PageUnboxing5, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing done")
    #enddef


    def show(self):
        self.items.update({
            'text' : _("The printer is fully unboxed and ready for the selftest.")})
        super(PageUnboxing5, self).show()
    #enddef


    def contButtonRelease(self):
        return "wizardinit"
    #enddef


    def backButtonRelease(self):
        return "_EXIT_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageUnboxingConfirm(Page):
    Name = "unboxingconfirm"

    def __init__(self, display):
        super(PageUnboxingConfirm, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Skip unboxing?")
        self.checkPowerbutton = False
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Do you really want to skip the unboxing wizard?\n\n"
                "Press 'Yes' only in case you've assembled the printer as a kit,"
                " or you went through this wizard previously and the printer is"
                " unpacked.")})
        super(PageUnboxingConfirm, self).show()
    #enddef


    def yesButtonRelease(self):
        self.display.hwConfig.update(showUnboxing = "no")
        if not self.display.hwConfig.writeFile():
            self.display.pages['error'].setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return "_BACK_"
    #enddef


    def noButtonRelease(self):
        return "_NOK_"
    #enddef

#endclass
