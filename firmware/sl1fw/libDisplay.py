# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os, sys
import logging
from time import sleep
from time import monotonic

from sl1fw import defines
from sl1fw import libPages
from sl1fw.libConfig import WizardData
from sl1fw.pages import * # pylint: disable=unused-import


class Display(object):

    def __init__(self, hwConfig, config, devices, hw, inet, screen):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.config = config
        self.devices = devices
        self.show_admin = bool(hwConfig.factoryMode)
        self.hw = hw
        self.inet = inet
        self.screen = screen
        self.wizardData = WizardData(defines.wizardDataFile)

        # Instantiate pages
        self.pages = {}
        for page, page_class in libPages.page.getpages().items():
            self.pages[page] = page_class(self)
        #endfor

        self.actualPage = self.pages['start']

        self.fanErrorOverride = False
        self.checkCoolingExpo = True
        self.backActions = set(("_EXIT_", "_BACK_", "_OK_", "_NOK_"))
        self.waitPageItems = None
        self.netState = None
        self.forcedPage = None
    #enddef


    def __del__(self):
        self.exit()
    #enddef


    def exit(self):
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
        self.netState = value
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
                    return (event.get('id', None), event.get('pressed', None), event.get('data', None))
                #endif
                self.logger.warning("event page (%s) and actual page (%s) differ", event['page'], actualPage.pageUI)
            elif event.get('client_type', None) == "prusa_sla_client_qt":
                self.pages['sysinfo'].setItems(qt_gui_version = event.get('client_version', _("unknown")))
            #endif
        #endfor
        return (None, None, None)
    #enddef


    def doMenu(self, startPage):
        pageStack = list()
        actualPage = self._setPage(startPage)
        autorepeatFce = None
        autorepeatDelay = 1
        callbackTime = 0.0  # call the callback immediately
        updateDataTime = callbackTime
        while True:

            if self.forcedPage is not None:
                actualPage = self.forcedPage
                self.forcedPage = None
            #enddef

            if self.netState is not None:
                actualPage.netChange()
                self.netState = None
            #endif

            now = monotonic()

            if actualPage.callbackPeriod and now - callbackTime > actualPage.callbackPeriod:
                callbackTime = now
                newPage = actualPage.callback()
                if newPage == "_EXIT_":
                    break
                elif newPage is not None:
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
                        self.hw.beepEcho()
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
                    self.hw.beepEcho()
                    submitFce = getattr(actualPage, button + "ButtonSubmit", None)
                    releaseFce = getattr(actualPage, button + "ButtonRelease", actualPage.emptyButtonRelease)
                    if submitFce:
                        newPage = submitFce(data)
                    elif releaseFce:
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
                            if len(pageStack):
                                actualPage = pageStack.pop()
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
                            libPages.PageWait(self, **self.waitPageItems).show()
                            self.waitPageItems = None
                        else:
                            actualPage.show()
                        #endif
                        continue
                    elif newPage is not None:
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


    # TODO presunout pryc
    def shutDown(self, doShutDown, reboot=False):
        self.forcePage("start")
        self.hw.uvLed(False)
        self.hw.motorsRelease()

        if doShutDown:
            if reboot:
                self.logger.debug("reboot")
                os.system("reboot")
            else:
                self.hw.shutdown()
                self.logger.debug("poweroff")
                os.system("poweroff")
        #endif

        self.screen.exit()
        self.inet.exit()
        self.hw.exit()
        self.exit()
        sys.exit()
    #enddef

#endclass
