# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os, sys
import logging
from time import sleep
from datetime import datetime

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
        self.page_systemwait = libPages.PageWait(self)
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

        self.actualPage = self.page_start
        self.fanErrorOverride = False
        self.checkCoolingExpo = True
        self.backActions = set(("_EXIT_", "_BACK_", "_OK_", "_NOK_"))
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
                    return (event.get('id', None), event.get('pressed', None), event.get('data', None))
                #endif
                self.logger.warning("event page (%s) and actual page (%s) differ", event['page'], self.actualPage.pageUI)
            elif event.get('client_type', None) == "prusa_sla_client_qt":
                self.page_sysinfo.setItems(qt_gui_version = event.get('client_version', _("unknown")))
            #endif
        #endfor
        return (None, None, None)
    #enddef


    def doMenu(self, startPage):
        self.pageStack = list()
        if startPage is not None:
            self.setPage(startPage)
        #endif
        autorepeatFce = None
        autorepeatDelay = 1
        callbackTime = datetime.fromtimestamp(0)
        updateDataTime = callbackTime
        while True:
            now = datetime.now()

            if self.actualPage.callbackPeriod and (now - callbackTime).total_seconds() > self.actualPage.callbackPeriod:
                callbackTime = now
                newPage = self.actualPage.callback()
                if newPage == "_EXIT_":
                    break
                elif newPage is not None:
                    if self.actualPage.stack:
                        self.pageStack.append(self.actualPage)
                    #endif
                    self.setPage(newPage)
                    continue
                #endif
            #endif

            if self.actualPage.updateDataPeriod and (now - updateDataTime).total_seconds() > self.actualPage.updateDataPeriod:
                updateDataTime = now
                self.actualPage.updateData()
            #endif

            button, pressed, data = self.getEvent()
            if button is not None:
                if button in self.actualPage.autorepeat:
                    if pressed:
                        self.hw.beepEcho()
                        autorepeatDelay, autorepeatDelayNext = self.actualPage.autorepeat[button]
                        autorepeatFce = getattr(self.actualPage, button + "Button", self.actualPage.emptyButton)
                        autorepeatFce()
                    else:
                        autorepeatFce = None
                        autorepeatDelay = 1
                        submitFce = getattr(self.actualPage, button + "ButtonSubmit", None)
                        releaseFce = getattr(self.actualPage, button + "ButtonRelease", None)
                        if submitFce:
                            submitFce(data)
                        elif releaseFce:
                            releaseFce()
                        #endif
                    #endif
                elif pressed:
                    pressFce = getattr(self.actualPage, button + "Button", None)
                    if pressFce:
                        pressFce()
                    #endif
                else:
                    self.hw.beepEcho()
                    submitFce = getattr(self.actualPage, button + "ButtonSubmit", None)
                    releaseFce = getattr(self.actualPage, button + "ButtonRelease", self.actualPage.emptyButtonRelease)
                    if submitFce:
                        newPage = submitFce(data)
                    elif releaseFce:
                        newPage = releaseFce()
                    #endif

                    # Allow leave function o override newPage
                    if newPage is not None:
                        newPage = self.actualPage.leave(newPage)
                    #endif

                    if newPage in self.backActions:
                        autorepeatFce = None
                        autorepeatDelay = 1
                        sleep(0.1)
                        while newPage in self.backActions:
                            if not self.goBack(show = False):
                                return
                            #endif
                            np = None
                            backFce = getattr(self.actualPage, newPage, None)
                            if backFce:
                                np = backFce()
                            #endif
                            newPage = np
                        #endwhile
                        self.actualPage.show()
                    #endif
                    if newPage == "_SELF_":
                        self.actualPage.show()
                        continue
                    elif newPage is not None:
                        if self.actualPage.stack:
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


    def goBack(self, count = 1, show = True):
        retc = True
        page = self.actualPage
        for i in xrange(count):
            if len(self.pageStack):
                page = self.pageStack.pop()
            else:
                retc = False
            #endif
        #endfor
        if page != self.actualPage:
            self.actualPage = page
            if show:
                self.actualPage.show()
            #endif
        #endif
        return retc
    #enddef


    # TODO presunout pryc
    def shutDown(self, doShutDown, reboot=False):
        self.setPage("start")
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
