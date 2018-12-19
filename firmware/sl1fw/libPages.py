# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from time import sleep
import json

import defines
import libConfig

class Page(object):

    def __init__(self, display):
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.autorepeat = {}
        self.callbackPeriod = None
        self.fill()
    #enddef


    def fill(self):
        self.items = { "image_version" : self.display.hwConfig.os.versionId, "page_title" : self.pageTitle }
    #enddef


    def prepare(self):
        pass
    #enddef


    def show(self):
        for device in self.display.devices:
            device.setPage(self.pageUI)
            device.setItems(self.items)
            device.showPage()
        #endfor
    #enddef


    def showItems(self, **kwargs):
        self.items.update(kwargs)
        for device in self.display.devices:
            device.showItems(kwargs)
        #endfor
    #enddef


    def emptyButton(self):
        self.logger.debug("emptyButton() called")
    #enddef


    def emptyButtonRelease(self):
        self.logger.debug("emptyButtonRelease() called")
    #enddef


    def backButtonRelease(self):
        return "_BACK_"
    #enddef


    def wifiButtonRelease(self):
        return "netinfo"
    #enddef


    def infoButtonRelease(self):
        return "about"
    #enddef


    def turnoffButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.display.exitus,
                line1 = "Do you really want to",
                line2 = "turn off the printer?")
        return "confirm"
    #enddef


    def checkConfFile(self, configFileWithPath):
        # pokud se tiskne, nic nenacitat
        if self.display.config.final:
            return
        #endif
        newConfig = libConfig.PrintConfig(self.display.hwConfig, configFileWithPath)
        self.logger.info("JOB config:")
        newConfig.logAllItems()
        # pokud byl uz soubor jednou nacten, ponechej puvodni, doba osvitu
        # mohla byt zmenena
        if newConfig.getHash() != self.display.config.getHash():
            # pro jistotu nacteme do puvodniho configu, buh vi co by udelalo
            # proste prirazeni
            self.display.config.parseFile(configFileWithPath)
        else:
            # zipfile se cte vzdycky znovu, mohl se zmenit
            # (napr. oprava spatne vygenerovaneho)
            self.display.config.readZipFile()
        #endif
    #enddef


    def netChange(self):
        pass
    #enddef


    def _setItem(self, items, index, value):
        if self.oldValues.get(index, None) != value:
            valueType = type(value).__name__
            if valueType == "bool":
                items[index] = 1 if value else 0
            else:
                items[index] = str(value)
            #endif
            self.oldValues[index] = value
        #endif
    #enddef


    def _syncTower(self, pageWait):
        self.display.hw.towerSync()
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
            pageWait.showItems(line3 = self.display.hw.getTowerPosition())
        #endwhile
        if self.display.hw.towerSyncFailed():
            self.display.page_error.setParams(
                    line1 = "Tower homing failed!",
                    line2 = "Check printer's hardware.")
            return "error"
        #endif
        return "_SELF_"
    #enddef


    def _syncTilt(self):
        if not self.display.hw.tiltSyncWait(retries = 2):
            self.display.page_error.setParams(
                    line1 = "Tilt homing failed!",
                    line2 = "Check printer's hardware.")
            return "error"
        #endif
        return "_SELF_"
    #enddef

#endclass


class PageWait(Page):

    def __init__(self, display, **kwargs):
        self.pageUI = "wait"
        self.pageTitle = "Wait"
        super(PageWait, self).__init__(display)
        self.items.update(kwargs)
    #enddef


    def fill(self, **kwargs):
        super(PageWait, self).fill()
        self.items.update(kwargs)
    #enddef

#endclass


class PageConfirm(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = "Confirm"
        super(PageConfirm, self).__init__(display)
    #enddef


    def setParams(self, **kwargs):
        self.continueFce = kwargs.pop("continueFce", None)
        self.continueParmas = kwargs.pop("continueParmas", dict())
        self.fill()
        self.items.update(kwargs)
    #enddef


    def contButtonRelease(self):
        if self.continueFce is None:
            return "_EXIT_MENU_"
        else:
            return self.continueFce(**self.continueParmas)
        #endif
    #enddef

#endclass


class PageIntro(Page):

    def __init__(self, display):
        self.pageUI = "intro"
        self.pageTitle = "Intro"
        super(PageIntro, self).__init__(display)
    #enddef

#endclass


class PageStart(Page):

    def __init__(self, display):
        self.pageUI = "start"
        self.pageTitle = "Start"
        super(PageStart, self).__init__(display)
    #enddef

#endclass


class PageHome(Page):

    def __init__(self, display):
        self.pageUI = "home"
        self.pageTitle = "Home"
        super(PageHome, self).__init__(display)
        # meni se i z libPrinter!
        self.firstRun = True
    #enddef


    def show(self):
        super(PageHome, self).show()
        if self.firstRun:
            self.display.hw.beepRepeat(2) # ready beep
            self.firstRun = False
        #endif
    #enddef


    def controlButtonRelease(self):
        return "control"
    #enddef


    def settingsButtonRelease(self):
        return "settings"
    #enddef


    def printButtonRelease(self):
        # FIXME
#        if not self.display.hwConfig.calibrated and not self.display.towerMeasure():
#            return "home"
#        #endif

        return "sourceselect"
    #enddef

#endclass


class PageControl(Page):

    def __init__(self, display):
        self.pageUI = "control"
        self.pageTitle = "Control"
        super(PageControl, self).__init__(display)
        self.autorepeat = { "up" : (1, 1) }
    #enddef


    def show(self):
        self.moving = False
        super(PageControl, self).show()
    #enddef


    def topButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Moving platform to top")
        pageWait.show()
        retc = self._syncTower(pageWait)
        self.display.hw.motorsRelease()
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def upButton(self):
        if not self.moving:
            self.display.hw.towerSync()
            self.moving = True
        elif self.display.hw.isTowerSynced():
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def upButtonRelease(self):
        self.display.hw.towerStop()
        self.moving = False
        self.display.hw.motorsRelease()
    #enddef


    def tankresButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Tank reset")
        pageWait.show()
        self.display.hw.checkCoverStatus(PageWait(self.display), pageWait)
        retc = self._syncTilt()
        if retc == "error":
            self.display.hw.motorsRelease()
            return retc
        #endif
        self.display.hw.setTiltProfile('layer')
        self.display.hw.tiltDownWait()
        self.display.hw.tiltUpWait()
        self.display.hw.motorsRelease()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef

#endclass


class PageSettings(Page):

    def __init__(self, display):
        self.pageUI = "settings"
        self.pageTitle = "Settings"
        super(PageSettings, self).__init__(display)
    #enddef


    def projsettButtonRelease(self):
        return "projsettings"
    #enddef


    def sysinfoButtonRelease(self):
        return "sysinfo"
    #enddef


    def changeButtonRelease(self):
        return "change"
    #enddef

#endclass


class PagePrint(Page):

    def __init__(self, display):
        self.pageUI = "print"
        self.pageTitle = "Print"
        super(PagePrint, self).__init__(display)
    #enddef


    def setupButtonRelease(self):
        return "homeprint"
    #enddef

#endclass


class PageHomePrint(Page):

    def __init__(self, display, expo):
        self.pageUI = "homeprint"
        self.pageTitle = "Print Home"
        super(PageHomePrint, self).__init__(display)
        self.expo = expo
    #enddef


    def updownButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.doUpAndDown,
                line1 = "Do you really want to",
                line2 = "go platform up and down?",
                line3 = "It may affect the result!")
        return "confirm"
    #enddef


    def doUpAndDown(self):
        self.expo.doUpAndDown()
        self.display.page_systemwait.fill(
                line2 = "Up and down will be executed",
                line3 = "after layer finish")
        return "systemwait"
    #enddef


    def settingsButtonRelease(self):
        return "settings"
    #enddef


    def upoffButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.exitPrint,
                line1 = "Do you really want to",
                line2 = "cancel actual job",
                line3 = "and turn off the printer?")
        return "confirm"
    #enddef


    def exitPrint(self):
        self.expo.doExitPrint()
        self.display.page_systemwait.fill(
                line2 = "Job will be canceled",
                line3 = "after layer finish")
        return "systemwait"
    #enddef

#endclass


class PageProjSett(Page):

    def __init__(self, display):
        self.pageUI = "projsettings"
        self.pageTitle = "Project Settings"
        super(PageProjSett, self).__init__(display)
    #enddef


    def prepare(self):
        self.checkConfFile(self.display.config.configFile)
        if self.display.config.zipError:
            sleep(0.5)
            self.display.page_error.setParams(
                    line1 = "Your project has a problem:",
                    line2 = self.display.config.zipError,
                    line3 = "Regenerate it and try again.")
            return "error"
        #endif
    #enddef


    def show(self):
        self.items["line2"] = "Layers: %d at a height of %.3f mm" % (self.display.config.totalLayers, self.display.hwConfig.calcMM(self.display.config.layerMicroSteps))
        if self.display.config.calibrateRegions:
            self.items["line1"] = "Calibration[%d]: %s" % (self.display.config.calibrateRegions, self.display.config.projectName)
            self.items["line3"] = "Exposure times: %d s / %.1f s (+%.1f)" % (int(self.display.config.expTimeFirst), self.display.config.expTime, self.display.config.calibrateTime)
        else:
            self.items["line1"] = "Project: %s" % self.display.config.projectName
            self.items["line3"] = "Exposure times: %d s / %.1f s" % (int(self.display.config.expTimeFirst), self.display.config.expTime)
        #endif
        super(PageProjSett, self).show()
    #enddef


    def changeButtonRelease(self):
        return "change"
    #enddef

#endclass


class PageChange(Page):

    def __init__(self, display):
        self.pageUI = "change"
        self.pageTitle = "Change Exposure Time"
        super(PageChange, self).__init__(display)
        self.autorepeat = { "addsecond" : (5, 1), "subsecond" : (5, 1) }
    #enddef


    def show(self):
        self.expTime = self.display.config.expTime
        self.items["timeexpos"] = "%.1f" % self.expTime
        super(PageChange, self).show()
    #enddef


    def backButtonRelease(self):
        self.display.config.expTime = self.expTime
        return super(PageChange, self).backButtonRelease()
    #endif


    def addsecondButton(self):
        if self.expTime < 60:
            self.expTime += 1
        #endif
        self.showItems(timeexpos = "%.1f" % self.expTime)
    #enddef


    def subsecondButton(self):
        if self.expTime > 1:
            self.expTime -= 1
        #endif
        self.showItems(timeexpos = "%.1f" % self.expTime)
    #enddef

#endclass


class PageSysInfo(Page):

    def __init__(self, display):
        self.pageUI = "sysinfo"
        self.pageTitle = "System Information"
        super(PageSysInfo, self).__init__(display)
        self.items.update({
                "line1" : "Serial number: %s" % self.display.hwConfig.sn,
                "line2" : "System: %s" % self.display.hwConfig.os.name,
                "line3" : "System version: %s" % self.display.hwConfig.os.version,
                "line4" : "Firwmare version: %s" % defines.swVersion,
                })
        self.callbackPeriod = 2
    #enddef


    def show(self):
        self.oldValues = {}
        self.items["line5"] = "Controller version: %s" % self.display.hw.getControllerVersion()
        self.items["line6"] = "Controller number: %s" % self.display.hw.getControllerSerial()
        super(PageSysInfo, self).show()
    #enddef


    def menuCallback(self):
        items = {}
        self._setItem(items, "line7", "Tower height: %.2f mm" % self.display.hwConfig.calcMM(self.display.hwConfig.towerHeight))
        self._setItem(items, "line8", "SYS temperature: %.1f C" % self.display.hw.getTemperatureSystem())
        self._setItem(items, "line9", "LED temperature: %.1f C" % self.display.hw.getTemperatureUVLED())
        if len(items):
            self.showItems(**items)
        #endif
    #enddef

#endclass


class PageNetInfo(Page):

    def __init__(self, display):
        self.pageUI = "netinfo"
        self.pageTitle = "Network Information"
        super(PageNetInfo, self).__init__(display)
    #enddef


    def fillData(self):
        items = {}
        ip = self.display.inet.getIp()
        items["line1"] = "IP address: %s" % ip
        items["line2"] = "Hostname: %s" % self.display.inet.getHostname()
        if ip != "none":
            items["qr1label"] = "Remote access"
            items["qr1"] = "http://%s" % ip
            items["qr2label"] = "Debug"
            items["qr2"] = "http://%s/debug" % ip
        else:
            items["qr1label"] = ""
            items["qr1"] = ""
            items["qr2label"] = ""
            items["qr2"] = ""
        #endif
        return items
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageNetInfo, self).show()
    #enddef


    def netChange(self):
        self.showItems(**self.fillData())
    #enddef

#endclass


class PageAbout(Page):

    def __init__(self, display):
        self.pageUI = "about"
        self.pageTitle = "About"
        super(PageAbout, self).__init__(display)
        self.items.update({
                "line1" : "(c) 2018 Prusa Research s.r.o.",
                "line2" : "www.prusa3d.com",
#                "qr1" : "https://www.prusa3d.com",
                "qr1" : "MECARD:N:Prusa Research s.r.o.;URL:www.prusa3d.com;EMAIL:info@prusa3d.com;;",
                })
    #enddef


    def adminButtonRelease(self):
        return "admin"
    #enddef

#endclass


class PageSrcSelect(Page):

    def __init__(self, display):
        self.pageUI = "sourceselect"
        self.pageTitle = "Source Select"
        super(PageSrcSelect, self).__init__(display)
    #enddef


    def show(self):
        self.items["line1"] = "Please select project source"
        self.items["line2"] = "IP: %s" % self.display.inet.getIp()
        super(PageSrcSelect, self).show()
    #enddef


    def netChange(self):
        self.showItems(line2 = "IP: %s" % self.display.inet.getIp())
    #enddef


    def bothButtons(self, source, configFileWithPath):

        self.showItems(line1 = "Reading project data...")
        self.checkConfFile(configFileWithPath)
        config = self.display.config

        if not config.configFound:
            sleep(0.5)
            self.showItems(line1 = "%s project not found" % source)
            self.display.hw.beepAlarm(3)
            return
        elif config.action != "print":
            self.showItems(line1 = "Invalid project file")
            self.display.hw.beepAlarm(3)
            return
        elif config.zipError is not None:
            sleep(0.5)
            self.display.page_error.setParams(
                    line1 = "Your project has a problem:",
                    line2 = config.zipError,
                    line3 = "Regenerate it and try again.")
            return "error"
        #endif

        if config.calibrateRegions:
            self.display.page_confirm.setParams(
                    line1 = "Calibration[%d]: %s" % (config.calibrateRegions, config.projectName),
                    line2 = "Layers: %d at a height of %.3f mm" % (config.totalLayers, self.display.hwConfig.calcMM(config.layerMicroSteps)),
                    line3 = "Exposure times: %d s / %.1f s (+%.1f)" % (int(config.expTimeFirst), config.expTime, config.calibrateTime))
        else:
            self.display.page_confirm.setParams(
                    line1 = "Project: %s" % config.projectName,
                    line2 = "Layers: %d at a height of %.3f mm" % (config.totalLayers, self.display.hwConfig.calcMM(config.layerMicroSteps)),
                    line3 = "Exposure times: %d s / %.1f s" % (int(config.expTimeFirst), config.expTime))
        #endif
        return "confirm"
    #endef


    def usbButtonRelease(self):
        return self.bothButtons("USB", os.path.join(defines.usbPath, defines.configFile))
    #enddef


    def lanButtonRelease(self):
        return self.bothButtons("LAN", os.path.join(defines.ramdiskPath, defines.configFile))
    #enddef

#endclass


class PageKeyboard(Page):

    def __init__(self, display):
        self.pageUI = "keyboard_edit"
        self.pageTitle = "Keyboard"
        super(PageKeyboard, self).__init__(display)
        self.items.update({
            'text' : "initial text",
            'line1' : "Item",
            })
    #enddef


    def acceptButtonRelease(self):
        return super(PageKeyboard, self).backButtonRelease()
    #enddef


    def cancelButtonRelease(self):
        return super(PageKeyboard, self).backButtonRelease()
    #enddef

#endclass


class PageError(Page):

    def __init__(self, display):
        self.pageUI = "error"
        self.pageTitle = "Error"
        super(PageError, self).__init__(display)
    #enddef


    def show(self):
        super(PageError, self).show()
        self.display.hw.powerLed("error")
        self.display.hw.beepAlarm(3)
    #enddef


    def setParams(self, **kwargs):
        self.fill()
        self.items.update(kwargs)
    #enddef


    def backButtonRelease(self):
        self.display.hw.powerLed("normal")
        return super(PageError, self).backButtonRelease()
    #enddef


    def turnoffButtonRelease(self):
        self.display.hw.powerLed("normal")
        return super(PageError, self).turnoffButtonRelease()
    #enddef

#endclass


class PageControlHW(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = "Admin - Hardware control"
        super(PageControlHW, self).__init__(display)
        self.items.update({
                "button1" : "Tilt home",
                "button2" : "Tilt move",
                "button3" : "Tilt man. calib.",
                "button4" : "Tilt test",
                "button5" : "Tilt profiles",
                "button6" : "Tower home",
                "button7" : "Tower move",
                "button8" : "Tower man. calib.",
                "button9" : "Tower test",
                "button10" : "Tower profiles",
                "button11" : "Aret. off",
#                "button12" : "Recalib. endstops",

                "back" : "Back",
                })
    #enddef


    def button1ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Tilt home")
        pageWait.show()
        retc = self._syncTilt()
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def button2ButtonRelease(self):
        return "tiltmove"
    #enddef


    def button3ButtonRelease(self):
        return "tiltcalib"
    #enddef


    def button4ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Tilt sync")
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line2 = "Tilt up")
        self.display.hw.tiltUpWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line2 = "Tilt down")
        self.display.hw.tiltDownWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line2 = "Tilt up")
        self.display.hw.tiltUpWait()
        self.display.hw.beepEcho()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button5ButtonRelease(self):
        return "tiltprofiles"
    #enddef


    def button6ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Moving platform to top")
        pageWait.show()
        retc = self._syncTower(pageWait)
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def button7ButtonRelease(self):
        return "towermove"
    #enddef


    def button8ButtonRelease(self):
        return "towercalib"
    #enddef


    def button9ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Moving platform to top")
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line2 = "Moving platform to zero")
        self.display.hw.towerZero()
        while not self.display.hw.isTowerOnZero():
            sleep(0.25)
            pageWait.showItems(line3 = self.display.hw.getTowerPosition())
        #endwhile
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button10ButtonRelease(self):
        return "towerprofiles"
    #enddef


    def button11ButtonRelease(self):
        self.display.hw.motorsRelease()
    #enddef

#endclass


class PagePatterns(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = "Admin - Display Test"
        super(PagePatterns, self).__init__(display)
        self.items.update({
                "button1" : "Chess 8",
                "button2" : "Chess 16",
                "button3" : "Grid 8",
                "button4" : "Grid 16",
                "button5" : "Maze",

                "button6" : "USB:/test.png",

                "button11" : "Black",
                "button12" : "Inverse",

                "button14" : "UV on",
                "back" : "Back",
                })
        self.uvIsOn = False
    #enddef


    def prepare(self):
        try:
            from libScreen import Screen
            self.screen = Screen(self.display.hwConfig, defines.dataPath)
        except Exception:
            self.logger.exception("screen exception:")
            self.display.page_error.setParams(
                    line1 = "Display init failed!",
                    line2 = "Check printer's hardware.")
            return "error"
        #endtry
    #enddef


    def show(self):
        self.button1ButtonRelease()
        super(PagePatterns, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.screen.getImg("sachovnice8_1440x2560.png")
    #enddef


    def button2ButtonRelease(self):
        self.screen.getImg("sachovnice16_1440x2560.png")
    #enddef


    def button3ButtonRelease(self):
        self.screen.getImg("mrizka8_1440x2560.png")
    #enddef


    def button4ButtonRelease(self):
        self.screen.getImg("mrizka16_1440x2560.png")
    #enddef


    def button5ButtonRelease(self):
        self.screen.getImg("bludiste_1440x2560.png")
    #enddef


    def button6ButtonRelease(self):
        try:
            self.screen.getImg("test.png", defines.usbPath)
        except Exception:
            self.logger.exception("export exception:")
            self.display.hw.beepAlarm(3)
        #endtry
    #enddef


    def button11ButtonRelease(self):
        self.screen.getImgBlack()
    #enddef


    def button12ButtonRelease(self):
        self.screen.inverse()
    #enddef


    def button14ButtonRelease(self):
        if self.uvIsOn:
            self.uvIsOn = False
            self.showItems(button14 = "UV on")
        else:
            self.uvIsOn = True
            self.showItems(button14 = "UV off")
        #endif
        self.display.hw.uvLed(self.uvIsOn)
    #enddef


    def backButtonRelease(self):
        try:
            self.screen.exit()
            del self.screen
        except Exception:
            self.logger.exception("screen exception:")
            self.display.hw.beepAlarm(3)
        #endtry
        return super(PagePatterns, self).backButtonRelease()
    #enddef

#endclass


class PageAdmin(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = "Admin - Main Page"
        super(PageAdmin, self).__init__(display)
        self.items.update({
                "button1" : "Control HW",
                "button2" : "Display test",
                "button3" : "State",
                "button4" : "Setup HW",

                "button6" : "Flash MC",
                "button7" : "MC2Net (bootloader)",
                "button8" : "MC2Net (firmware)",
                #"button10" : "USB update",

                "button11" : "Change hostname",
                "button12" : "Setup WiFi",
                "button13" : "Network",
                "button14" : "Keyboard test",

                "back" : "Back",
                })
    #enddef


    def button1ButtonRelease(self):
        return "controlhw"
    #enddef


    def button2ButtonRelease(self):
        return "patterns"
    #enddef


    def button3ButtonRelease(self):
        return "state"
    #enddef


    def button4ButtonRelease(self):
        return "setuphw"
    #enddef


    def button6ButtonRelease(self):
        pageWait = PageWait(self.display, line2 = "Flashing Motion Controler")
        pageWait.show()
        self.display.hw.flashMC()
        return "_SELF_"
    #enddef


    def button7ButtonRelease(self):
        self.display.mc2net(bootloader = True)
        return "_BACK_"
    #enddef


    def button8ButtonRelease(self):
        self.display.mc2net(bootloader = False)
        return "_BACK_"
    #enddef


    def button10ButtonRelease(self):
        pass
        #return self.display.usbUpdate()
    #enddef


    def button11ButtonRelease(self):
        self.checkConfFile(self.display.config.configFile)
        return self.display.changeHostname()
    #enddef


    def button12ButtonRelease(self):
        self.checkConfFile(self.display.config.configFile)
        return self.display.setupWiFi()
    #enddef


    def button13ButtonRelease(self):
        return "netinfo"
    #enddef


    def button14ButtonRelease(self):
        return "keyboard"
    #enddef


#endclass


class PageSetupHW(Page):

    def __init__(self, display):
        self.pageUI = "setup"
        self.pageTitle = "Admin - Hardware Setup"
        super(PageSetupHW, self).__init__(display)
        self.autorepeat = {
                "minus2g1" : (5, 1), "plus2g1" : (5, 1),
                "minus2g2" : (5, 1), "plus2g2" : (5, 1),
                "minus2g3" : (5, 1), "plus2g3" : (5, 1),
                }
        self.items.update({
                "label1g1" : "Fan check",
                "label1g2" : "Cover check",
                "label1g3" : "MC version check",

                "label2g1" : "Screw mm/rot",
                "label2g2" : "Tower corr. (mm)",
                "label2g3" : "Tilt height (msteps)",

                "button4" : "Save",
                "back" : "Back",
                })
        self.changed = {}
        self.temp = {}
    #enddef


    def show(self):
        self.temp["screwmm"] = self.display.hwConfig.screwMm
        self.temp["towcorr"] = 0.0
        self.temp["tiltheight"] = self.display.hwConfig.tiltHeight

        self.items["value2g1"] = str(self.temp["screwmm"])
        self.items["value2g2"] = str(self.temp["towcorr"])
        self.items["value2g3"] = str(self.temp["tiltheight"])

        self.temp["fancheck"] = self.display.hwConfig.fanCheck
        self.temp["covercheck"] = self.display.hwConfig.coverCheck
        self.temp["mcversioncheck"] = self.display.hwConfig.MCversionCheck

        self.items["state1g1"] = 1 if self.temp["fancheck"] else 0
        self.items["state1g2"] = 1 if self.temp["covercheck"] else 0
        self.items["state1g3"] = 1 if self.temp["mcversioncheck"] else 0

        super(PageSetupHW, self).show()
    #enddef


    def _onOff(self, val, name):
        self.temp[val] = not self.temp[val]
        self.changed[val] = "on" if self.temp[val] else "off"
        self.showItems(**{ name : 1 if self.temp[val] else 0 })
    #enddef


    def _value(self, valmin, valmax, val, change, name):
        if valmin <= self.temp[val] + change <= valmax:
            self.temp[val] += change
            self.changed[val] = str(self.temp[val])
            self.showItems(**{ name : str(self.temp[val]) })
        else:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def button4ButtonRelease(self):
        ''' save '''

        # FIXME hnus, pryc jak to bude mozne...
        if "towcorr" in self.changed:
            corr = self.display.hwConfig.calcMicroSteps(self.temp["towcorr"])
            self.logger.debug("tower correction", corr)
            del self.changed["towcorr"]
            self.changed["towerheight"] = self.display.hwConfig.towerHeight + corr
        #endif
        # az sem

        self.display.hwConfig.update(**self.changed)
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        self.display.config._parseData()
        return super(PageSetupHW, self).backButtonRelease()
    #endif


    def state1g1ButtonRelease(self):
        self._onOff("fancheck", "state1g1")
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff("covercheck", "state1g2")
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff("mcversioncheck", "state1g3")
    #enddef


    def minus2g1Button(self):
        return self._value(2, 8, "screwmm", -1, "value2g1")
    #enddef


    def plus2g1Button(self):
        return self._value(2, 8, "screwmm", 1, "value2g1")
    #enddef


    def minus2g2Button(self):
        return self._value(-10, 10, "towcorr", -0.1, "value2g2")
    #enddef


    def plus2g2Button(self):
        return self._value(-10, 10, "towcorr", 0.1, "value2g2")
    #enddef


    def minus2g3Button(self):
        return self._value(1, 1600, "tiltheight", -1, "value2g3")
    #enddef


    def plus2g3Button(self):
        return self._value(1, 1600, "tiltheight", 1, "value2g3")
    #enddef

#endclass


class PageException(Page):

    def __init__(self, display):
        self.pageUI = "exception"
        self.pageTitle = "System Fatal Error"
        super(PageException, self).__init__(display)
    #enddef


    def setParams(self, **kwargs):
        self.fill()
        self.items.update(kwargs)
    #enddef

#endclass


class MovePage(Page):

    def upfastButton(self):
        self._up(False)
    #enddef


    def upfastButtonRelease(self):
        self._stop()
    #enddef


    def upslowButton(self):
        self._up(True)
    #enddef


    def upslowButtonRelease(self):
        self._stop()
    #enddef


    def downfastButton(self):
        self._down(False)
    #enddef


    def downfastButtonRelease(self):
        self._stop()
    #enddef


    def downslowButton(self):
        self._down(True)
    #enddef


    def downslowButtonRelease(self):
        self._stop()
    #enddef

#endclass


class PageTowerMove(MovePage):

    def __init__(self, display):
        self.pageUI = "towermove"
        self.pageTitle = "Tower Move"
        super(PageTowerMove, self).__init__(display)
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
        self.setProfiles = True
    #enddef


    def show(self):
        self.items["value"] = self.display.hw.getTowerPosition()
        self.moving = False
        super(PageTowerMove, self).show()
    #enddef


    def _up(self, slowMoving):
        if not self.moving:
            if self.setProfiles:
                self.display.hw.setTowerProfile('moveSlow' if slowMoving else 'moveFast')
            #endif
            self.display.hw.towerToMax()
            self.moving = True
        else:
            if self.display.hw.isTowerOnMax():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTowerPosition())
        #endif
    #enddef


    def _down(self, slowMoving):
        if not self.moving:
            if self.setProfiles:
                self.display.hw.setTowerProfile('moveSlow' if slowMoving else 'moveFast')
            #endif
            self.display.hw.towerToMin()
            self.moving = True
        else:
            if self.display.hw.isTowerOnMin():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTowerPosition())
        #endif
    #enddef


    def _stop(self):
        self.display.hw.towerStop()
        self.moving = False
    #enddef


    def changeProfiles(self, setProfiles):
        self.setProfiles = setProfiles
    #enddef

#endclass


class PageTowerCalib(MovePage):

    def __init__(self, display):
        self.pageUI = "towermove"
        self.pageTitle = "Tower Calibration"
        super(PageTowerCalib, self).__init__(display)
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
    #enddef


    def prepare(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Moving platform to top")
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line2 = "Moving tank to start", line3 = "")
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.tiltUpWait()
        pageWait.showItems(line2 = "Moving platform down")
        self.display.hw.setTowerProfile('calibration')
        self.display.hw.towerZero()
        while not self.display.hw.isTowerOnZero():
            sleep(0.25)
            pageWait.showItems(line3 = self.display.hw.getTowerPosition())
        #endwhile
        self.display.hw.powerLed("normal")
        self.display.hw.setTowerZero()
        self.items["value"] = self.display.hw.getTowerPosition()
        self.moving = False
    #enddef


    def backButtonRelease(self):
        self.display.hw.setTowerZero()
        self.display.hw.setTowerProfile('calibration')
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Measuring")
        pageWait.show()
        self.display.hw.towerToMax()
        # isTowerOnMax sets the position and we don't want it here
        while not self.display.hw.isTowerOnPosition():
            sleep(0.25)
            pageWait.showItems(line3 = self.display.hw.getTowerPosition())
        #endwhile
        position = self.display.hw.getTowerPositionMicroSteps()
        if position is not None:
            self.display.hwConfig.update(towerheight = position)
            if not self.display.hwConfig.writeFile():
                self.display.hw.beepAlarm(3)
                sleep(1)
                self.display.hw.beepAlarm(3)
            #endif
        else:
            self.logger.error("Invalid tower position to save!")
            self.display.hw.beepAlarm(3)
        #endif
        return super(PageTowerCalib, self).backButtonRelease()
    #endif


    def _up(self, slowMoving):
        if not self.moving:
            self.display.hw.setTowerProfile('moveSlow' if slowMoving else 'moveFast')
            self.display.hw.towerToMax()
            self.moving = True
        else:
            if self.display.hw.isTowerOnMax():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTowerPosition())
        #endif
    #enddef


    def _down(self, slowMoving):
        if not self.moving:
            self.display.hw.setTowerProfile('moveSlow' if slowMoving else 'moveFast')
            self.display.hw.towerToMin()
            self.moving = True
        else:
            if self.display.hw.isTowerOnMin():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTowerPosition())
        #endif
    #enddef


    def _stop(self):
        self.display.hw.towerStop()
        self.moving = False
    #enddef

#endclass


class PageTiltMove(MovePage):

    def __init__(self, display):
        self.pageUI = "tiltmove"
        self.pageTitle = "Tilt Move"
        super(PageTiltMove, self).__init__(display)
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
        self.setProfiles = True
    #enddef


    def show(self):
        self.items["value"] = self.display.hw.getTiltPosition()
        self.moving = False
        super(PageTiltMove, self).show()
    #enddef


    def _up(self, slowMoving):
        if not self.moving:
            if self.setProfiles:
                self.display.hw.setTiltProfile('moveSlow' if slowMoving else 'moveFast')
            #endif
            self.display.hw.tiltToMax()
            self.moving = True
        else:
            if self.display.hw.isTiltOnMax():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTiltPosition())
        #endif
    #enddef


    def _down(self, slowMoving):
        if not self.moving:
            if self.setProfiles:
                self.display.hw.setTiltProfile('moveSlow' if slowMoving else 'moveFast')
            #endif
            self.display.hw.tiltToMin()
            self.moving = True
        else:
            if self.display.hw.isTiltOnMin():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTiltPosition())
        #endif
    #enddef


    def _stop(self):
        self.display.hw.tiltStop()
        self.moving = False
    #enddef


    def changeProfiles(self, setProfiles):
        self.setProfiles = setProfiles
    #enddef

#endclass


class PageTiltCalib(MovePage):

    def __init__(self, display):
        self.pageUI = "tiltmove"
        self.pageTitle = "Tilt Calibration"
        super(PageTiltCalib, self).__init__(display)
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
    #enddef


    def prepare(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Moving tank to start")
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.setTiltProfile('layer')
        self.display.hw.tiltDownWait()
        self.display.hw.tiltUpWait()
        self.display.hw.powerLed("normal")
        self.items["value"] = self.display.hw.getTiltPosition()
        self.moving = False
    #enddef


    def backButtonRelease(self):
        position = self.display.hw.getTiltPositionMicroSteps()
        if position is not None:
            self.display.hwConfig.update(tiltheight = position)
            if not self.display.hwConfig.writeFile():
                self.display.hw.beepAlarm(3)
                sleep(1)
                self.display.hw.beepAlarm(3)
            #endif
        else:
            self.logger.error("Invalid tilt position to save!")
            self.display.hw.beepAlarm(3)
        #endif
        return super(PageTiltCalib, self).backButtonRelease()
    #endif


    def _up(self, slowMoving):
        if not self.moving:
            self.display.hw.setTiltProfile('moveSlow' if slowMoving else 'moveFast')
            self.display.hw.tiltToMax()
            self.moving = True
        else:
            if self.display.hw.isTiltOnMax():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTiltPosition())
        #endif
    #enddef


    def _down(self, slowMoving):
        if not self.moving:
            self.display.hw.setTiltProfile('moveSlow' if slowMoving else 'moveFast')
            self.display.hw.tiltToMin()
            self.moving = True
        else:
            if self.display.hw.isTiltOnMin():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTiltPosition())
        #endif
    #enddef


    def _stop(self):
        self.display.hw.tiltStop()
        self.moving = False
    #enddef

#endclass


class ProfilesPage(Page):

    def __init__(self, display):
        self.pageUI = "setup"
        super(ProfilesPage, self).__init__(display)
        self.autorepeat = {
                "minus2g1" : (5, 1), "plus2g1" : (5, 1),
                "minus2g2" : (5, 1), "plus2g2" : (5, 1),
                "minus2g3" : (5, 1), "plus2g3" : (5, 1),
                "minus2g4" : (5, 1), "plus2g4" : (5, 1),
                "minus2g5" : (5, 1), "plus2g5" : (5, 1),
                "minus2g6" : (5, 1), "plus2g6" : (5, 1),
                "minus2g7" : (5, 1), "plus2g7" : (5, 1),
                }
        self.items.update({
                "label1g1" : self.profilesNames[0],
                "label1g2" : self.profilesNames[1],
                "label1g3" : self.profilesNames[2],
                "label1g4" : self.profilesNames[3],
                "label1g5" : self.profilesNames[4],
                "label1g6" : self.profilesNames[5],
                "label1g7" : self.profilesNames[6],
                "label1g8" : self.profilesNames[7],

                "label2g1" : "starting steprate",
                "label2g2" : "maximum steprate",
                "label2g3" : "acceleration",
                "label2g4" : "deceleration",
                "label2g5" : "current",
                "label2g6" : "stallguard threshold",
                "label2g7" : "coolstep threshold",

                "button1" : "Export",
                "button2" : "Import",
                "button3" : "Test",
                "button4" : "Save",
                "back" : "Back",
                })
        self.actualProfile = 0
    #enddef


    def _value(self, valmin, valmax, idx, change):
        if valmin <= self.profiles[self.actualProfile][idx] + change <= valmax:
            self.profiles[self.actualProfile][idx] += change
            self.showItems(**{ "value2g%d" % (idx + 1) : str(self.profiles[self.actualProfile][idx]) })
        else:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def _setProfile(self, profile = None):
        if profile is not None:
            self.actualProfile = profile
        #endif
        data = { "state1g1" : 0, "state1g2" : 0, "state1g3" : 0, "state1g4" : 0, "state1g5" : 0, "state1g6" : 0, "state1g7" : 0, "state1g8" : 0 }
        data["state1g%d" % (self.actualProfile + 1)] = 1

        for i in xrange(7):
            data["value2g%d" % (i + 1)] = str(self.profiles[self.actualProfile][i])
        #endfor

        self.showItems(**data)
    #enddef


    def button1ButtonRelease(self):
        ''' export '''
        try:
            with open(os.path.join(defines.usbPath, self.profilesFilename), "w") as f:
                f.write(json.dumps(self.profiles, sort_keys=True, indent=4, separators=(',', ': ')))
            #endwith
        except Exception:
            self.logger.exception("export exception:")
            self.display.hw.beepAlarm(3)
        #endtry
    #endif


    def button2ButtonRelease(self):
        ''' import '''
        try:
            with open(os.path.join(defines.usbPath, self.profilesFilename), "r") as f:
                self.profiles = json.loads(f.read())
            #endwith
            self._setProfile()
            return
        except Exception:
            self.logger.exception("import exception:")
            self.display.hw.beepAlarm(3)
        #endtry

        try:
            with open(os.path.join(defines.dataPath, self.profilesFilename), "r") as f:
                self.profiles = json.loads(f.read())
            #endwith
            self._setProfile()
        except Exception:
            self.logger.exception("import exception:")
            self.display.hw.beepAlarm(3)
        #endtry
    #endif


    def state1g1ButtonRelease(self):
        self._setProfile(0)
    #enddef


    def state1g2ButtonRelease(self):
        self._setProfile(1)
    #enddef


    def state1g3ButtonRelease(self):
        self._setProfile(2)
    #enddef


    def state1g4ButtonRelease(self):
        self._setProfile(3)
    #enddef


    def state1g5ButtonRelease(self):
        self._setProfile(4)
    #enddef


    def state1g6ButtonRelease(self):
        self._setProfile(5)
    #enddef


    def state1g7ButtonRelease(self):
        self._setProfile(6)
    #enddef


    def state1g8ButtonRelease(self):
        self._setProfile(7)
    #enddef


    def minus2g1Button(self):
        return self._value(100, 22000, 0, -10)
    #enddef


    def plus2g1Button(self):
        return self._value(100, 22000, 0, 10)
    #enddef


    def minus2g2Button(self):
        return self._value(100, 22000, 1, -10)
    #enddef


    def plus2g2Button(self):
        return self._value(100, 22000, 1, 10)
    #enddef


    def minus2g3Button(self):
        return self._value(12, 800, 2, -1)
    #enddef


    def plus2g3Button(self):
        return self._value(12, 800, 2, 1)
    #enddef


    def minus2g4Button(self):
        return self._value(12, 800, 3, -1)
    #enddef


    def plus2g4Button(self):
        return self._value(12, 800, 3, 1)
    #enddef


    def minus2g5Button(self):
        return self._value(0, 63, 4, -1)
    #enddef


    def plus2g5Button(self):
        return self._value(0, 63, 4, 1)
    #enddef


    def minus2g6Button(self):
        return self._value(-128, 127, 5, -1)
    #enddef


    def plus2g6Button(self):
        return self._value(-128, 127, 5, 1)
    #enddef


    def minus2g7Button(self):
        return self._value(0, 10000, 6, -10)
    #enddef


    def plus2g7Button(self):
        return self._value(0, 10000, 6, 10)
    #enddef

#endclass


class PageTiltProfiles(ProfilesPage):

    def __init__(self, display):
        self.profilesFilename = "tilt_profiles.json"
        self.profilesNames = display.hw.getTiltProfilesNames()
        self.profiles = display.hw.getTiltProfiles()
        self.pageTitle = "Admin - Tilt Profiles"
        super(PageTiltProfiles, self).__init__(display)
    #enddef


    def show(self):
        super(PageTiltProfiles, self).show()
        self._setProfile()
        self.display.page_tiltmove.changeProfiles(False)
    #enddef


    def button3ButtonRelease(self):
        ''' test '''
        self.display.hw.setTiltTempProfile(self.profiles[self.actualProfile])
        return "tiltmove"
    #endif


    def button4ButtonRelease(self):
        ''' save '''
        self.display.page_tiltmove.changeProfiles(True)
        self.display.hw.setTiltProfiles(self.profiles)
        return super(PageTiltProfiles, self).backButtonRelease()
    #enddef


    def backButtonRelease(self):
        self.display.page_tiltmove.changeProfiles(True)
        self.profiles = self.display.hw.getTiltProfiles()
        return super(PageTiltProfiles, self).backButtonRelease()
    #endif

#endclass


class PageTowerProfiles(ProfilesPage):

    def __init__(self, display):
        self.profilesFilename = "tower_profiles.json"
        self.profilesNames = display.hw.getTowerProfilesNames()
        self.profiles = display.hw.getTowerProfiles()
        self.pageTitle = "Admin - Tower Profiles"
        super(PageTowerProfiles, self).__init__(display)
    #enddef


    def show(self):
        super(PageTowerProfiles, self).show()
        self._setProfile()
        self.display.page_towermove.changeProfiles(False)
    #enddef


    def button3ButtonRelease(self):
        ''' test '''
        self.display.hw.setTowerTempProfile(self.profiles[self.actualProfile])
        return "towermove"
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        self.display.page_towermove.changeProfiles(True)
        self.display.hw.setTowerProfiles(self.profiles)
        return super(PageTowerProfiles, self).backButtonRelease()
    #enddef


    def backButtonRelease(self):
        self.display.page_towermove.changeProfiles(True)
        self.profiles = self.display.hw.getTowerProfiles()
        return super(PageTowerProfiles, self).backButtonRelease()
    #enddef

#endclass


class PageState(Page):

    def __init__(self, display):
        self.pageUI = "setup"
        self.pageTitle = "Admin - State"
        super(PageState, self).__init__(display)
#        self.autorepeat = {
#                "minus2g1" : (5, 1), "plus2g1" : (5, 1),
#                "minus2g2" : (5, 1), "plus2g2" : (5, 1),
#                "minus2g3" : (5, 1), "plus2g3" : (5, 1),
#                "minus2g4" : (5, 1), "plus2g4" : (5, 1),
#                "minus2g5" : (5, 1), "plus2g5" : (5, 1),
#                "minus2g6" : (5, 1), "plus2g6" : (5, 1),
#                "minus2g7" : (5, 1), "plus2g7" : (5, 1),
#                "minus2g8" : (5, 1), "plus2g8" : (5, 1),
#                }
        self.items.update({
                "label1g1" : "Fan 1",
                "label1g2" : "Fan 2",
                "label1g3" : "Fan 3",
                "label1g4" : "Fan 4",
                "label1g5" : "UV LED",
                "label1g6" : "Cam LED",
                "label1g7" : "Power LED",
                "label1g8" : "Cover",

                "label2g1" : "Fan 1 RPM",
                "label2g2" : "Fan 2 RPM",
                "label2g3" : "Fan 3 RPM",
                "label2g4" : "Fan 4 RPM",
                "label2g5" : "UV LED temperature",
                "label2g6" : "Ambient temperature",
                "label2g7" : "CPU core temperature",

                "back" : "Back",
                })
        self.callbackPeriod = 0.5
    #enddef


    def show(self):
        self.oldValues = {}
        super(PageState, self).show()
    #enddef


    def menuCallback(self):
        items = {}
        fan1, fan2, fan3, fan4 = self.display.hw.getFans()
        self._setItem(items, "state1g1", fan1)
        self._setItem(items, "state1g2", fan2)
        self._setItem(items, "state1g3", fan3)
        self._setItem(items, "state1g4", fan4)
        self._setItem(items, "state1g5", self.display.hw.getUvLedState())
        self._setItem(items, "state1g6", self.display.hw.getCameraLedState())
        self._setItem(items, "state1g7", self.display.hw.getPowerLedState())
        self._setItem(items, "state1g8", self.display.hw.getCoverState())
        rpm1, rpm2, rpm3, rpm4 = self.display.hw.getRPMs()
        self._setItem(items, "value2g1", rpm1)
        self._setItem(items, "value2g2", rpm2)
        self._setItem(items, "value2g3", rpm3)
        self._setItem(items, "value2g4", rpm4)
        self._setItem(items, "value2g5", self.display.hw.getTemperatureUVLED())
        self._setItem(items, "value2g6", self.display.hw.getTemperatureSystem())

        if len(items):
            self.showItems(**items)
        #endif
    #enddef


    def state1g1ButtonRelease(self):
        fan1, fan2, fan3, fan4 = self.display.hw.getFans()
        fan1 = not fan1
        self.display.hw.fans(fan1, fan2, fan3, fan4)
    #enddef


    def state1g2ButtonRelease(self):
        fan1, fan2, fan3, fan4 = self.display.hw.getFans()
        fan2 = not fan2
        self.display.hw.fans(fan1, fan2, fan3, fan4)
    #enddef


    def state1g3ButtonRelease(self):
        fan1, fan2, fan3, fan4 = self.display.hw.getFans()
        fan3 = not fan3
        self.display.hw.fans(fan1, fan2, fan3, fan4)
    #enddef


    def state1g4ButtonRelease(self):
        fan1, fan2, fan3, fan4 = self.display.hw.getFans()
        fan4 = not fan4
        self.display.hw.fans(fan1, fan2, fan3, fan4)
    #enddef


    def state1g5ButtonRelease(self):
        self.display.hw.uvLed(not self.display.hw.getUvLedState())
    #enddef


    def state1g6ButtonRelease(self):
        self.display.hw.cameraLed(not self.display.hw.getCameraLedState())
    #enddef


    def state1g7ButtonRelease(self):
        self.display.hw.powerLed("warn" if self.display.hw.getPowerLedState() else "normal")
    #enddef


    def state1g8ButtonRelease(self):
        self.showItems(state1g8 = 1 if self.display.hw.getCoverState() else 0)
        self.display.hw.beepAlarm(3)
    #enddef


    def minus2g1Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def plus2g1Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def minus2g2Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def plus2g2Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def minus2g3Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def plus2g3Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def minus2g4Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def plus2g4Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def minus2g5Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def plus2g5Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def minus2g6Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def plus2g6Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def minus2g7Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def plus2g7Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def minus2g8Button(self):
        self.display.hw.beepAlarm(3)
    #enddef


    def plus2g8Button(self):
        self.display.hw.beepAlarm(3)
    #enddef

#endclass
