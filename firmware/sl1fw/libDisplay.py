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

    def __init__(self, hwConfig, config, devices, hw, inet):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.config = config
        self.devices = devices
        self.hw = hw
        self.inet = inet
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
        self.page_controlhw = libPages.PageControlHW(self)
        self.page_patterns = libPages.PagePatterns(self)
        self.page_admin = libPages.PageAdmin(self)
        self.page_setuphw = libPages.PageSetupHW(self)
        self.page_exception = libPages.PageException(self)
        self.page_towermove = libPages.PageTowerMove(self)
        self.page_tiltmove = libPages.PageTiltMove(self)
        self.page_towercalib = libPages.PageTowerCalib(self)
        self.page_tiltcalib = libPages.PageTiltCalib(self)
        self.page_tiltprofiles = libPages.PageTiltProfiles(self)
        self.page_towerprofiles = libPages.PageTowerProfiles(self)
        self.page_state = libPages.PageState(self)
        self.page_keyboard = libPages.PageKeyboard(self)

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


    def exitus(self):
        pageWait = libPages.PageWait(self, line2 = "Shutting down")
        pageWait.show()
        self.shutDown(self.config.autoOff)
    #enddef


    def mc2net(self, bootloader = False):
        import subprocess
        baudrate = 19200 if bootloader else 115200
        pageWait = libPages.PageWait(self,
            line1 = "Master is down. Baudrate is %d" % baudrate,
            line2 = "Serial line is redirected to port %d" % defines.socatPort,
            line3 = "Press reset to continue ;-)" if bootloader else 'Type "!shdn 0" to power off ;-)')
        pageWait.show()
        pid = subprocess.Popen([
            defines.Mc2NetCommand,
            defines.motionControlDevice,
            str(defines.socatPort),
            str(baudrate)]).pid
        self.shutDown(False)
    #enddef


    def netUpdate(self):
        import libConfig
        # check network connection
        if self.inet.getIp() != "none":
            # download version info
            configText = self.inet.httpRequestEX(defines.netUpdateVersionURL)
            if configText is not None:
                netConfig = libConfig.NetConfig()
                netConfig.parseText(configText)
                netConfig.logAllItems()
                # check versions
                if netConfig.firmware.startswith("Gen3"):
                    if netConfig.firmware != defines.swVersion:
                        self.updateCommand = defines.netUpdateCommand
                        self.page_confirm.setParams(
                                continueFce = self.performUpdate,
                                line1 = "Firmware version: " + netConfig.firmware,
                                line3 = "Proceed update?")
                        return "confirm"
                    else:
                        message = "System is up to date"
                    #endif
                else:
                    message = "Wrong firmware signature"
                #endif
            else:
                message = "Network read error"
            #endif
        else:
            message = "Network is not avaiable"
        #endif

        self.logger.warning(message)
        self.page_error.setParams(line1 = "Net update was rejected:", line2 = message)
        return "error"
    #enddef


    def usbUpdate(self):
        import libConfig
        # check new firmware defines
        fwConfig = libConfig.FwConfig(os.path.join(defines.usbUpdatePath + defines.swPath, "defines.py"))
        fwConfig.logAllItems()
        if fwConfig.version.startswith("Gen3"):
            self.updateCommand = defines.usbUpdateCommand
            self.page_confirm.setParams(
                    continueFce = self.performUpdate,
                    line1 = "Firmware version: " + fwConfig.version,
                    line3 = "Proceed update?")
            return "confirm"
        else:
            message = "Wrong firmware signature"
        #endif

        self.logger.warning(message)
        self.page_error.setParams(line1 = "USB update was rejected:", line2 = message)
        return "error"
    #enddef


    def performUpdate(self):
        import subprocess
        import shutil

        pageWait = libPages.PageWait(self, line1 = "Updating")
        pageWait.show()

        if not self.remountBoot("rw"):
            pageWait.showItems(line1 = "Something went wrong!", line2 = "Can't write to system")
            self.shutDown(False)
        #endif

        process = subprocess.Popen(self.updateCommand, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        while True:
            line = process.stdout.readline()
            retc = process.poll()
            if line == '' and retc is not None:
                break
            #endif
            if line:
                line = line.strip()
                if line == "":
                    continue
                #endif
                # TODO lepe osetrit cteni vstupu! obcas se vrati radek na kterem
                # to hodi vyjimku
                eq_index = line.find('=')
                if eq_index > 0:
                    eq_index2 = line[eq_index + 1:].find("/")
                    if eq_index2 > 0:
                        togo = int(line[eq_index + 1 : eq_index + eq_index2 + 1])
                        total = int(line[eq_index + eq_index2 + 2 : -1])
                        actual = total - togo
                        percent = int(100 * actual / total)
                        pageWait.showItems(line2 = "%d/%d" % (actual, total))
                        continue
                    #endif
                #endif
                self.logger.info("rsync output: '%s'", line)
            #endif
        #endwhile

        self.remountBoot("ro")

        try:
            shutil.copyfile(defines.printerlog, os.path.join(defines.home, "update.log"))
        except Exception:
            self.logger.exception("copyfile exception:")
        #endtry

        if retc:
            pageWait.showItems(
                    line1 = "Something went wrong!",
                    line2 = "The firmware is probably damaged",
                    line3 = "and maybe does not start :(")
            self.shutDown(False)
        else:
            pageWait.showItems(
                    line1 = "Update done",
                    line2 = "Shutting down")
            self.shutDown(self.config.autoOff)
        #endif
    #enddef


    def remountBoot(self, mode):
        retc = os.system("mount -o remount,%s /boot" % mode)
        if retc:
            self.logger.error("remount %s failed with code %d", mode, retc)
            return False
        #endif
        return True
    #enddef


    def changeHostname(self):
        self.page_confirm.setParams(
                continueFce = self.performChangeHostname,
                line1 = "New hostname: %s" % self.config.newHostname)
        return "confirm"
    #enddef

    def performChangeHostname(self):
        self.logger.info('new hostname: %s', self.config.newHostname)
        retc = os.system('%s "%s"' % (defines.hostnameCommand, self.config.newHostname))
        if retc:
            self.logger.error("%s failed with code %d", defines.hostnameCommand, retc)
        #endif
        return "_BACK_"
    #enddef


    def setupWiFi(self):
        if self.config.ssid:
            if self.config.password:
                self.message = None
                self.page_confirm.setParams(
                        continueFce = self.performSetupWifi,
                        line1 = "WiFi SSID: %s" % self.config.ssid,
                        line2 = "WiFi password: %s" % self.config.password)
                return "confirm"
            else:
                self.message = "Password is empty!"
            #endif
        else:
            self.message = "SSID is empty!"
        #endif

        self.logger.error(self.message)
        self.page_error.setParams(line1 = "Can't setup WiFi:", line2 = self.message)
        return "error"
    #enddef

    def performSetupWifi(self):
        pageWait = libPages.PageWait(self, line1 = "Setting WiFi")
        pageWait.show()
        self.message = self.inet.setupWireless(self.config.ssid, self.config.password)
        return "_BACK_"
    #enddef


    def towerMeasure(self):

        # FIXME

        self.page_confirm.setParams(
                continueFce = self.performTowerMeasure,
                line1 = "Tower is not calibrated.",
                line2 = "On next page zero the platform",
                line3 = "and then press OK button.")
        return self.doMenu("confirm")
    #endif


    def performTowerMeasure(self):

        # FIXME


        pageWait = libPages.PageWait(self)
        self.hw.powerLed("warn")
        pageWait.show()
        pageWait.showItems(line2 = "Tank start position")
        self.hw.tiltReset()
        self.hw.powerLed("normal")
        self.doMenu("towermove")
        self.hw.powerLed("warn")
        pageWait.show()
        pageWait.showItems(line2 = "Measuring")
        towerHeight = self.hw.measureTower()
        self.hwConfig.update(towerheight = str(towerHeight), calibrated = "yes")
        #self.hwConfig.writeFile()
        self.hw.powerLed("normal")
        return "_EXIT_MENU_"
    #enddef


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
