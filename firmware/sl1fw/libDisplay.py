# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import os, sys
import logging
from time import sleep
import datetime

import defines
import libPages

class Display(object):

    def __init__(self, hwConfig, config, devices, hw, inet, screen):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.config = config
        self.devices = devices
        self.hw = hw
        self.inet = inet
        self.screen = screen
        self.page_confirm = libPages.PageConfirm(self)
        self.page_systemwait = libPages.PageWait(self)
        self.page_intro = libPages.PageIntro(self)
        self.page_start = libPages.PageStart(self)
        self.page_home = libPages.PageHome(self)
        self.page_control = libPages.PageControl(self)
        self.page_settings = libPages.PageSettings(self)
        self.page_print = libPages.PagePrint(self)
        self.page_projsettings = libPages.PageProjSett(self)
        self.page_change = libPages.PageChange(self)
        self.page_sysinfo = libPages.PageSysInfo(self)
        self.page_netinfo = libPages.PageNetInfo(self)
        self.page_about = libPages.PageAbout(self)
        self.page_sourceselect = libPages.PageSrcSelect(self)
        self.page_error = libPages.PageError(self)
        self.page_tilttower = libPages.PageTiltTower(self)
        self.page_display = libPages.PageDisplay(self)
        self.page_admin = libPages.PageAdmin(self)
        self.page_setup = libPages.PageSetup(self)
        self.page_exception = libPages.PageException(self)
        self.page_towermove = libPages.PageTowerMove(self)
        self.page_tiltmove = libPages.PageTiltMove(self)
        self.page_towercalib = libPages.PageTowerCalib(self)
        self.page_tiltcalib = libPages.PageTiltCalib(self)
        self.page_tiltprofiles = libPages.PageTiltProfiles(self)
        self.page_towerprofiles = libPages.PageTowerProfiles(self)
        self.page_fansleds = libPages.PageFansLeds(self)
        self.page_hwinfo = libPages.PageHardwareInfo(self)
        self.page_keyboard = libPages.PageKeyboard(self)
        self.page_networking = libPages.PageNetworking(self)
        self.page_networkstate = libPages.PageNetworkState(self)

        self.noBackPages = set(("error", "confirm"))
        self.actualPage = self.page_intro
    #enddef


    def initExpoPages(self, expo):
        self.page_homeprint = libPages.PageHomePrint(self, expo)
    #enddef


    def setPage(self, page):
        newPage = getattr(self, 'page_' + page, None)
        if newPage is None:
            self.logger.warning("There is no page named '%s'!", page)
        else:
            retc = newPage.prepare()
            if retc:
                self.setPage(retc)
            else:
                self.actualPage = newPage
                self.actualPage.show()
            #endif
        #endif
        return self.actualPage
    #enddef


    def assignNetActive(self, value):
        for device in self.devices:
            device.assignNetActive(value)
        #endfor
        self.actualPage.netChange()
    #enddef


    def getEvent(self):
        for device in self.devices:
            event = device.getEventNoWait()
            if event.get('page', None) is not None:
                if event['page'] == self.actualPage.pageUI:
                    # FIXME nejdrive se vycte drivejsi zarizeni, je to OK?
                    return (event.get('id', None), event.get('pressed', None))
                #endif
                self.logger.warning("event page (%s) and actual page (%s) differ", event['page'], self.actualPage.pageUI)
            #endif
        #endfor
        return (None, None)
    #enddef


    def doMenu(self, startPage, callback = None, callbackPeriod = 0.1):
        self.pageStack = list()
        if startPage is not None:
            self.setPage(startPage)
        #endif
        autorepeatFce = None
        autorepeatDelay = 1
        callbackTimeOld = datetime.datetime.now()
        callbackTime = datetime.datetime.fromtimestamp(0)
        while True:
            now = datetime.datetime.now()

            # old style callbacks (TODO:remove)
            if callback is not None and (now - callbackTimeOld).total_seconds() > callbackPeriod:
                callbackTimeOld = now
                if callback(self.actualPage) == "_EXIT_MENU_":
                    break
                #endif
            #endif

            # new style callbacks
            if self.actualPage.callbackPeriod and (now - callbackTime).total_seconds() > self.actualPage.callbackPeriod:
                callbackTime = now
                if self.actualPage.menuCallback() == "_EXIT_MENU_":
                    break
                #endif
            #endif

            button, pressed = self.getEvent()
            if button is not None:
                if pressed:
                    self.hw.beepEcho()
                #endif
                if button in self.actualPage.autorepeat:
                    if pressed:
                        autorepeatDelay, autorepeatDelayNext = self.actualPage.autorepeat[button]
                        autorepeatFce = getattr(self.actualPage, button + "Button", self.actualPage.emptyButton)
                        autorepeatFce()
                    else:
                        autorepeatFce = None
                        autorepeatDelay = 1
                        releaseFce = getattr(self.actualPage, button + "ButtonRelease", None)
                        if releaseFce:
                            releaseFce()
                        #endif
                    #endif
                elif pressed:
                    pressFce = getattr(self.actualPage, button + "Button", None)
                    if pressFce:
                        pressFce()
                    #endif
                else:
                    newPage = getattr(self.actualPage, button + "ButtonRelease", self.actualPage.emptyButtonRelease)()
                    if newPage == "_BACK_":
                        if not self.goBack():
                            return False
                        #endif
                        autorepeatFce = None
                        autorepeatDelay = 1
                        sleep(0.1)
                        continue
                    elif newPage == "_SELF_":
                        self.actualPage.show()
                        continue
                    elif newPage == "_EXIT_MENU_":
                        return True
                    elif newPage is not None:
                        if self.actualPage.pageUI not in self.noBackPages:
                            self.pageStack.append(self.actualPage)
                        #endif
                        autorepeatFce = None
                        autorepeatDelay = 1
                        self.setPage(newPage)
                    #endif
                #endif
            #endif

            if autorepeatDelay:
                # 1 for normal operation
                sleep(0.1)
            #endif

            if autorepeatFce:
                if autorepeatDelay > 1:
                    autorepeatDelay -= 1
                else:
                    autorepeatDelay = autorepeatDelayNext
                    autorepeatFce()
                #endif
            #endif
        #endwhile
    #enddef


    def goBack(self, count = 1):
        for i in xrange(count):
            if len(self.pageStack):
                self.actualPage = self.pageStack.pop()
            else:
                return False
            #endif
        #endfor
        self.actualPage.show()
        return True
    #enddef


    # TODO presunout pryc
    def shutDown(self, doShutDown):
        self.hw.uvLed(False)
        self.hw.motorsRelease()

        if doShutDown:
            self.hw.shutdown()
            self.logger.debug("poweroff")
            os.system("poweroff")
        #endif

        sys.exit()
    #enddef

#endclass