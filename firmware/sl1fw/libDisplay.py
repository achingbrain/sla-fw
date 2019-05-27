# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os, sys
import logging
from time import sleep
# Python 2/3 imports
try:
    from time import monotonic
except ImportError:
    # TODO: Remove once we accept Python 3
    from monotonic import monotonic
#endtry

from sl1fw import defines
from sl1fw import libPages
from sl1fw.libConfig import WizardData

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
        self.page_confirm = libPages.PageConfirm(self)
        self.page_yesno = libPages.PageYesNo(self)
        self.page_start = libPages.PageStart(self)
        self.page_home = libPages.PageHome(self)
        self.page_control = libPages.PageControl(self)
        self.page_settings = libPages.PageSettings(self)
        self.page_advancedsettings = libPages.PageAdvancedSettings(self)
        self.page_factoryreset = libPages.PageFactoryReset(self)
        self.page_timesettings = libPages.PageTimeSettings(self)
        self.page_settime = libPages.PageSetTime(self)
        self.page_setdate = libPages.PageSetDate(self)
        self.page_settimezone = libPages.PageSetTimezone(self)
        self.page_sethostname = libPages.PageSetHostname(self)
        self.page_setlanguage = libPages.PageSetLanguage(self)
        self.page_change = libPages.PageChange(self)
        self.page_sysinfo = libPages.PageSysInfo(self)
        self.page_netinfo = libPages.PageNetInfo(self)
        self.page_about = libPages.PageAbout(self)
        self.page_sourceselect = libPages.PageSrcSelect(self)
        self.page_error = libPages.PageError(self)
        self.page_tilttower = libPages.PageTiltTower(self)
        self.page_display = libPages.PageDisplay(self)
        self.page_uvcalibrationtest = libPages.PageUvCalibrationTest(self)
        self.page_uvcalibration = libPages.PageUvCalibration(self)
        self.page_uvcalibrationconfirm = libPages.PageUvCalibrationConfirm(self)
        self.page_uvmeter = libPages.PageUvMeter(self)
        self.page_uvmetershow = libPages.PageUvMeterShow(self)
        self.page_displaytest = libPages.PageDisplayTest(self)
        self.page_admin = libPages.PageAdmin(self)
        self.page_netupdate = libPages.PageNetUpdate(self)
        self.page_setuphw = libPages.PageSetupHw(self)
        self.page_setupexpo = libPages.PageSetupExposure(self)
        self.page_exception = libPages.PageException(self)
        self.page_towermove = libPages.PageTowerMove(self)
        self.page_tiltmove = libPages.PageTiltMove(self)
        self.page_toweroffset = libPages.PageTowerOffset(self)
        self.page_tiltprofiles = libPages.PageTiltProfiles(self)
        self.page_calibration1 = libPages.PageCalibration1(self)
        self.page_calibration2 = libPages.PageCalibration2(self)
        self.page_calibration3 = libPages.PageCalibration3(self)
        self.page_calibration4 = libPages.PageCalibration4(self)
        self.page_calibration5 = libPages.PageCalibration5(self)
        self.page_calibration6 = libPages.PageCalibration6(self)
        self.page_calibration7 = libPages.PageCalibration7(self)
        self.page_calibration8 = libPages.PageCalibration8(self)
        self.page_calibration9 = libPages.PageCalibration9(self)
        self.page_calibration10 = libPages.PageCalibration10(self)
        self.page_calibration11 = libPages.PageCalibration11(self)
        self.page_calibrationconfirm = libPages.PageCalibrationConfirm(self)
        self.page_tunetilt = libPages.PageTuneTilt(self)
        self.page_towerprofiles = libPages.PageTowerProfiles(self)
        self.page_fansleds = libPages.PageFansLeds(self)
        self.page_network = libPages.PageNetwork(self)
        self.page_support = libPages.PageSupport(self)
        self.page_firmwareupdate = libPages.PageFirmwareUpdate(self)
        self.page_printpreview = libPages.PagePrintPreview(self)
        self.page_printstart = libPages.PagePrintStart(self)
        self.page_manual = libPages.PageManual(self)
        self.page_videos = libPages.PageVideos(self)
        self.page_qrcode = libPages.PageQRCode(self)
        self.page_image = libPages.PageImage(self)
        self.page_video = libPages.PageVideo(self)
        self.page_setlogincredentials = libPages.PageSetLoginCredentials(self)
        self.page_unboxing1 = libPages.PageUnboxing1(self)
        self.page_unboxing2 = libPages.PageUnboxing2(self)
        self.page_unboxing3 = libPages.PageUnboxing3(self)
        self.page_unboxing4 = libPages.PageUnboxing4(self)
        self.page_unboxing5 = libPages.PageUnboxing5(self)
        self.page_unboxingconfirm = libPages.PageUnboxingConfirm(self)
        self.page_wizard1 = libPages.PageWizard1(self)
        self.page_wizard2 = libPages.PageWizard2(self)
        self.page_wizard3 = libPages.PageWizard3(self)
        self.page_wizard4 = libPages.PageWizard4(self)
        self.page_wizard5 = libPages.PageWizard5(self)
        self.page_wizard6 = libPages.PageWizard6(self)
        self.page_wizardconfirm = libPages.PageWizardConfirm(self)
        self.page_logging = libPages.PageLogging(self)
        self.page_print = libPages.PagePrint(self)
        self.page_feedme = libPages.PageFeedMe(self)
        self.page_infinitetest = libPages.PageInfiniteTest(self)

        self.actualPage = self.page_start   # TODO remove
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
        newPage = getattr(self, 'page_' + page, None)
        if newPage is None:
            self.logger.warning("There is no page named '%s'!", page)
        else:
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
                self.page_sysinfo.setItems(qt_gui_version = event.get('client_version', _("unknown")))
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
