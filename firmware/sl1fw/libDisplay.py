# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import sys
from time import monotonic
from time import sleep
from typing import Optional, List

from sl1fw import defines
from sl1fw.libConfig import HwConfig
from sl1fw.libExposure import Exposure
from sl1fw.libHardware import Hardware
from sl1fw.libNetwork import Network
from sl1fw.libScreen import Screen
from sl1fw.libVirtualDisplay import VirtualDisplay
from sl1fw.pages import pages
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


class Display:

    def __init__(self, hwConfig: HwConfig, devices: List[VirtualDisplay], hw: Hardware, inet: Network, screen: Screen, factory_mode: bool):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.devices = devices
        self.show_admin = factory_mode
        self.hw = hw
        self.inet = inet
        self.screen = screen
        self.factory_mode = factory_mode
        self.wizardData = None
        self.uvcalibData = None
        self.expo: Optional[Exposure] = None
        self.running = False

        # Instantiate pages
        self.pages = {}
        for page, page_class in pages.items():
            self.pages[page] = page_class(self)
        #endfor

        self.actualPageStack = None
        self.actualPage: Page = self.pages['start']

        self.fanErrorOverride = False
        self.checkCoolingExpo = True
        self.backActions = {"_EXIT_", "_BACK_", "_OK_", "_NOK_"}
        self.waitPageItems = None
        self.forcedPage = None

        self.inet.register_net_change_handler(self.assignNetActive)
    #enddef


    def start(self):
        self.running = True
        for device in self.devices:
            device.start()
        #endfor
    #enddef


    def exit(self):
        self.running = False
        for device in self.devices:
            device.exit()
        #endfor
    #enddef


    def initExpo(self, expo):
        # TODO remove cyclic dependency
        self.expo = expo
    #enddef


    def forcePage(self, page):
        self.forcedPage = self._setPage(page)
    #endef


    def _setPage(self, page):
        if page not in self.pages:
            self.logger.warning("There is no page named '%s'!", page)
        else:
            newPage = self.pages[page]
            retc = newPage.prepare()
            if retc:
                self._setPage(retc)
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


    def setWaitPage(self, **items):
        self.waitPageItems = items
    #enddef


    def getEvent(self, actualPage):
        for device in self.devices:
            event = device.getEventNoWait()
            if event.get('page', None) is not None:
                if event['page'] == actualPage.pageUI:
                    # FIXME nejdrive se vycte drivejsi zarizeni, je to OK?
                    return event.get('id', None), event.get('pressed', None), event.get('data', None)
                #endif
                self.logger.warning("event page (%s) and actual page (%s) differ", event['page'], actualPage.pageUI)
            elif event.get('client_type', None) == "prusa_sla_client_qt":
                self.pages['sysinfo'].setItems(qt_gui_version = event.get('client_version', _("unknown")))
            #endif
        #endfor
        return None, None, None
    #enddef


    def doMenu(self, startPage):
        pageStack = list()
        self.actualPageStack = pageStack
        actualPage = self._setPage(startPage)
        autorepeatFce = None
        autorepeatDelay = 1
        autorepeatDelayNext = 1
        callbackTime = 0.0  # call the callback immediately
        updateDataTime = callbackTime
        while self.running:
            if self.forcedPage is not None:
                actualPage = self.forcedPage
                self.forcedPage = None
            #enddef

            now = monotonic()

            if actualPage.callbackPeriod and now - callbackTime > actualPage.callbackPeriod:
                callbackTime = now
                newPage = actualPage.callback()
                if newPage is not None:
                    if actualPage.stack:
                        pageStack.append(actualPage)
                    #endif
                    actualPage = self._setPage(newPage)
                    continue
                #endif
            #endif

            if actualPage.updateDataPeriod and now - updateDataTime > actualPage.updateDataPeriod:
                updateDataTime = now
                actualPage.updateData()
            #endif

            button, pressed, data = self.getEvent(actualPage)
            if button is not None:
                if button in actualPage.autorepeat:
                    if pressed:
                        autorepeatDelay, autorepeatDelayNext = actualPage.autorepeat[button]
                        autorepeatFce = getattr(actualPage, button + "Button", actualPage.emptyButton)
                        autorepeatFce()
                    else:
                        autorepeatFce = None
                        autorepeatDelay = 1
                        submitFce = getattr(actualPage, button + "ButtonSubmit", None)
                        releaseFce = getattr(actualPage, button + "ButtonRelease", None)
                        if submitFce:
                            submitFce(data)
                        elif releaseFce:
                            releaseFce()
                        #endif
                    #endif
                elif pressed:
                    pressFce = getattr(actualPage, button + "Button", None)
                    if pressFce:
                        pressFce()
                    #endif
                else:
                    submitFce = getattr(actualPage, button + "ButtonSubmit", None)
                    releaseFce = getattr(actualPage, button + "ButtonRelease", actualPage.emptyButtonRelease)
                    if submitFce:
                        newPage = submitFce(data)
                    else:
                        newPage = releaseFce()
                    #endif

                    if newPage is not None and newPage != "_SELF_":
                        actualPage.leave()
                    #endif

                    if newPage in self.backActions:
                        autorepeatFce = None
                        autorepeatDelay = 1
                        sleep(0.1)
                        while newPage in self.backActions:
                            if pageStack:
                                actualPage = pageStack.pop()
                                self.actualPage = actualPage
                            elif newPage == "_OK_":
                                return True
                            else:
                                return False
                            #endif
                            np = None
                            backFce = getattr(actualPage, newPage, None)
                            if backFce:
                                np = backFce()
                            #endif
                            newPage = np
                        #endwhile
                        actualPage.show()
                    #endif
                    if newPage == "_SELF_":
                        if self.waitPageItems:
                            PageWait(self, **self.waitPageItems).show()
                            self.waitPageItems = None
                        else:
                            actualPage.show()
                        #endif
                        continue
                    elif newPage is not None:
                        if actualPage.clearStack:
                            pageStack = list()
                        #endif
                        if actualPage.stack:
                            pageStack.append(actualPage)
                        #endif
                        autorepeatFce = None
                        autorepeatDelay = 1
                        actualPage = self._setPage(newPage)
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


    @staticmethod
    def makeWait(*args, **kwargs) -> PageWait:
        return PageWait(*args, **kwargs)
    #enddef


    # TODO presunout pryc
    def shutDown(self, doShutDown, reboot=False):
        if defines.testing:
            self.logger.info("Skipping poweroff due to testing")
            return
        #endif

        self.forcePage("start")
        self.hw.uvLed(False)
        self.hw.motorsRelease()

        if doShutDown:
            if reboot:
                os.system("reboot")
            else:
                self.hw.shutdown()
                os.system("poweroff")
        #endif

        self.screen.exit()
        self.hw.exit()
        self.exit()
        sys.exit()
    #enddef

#endclass
