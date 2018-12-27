# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from time import sleep
import json
import subprocess

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
                continueFce = self.turnoffContinue,
                line1 = "Do you really want to",
                line2 = "turn off the printer?")
        return "confirm"
    #enddef


    def turnoffContinue(self):
        pageWait = PageWait(self.display, line2 = "Shutting down")
        pageWait.show()
        self.display.shutDown(self.display.config.autoOff)
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


    def _onOff(self, index, val):
        self.temp[val] = not self.temp[val]
        self.changed[val] = "on" if self.temp[val] else "off"
        self.showItems(**{ 'state1g%d' % (index + 1) : 1 if self.temp[val] else 0 })
    #enddef


    def _value(self, index, val, valmin, valmax, change):
        if valmin <= self.temp[val] + change <= valmax:
            self.temp[val] += change
            self.changed[val] = str(self.temp[val])
            self.showItems(**{ 'value2g%d' % (index + 1) : str(self.temp[val]) })
        else:
            self.display.hw.beepAlarm(1)
        #endif
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
        if not self.display.hwConfig.calibrated:
            self.display.page_confirm.setParams(
                    continueFce = self.printContinue,
                    line1 = "Printer is not calibrated!",
                    line2 = "Calibrate now?")
            return "confirm"
        #endif

        return "sourceselect"
    #enddef


    def printContinue(self):
        return "tiltcalib"
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
                'line1' : "Serial number: %s" % self.display.hwConfig.sn,
                'line2' : "System: %s" % self.display.hwConfig.os.name,
                'line3' : "System version: %s" % self.display.hwConfig.os.version,
                'line4' : "Firwmare version: %s" % defines.swVersion,
                })
    #enddef


    def show(self):
        self.items['line5'] = "Controller version: %s" % self.display.hw.getControllerVersion()
        self.items['line6'] = "Controller number: %s" % self.display.hw.getControllerSerial()
        super(PageSysInfo, self).show()
    #enddef

#endclass


class PageHardwareInfo(Page):

    def __init__(self, display):
        self.pageUI = "sysinfo"
        self.pageTitle = "Hardware Information"
        super(PageHardwareInfo, self).__init__(display)
        self.callbackPeriod = 2
    #enddef


    def show(self):
        self.oldValues = {}
        self.items['line1'] = "Tower height: %d (%.2f mm)" % (self.display.hwConfig.towerHeight, self.display.hwConfig.calcMM(self.display.hwConfig.towerHeight))
        self.items['line2'] = "Tilt height: %d" % self.display.hwConfig.tiltHeight

        super(PageHardwareInfo, self).show()
    #enddef


    def menuCallback(self):
        items = {}
        self._setItem(items, 'line3', "Fans [RPM]:  %s" % "  ".join(self.display.hw.getFansRpm()))
        self._setItem(items, 'line4', "Temperatures [C]:  %s" % "  ".join(self.display.hw.getTemperatures()))
        # cpu temp
        self._setItem(items, 'line5', "UV LED voltages [V]:  %s" % "  ".join(self.display.hw.getUvLedVoltages()))
        # resin sensor
        # cover state
        # power button state

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
        devices = self.display.inet.getDevices()
        if devices:
            if "ap0" in devices:
                # AP mode
                try:
                    with open(defines.wifiSetupFile, "r") as f:
                        wifiData = json.loads(f.read())
                    #endwith
                    ip = self.display.inet.getIp("ap0")
                    items["line1"] = "SSID: %s  password: %s" % (wifiData['ssid'], wifiData['psk'])
                    items["line2"] = "Setup URL: %s%s" % (ip, defines.wifiSetupURI)
                    items["qr1label"] = "WiFi"
                    items["qr1"] = "WIFI:S:%s;T:WPA;P:%s;H:false;" % (wifiData['ssid'], wifiData['psk'])
                    items["qr2label"] = "Setup URL"
                    items["qr2"] = "http://%s%s" % (ip, defines.wifiSetupURI)
                except Exception:
                    self.logger.exception("wifi setup file exception:")
                    items["line1"] = "Error reading WiFi setup!"
                    items["line2"] = ""
                    items["qr1label"] = ""
                    items["qr1"] = ""
                    items["qr2label"] = ""
                    items["qr2"] = ""
                #endtry
            else:
                # client mode
                ip = self.display.inet.getIp()
                items["line1"] = "IP address: %s" % ip
                items["line2"] = "Hostname: %s" % self.display.inet.getHostname()
                items["qr1label"] = "Logfile"
                items["qr1"] = "http://%s/log" % ip
                items["qr2label"] = "MC debug"
                items["qr2"] = "http://%s/debug" % ip
            #endif
        else:
            # no internet connection
            items["line1"] = "Not connected to network"
            items["line2"] = ""
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
        try:
            with open(defines.octoprintAuthFile, "r") as f:
                self.octoprintAuth = f.read()
            #endwith
        except Exception:
            self.logger.exception("octoprintAuthFile exception:")
            self.octoprintAuth = None
        #endtry
    #enddef


    def show(self):
        self.items["line1"] = "Please select project source"
        ip = self.display.inet.getIp()
        if ip != "none" and self.octoprintAuth:
            self.items["line2"] = "%s%s (%s)" % (ip, defines.octoprintURI, self.octoprintAuth)
        else:
            self.items["line2"] = "Not connected to network"
        #endif
        super(PageSrcSelect, self).show()
    #enddef


    def netChange(self):
        ip = self.display.inet.getIp()
        if ip != "none" and self.octoprintAuth:
            self.showItems(line2, "%s%s (%s)" % (ip, defines.octoprintURI, self.octoprintAuth))
        else:
            self.showItems(line2, "Not connected to network")
        #endif
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


class PageTiltTower(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = "Admin - Tilt & Tower"
        super(PageTiltTower, self).__init__(display)
        self.items.update({
                'button1' : "Tilt home",
                'button2' : "Tilt move",
                'button3' : "Tilt test",
                'button4' : "Tilt profiles",
                'button6' : "Tower home",
                'button7' : "Tower move",
                'button8' : "Tower test",
                'button9' : "Tower profiles",
                'button11' : "Turn motors off",
                'button13' : "Calibrate printer",

                'back' : "Back",
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


    def button4ButtonRelease(self):
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


    def button9ButtonRelease(self):
        return "towerprofiles"
    #enddef


    def button11ButtonRelease(self):
        self.display.hw.motorsRelease()
    #enddef


    def button13ButtonRelease(self):
        return "tiltcalib"
    #enddef

#endclass


class PageDisplay(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = "Admin - Display"
        super(PageDisplay, self).__init__(display)
        self.items.update({
                'button1' : "Chess 8",
                'button2' : "Chess 16",
                'button3' : "Grid 8",
                'button4' : "Grid 16",
                'button5' : "Maze",

                'button6' : "USB:/test.png",

                'button11' : "Black",
                'button12' : "Inverse",

                'back' : "Back",
                })
    #enddef


    def show(self):
        self.items['button14'] = "UV off" if self.display.hw.getUvLedState() else "UV on"
        self.button2ButtonRelease()
        super(PageDisplay, self).show()
    #enddef


    def button1ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice8_1440x2560.png"))
    #enddef


    def button2ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice16_1440x2560.png"))
    #enddef


    def button3ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "mrizka8_1440x2560.png"))
    #enddef


    def button4ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "mrizka16_1440x2560.png"))
    #enddef


    def button5ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "bludiste_1440x2560.png"))
    #enddef


    def button6ButtonRelease(self):
        try:
            self.display.screen.getImg(filename = os.path.join(defines.usbPath, "test.png"))
        except Exception:
            self.logger.exception("export exception:")
            self.display.hw.beepAlarm(3)
        #endtry
    #enddef


    def button11ButtonRelease(self):
        self.display.screen.getImgBlack()
    #enddef


    def button12ButtonRelease(self):
        self.display.screen.inverse()
    #enddef


    def button14ButtonRelease(self):
        state = not self.display.hw.getUvLedState()
        self.showItems(button14 = "UV off" if state else "UV on")
        self.display.hw.uvLed(state)
    #enddef


    def backButtonRelease(self):
        self.display.hw.uvLed(False)
        return super(PageDisplay, self).backButtonRelease()
    #enddef

#endclass


class PageAdmin(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = "Admin - Main Page"
        super(PageAdmin, self).__init__(display)
        self.items.update({
                'button1' : "Tilt & Tower",
                'button2' : "Display",
                'button3' : "Fans & LEDs",
                'button4' : "Setup",
                'button5' : "Hardware Info",

                'button6' : "Flash MC",
                'button7' : "Erase MC EEPROM",
                'button8' : "MC2Net (bootloader)",
                'button9' : "MC2Net (firmware)",

                'button11' : "Networking",
                'button12' : "USB update",
                'button13' : "Net update",
                'button14' : "Keyboard test",

                'back' : "Back",
                })
    #enddef


    def button1ButtonRelease(self):
        return "tilttower"
    #enddef


    def button2ButtonRelease(self):
        return "display"
    #enddef


    def button3ButtonRelease(self):
        return "fansleds"
    #enddef


    def button4ButtonRelease(self):
        return "setup"
    #enddef


    def button5ButtonRelease(self):
        return "hwinfo"
    #enddef


    def button6ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.button6Continue,
                line1 = "This overwrites the motion",
                line2 = "controller with supplied firmware.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def button6Continue(self):
        pageWait = PageWait(self.display, line2 = "Overwriting the motion controller")
        pageWait.show()
        self.display.hw.flashMC()
        return "_BACK_"
    #enddef


    def button7ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.button7Continue,
                line1 = "This will erase all profiles",
                line2 = "and other MC settings.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def button7Continue(self):
        pageWait = PageWait(self.display, line2 = "Erasing EEPROM")
        pageWait.show()
        self.display.hw.eraseEeprom()
        return "_BACK_"
    #enddef


    def button8ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.mc2net,
                continueParmas = { 'bootloader' : True },
                line1 = "This shuts down GUI and connect",
                line2 = "the MC bootloader to TCP port.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def button9ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.mc2net,
                continueParmas = { 'bootloader' : False },
                line1 = "This shuts down GUI and connect",
                line2 = "the motion controller to TCP port.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def mc2net(self, bootloader = False):
        baudrate = 19200 if bootloader else 115200
        pageWait = PageWait(self.display,
            line1 = "Master is down. Baudrate is %d" % baudrate,
            line2 = "Serial line is redirected to port %d" % defines.socatPort,
            line3 = "Power the printer off to continue ;-)" if bootloader else 'Type "!shdn 0" to power off ;-)')
        pageWait.show()
        if bootloader:
            self.display.hw.resetMc()
        #endif
        pid = subprocess.Popen([
            defines.Mc2NetCommand,
            defines.motionControlDevice,
            str(defines.socatPort),
            str(baudrate)]).pid
        self.display.shutDown(False)
    #enddef


    def button11ButtonRelease(self):
        return "networking"
    #enddef


    def button12ButtonRelease(self):
        # check new firmware defines
        osConfig = libConfig.OsConfig(os.path.join(defines.usbUpdatePath, "etc/os-release"))
        osConfig.logAllItems()
        fwConfig = libConfig.FwConfig(os.path.join(defines.usbUpdatePath + defines.swPath, "defines.py"))
        fwConfig.logAllItems()
        if fwConfig.version.startswith("Gen3"):
            self.display.page_confirm.setParams(
                    continueFce = self.performUpdate,
                    continueParmas = { 'updateCommand' : defines.usbUpdateCommand },
                    line1 = "Image release: " + osConfig.versionId,
                    line2 = "Firmware version: " + fwConfig.version,
                    line3 = "Proceed update?")
            return "confirm"
        else:
            message = "Wrong firmware signature"
        #endif

        self.logger.warning(message)
        self.display.page_error.setParams(line1 = "USB update was rejected:", line2 = message)
        return "error"
    #enddef


    def button13ButtonRelease(self):
        # check network connection
        if self.display.inet.getIp() != "none":
            # download version info
            configText = self.display.inet.httpRequestEX(defines.netUpdateVersionURL)
            if configText is not None:
                netConfig = libConfig.NetConfig()
                netConfig.parseText(configText)
                netConfig.logAllItems()
                # check versions
                if netConfig.firmware.startswith("Gen3"):
                    if netConfig.firmware != defines.swVersion or netConfig.image != self.display.hwConfig.os.versionId:
                        self.display.page_confirm.setParams(
                                continueFce = self.performUpdate,
                                continueParmas = { 'updateCommand' : defines.netUpdateCommand },
                                line1 = "Image release: " + netConfig.image,
                                line2 = "Firmware version: " + netConfig.firmware,
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
        self.display.page_error.setParams(line1 = "Net update was rejected:", line2 = message)
        return "error"
    #enddef


    def performUpdate(self, updateCommand):
        import shutil

        pageWait = PageWait(self.display, line1 = "Updating")
        pageWait.show()

        process = subprocess.Popen(updateCommand, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
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
            self.display.shutDown(False)
        else:
            pageWait.showItems(
                    line1 = "Update done",
                    line2 = "Shutting down")
            self.display.shutDown(self.display.config.autoOff)
        #endif
    #enddef


    def button14ButtonRelease(self):
        return "keyboard"
    #enddef

#endclass


class PageSetup(Page):

    def __init__(self, display):
        self.pageUI = "setup"
        self.pageTitle = "Admin - Setup"
        super(PageSetup, self).__init__(display)
        self.autorepeat = {
                'minus2g1' : (5, 1), 'plus2g1' : (5, 1),
                'minus2g2' : (5, 1), 'plus2g2' : (5, 1),
                'minus2g3' : (5, 1), 'plus2g3' : (5, 1),
                }
        self.items.update({
                'label1g1' : "Fan check",
                'label1g2' : "Cover check",
                'label1g3' : "MC version check",

                'label2g1' : "Screw (mm/rot)",
                'label2g2' : "Tower msteps",
                'label2g3' : "Tilt msteps",

                'button1' : "Export",
                'button2' : "Import",
                'button4' : "Save",
                'back' : "Back",
                })
        self.changed = {}
        self.temp = {}
        self.backupFilename = os.path.join(defines.usbPath, defines.hwConfigFileName)
    #enddef


    def show(self):
        self.temp['screwmm'] = self.display.hwConfig.screwMm
        self.temp['towerheight'] = self.display.hwConfig.towerHeight
        self.temp['tiltheight'] = self.display.hwConfig.tiltHeight

        self.items['value2g1'] = str(self.temp['screwmm'])
        self.items['value2g2'] = str(self.temp['towerheight'])
        self.items['value2g3'] = str(self.temp['tiltheight'])

        self.temp['fancheck'] = self.display.hwConfig.fanCheck
        self.temp['covercheck'] = self.display.hwConfig.coverCheck
        self.temp['mcversioncheck'] = self.display.hwConfig.MCversionCheck

        self.items['state1g1'] = 1 if self.temp['fancheck'] else 0
        self.items['state1g2'] = 1 if self.temp['covercheck'] else 0
        self.items['state1g3'] = 1 if self.temp['mcversioncheck'] else 0

        super(PageSetup, self).show()
    #enddef


    def button1ButtonRelease(self):
        ''' export '''
        if not self.display.hwConfig.writeFile(self.backupFilename):
            self.display.hw.beepAlarm(3)
        #endif
    #enddef


    def button2ButtonRelease(self):
        ''' import '''
        try:
            with open(self.backupFilename, "r") as f:
                self.display.hwConfig.parseText(f.read())
            #endwith
        except Exception:
            self.logger.exception("import exception:")
            self.display.hw.beepAlarm(3)
            return
        #endtry

        if not self.display.hwConfig.writeFile(defines.hwConfigFile):
            self.display.hw.beepAlarm(4)
        #endif

        self.show()
    #enddef


    def button4ButtonRelease(self):
        ''' save '''

        self.display.hwConfig.update(**self.changed)
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        self.display.config._parseData()
        return super(PageSetup, self).backButtonRelease()
    #endif


    def state1g1ButtonRelease(self):
        self._onOff(0, 'fancheck')
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(1, 'covercheck')
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(2, 'mcversioncheck')
    #enddef


    def minus2g1Button(self):
        return self._value(0, 'screwmm', 2, 8, -1)
    #enddef


    def plus2g1Button(self):
        return self._value(0, 'screwmm', 2, 8, 1)
    #enddef


    def minus2g2Button(self):
        return self._value(1, 'towerheight', -10, 10, 1)
    #enddef


    def plus2g2Button(self):
        return self._value(1, 'towerheight', -10, 10, 1)
    #enddef


    def minus2g3Button(self):
        return self._value(2, 'tiltheight', 1, 1600, -1)
    #enddef


    def plus2g3Button(self):
        return self._value(2, 'tiltheight', 1, 1600, 1)
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
        self.pageTitle = "Platform Calibration"
        super(PageTowerCalib, self).__init__(display)
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
    #enddef


    def prepare(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = "Platform calibration",
            line2 = "Moving platform to top")
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif

        # measure from top not from bottom with different profile
        self.display.hw.setTowerOnMax()
        pageWait.showItems(line2 = "Moving tank to start", line3 = "")
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.tiltUpWait()
        pageWait.showItems(line2 = "Moving platform down")
        self.display.hw.setTowerProfile('moveFast')
        self.display.hw.towerMoveAbsolute(self.display.hw.towerCalibPos) # move quickly to safe distance
        while not self.display.hw.isTowerOnPosition():
            sleep(0.25)
            pageWait.showItems(line3 = self.display.hw.getTowerPosition())
        #endwhile
        self.items["value"] = self.display.hw.getTowerPosition()
        self.display.hw.powerLed("normal")
        self.moving = False
    #enddef


    def backButtonRelease(self):
        position = self.display.hw.getTowerPositionMicroSteps()
        if position is None:
            self.logger.error("Invalid tower position to save!")
            self.display.hw.beepAlarm(3)
        else:
            towerHeight = self.display.hw.towerEnd - self.display.hw.getTowerPositionMicroSteps()
            self.logger.debug("Tower height: %d", towerHeight)
            self.display.hwConfig.update(towerheight = towerHeight, calibrated = "yes")
            if not self.display.hwConfig.writeFile():
                self.display.hw.beepAlarm(3)
                sleep(1)
                self.display.hw.beepAlarm(3)
            #endif
            pageWait = PageWait(self.display,
                line1 = "Calibration done!",
                line2 = "Moving platform to top")
            pageWait.show()
            retc = self._syncTower(pageWait)
            if retc == "error":
                return retc
            #endif
        #endif
        self.display.goBack(2)
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
        self.pageTitle = "Tank Calibration"
        super(PageTiltCalib, self).__init__(display)
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
    #enddef


    def prepare(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = "Tank calibration",
            line2 = "Moving platform to top")
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
        pageWait.showItems(line2 = "Moving tank to base position",)
        self.display.hw.setTiltProfile('layer')
        self.display.hw.tiltDownWait()
        self.display.hw.tiltUpWait()
        self.display.hw.powerLed("normal")
        self.items["value"] = self.display.hw.getTiltPosition()
        self.moving = False
    #enddef


    def backButtonRelease(self):
        position = self.display.hw.getTiltPositionMicroSteps()
        if position is None:
            self.logger.error("Invalid tilt position to save!")
            self.display.hw.beepAlarm(3)
        else:
            self.display.hwConfig.update(tiltheight = position)
            if not self.display.hwConfig.writeFile():
                self.display.hw.beepAlarm(3)
                sleep(1)
                self.display.hw.beepAlarm(3)
            #endif
        #endif
        return "towercalib"
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


    def _value(self, index, valmin, valmax, change):
        if valmin <= self.profiles[self.actualProfile][index] + change <= valmax:
            self.profiles[self.actualProfile][index] += change
            self.showItems(**{ 'value2g%d' % (index + 1) : str(self.profiles[self.actualProfile][index]) })
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
    #enddef


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
    #enddef


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
        return self._value(0, 100, 22000, -10)
    #enddef


    def plus2g1Button(self):
        return self._value(0, 100, 22000, 10)
    #enddef


    def minus2g2Button(self):
        return self._value(1, 100, 22000, -10)
    #enddef


    def plus2g2Button(self):
        return self._value(1, 100, 22000, 10)
    #enddef


    def minus2g3Button(self):
        return self._value(2, 12, 800, -1)
    #enddef


    def plus2g3Button(self):
        return self._value(2, 12, 800, 1)
    #enddef


    def minus2g4Button(self):
        return self._value(3, 12, 800, -1)
    #enddef


    def plus2g4Button(self):
        return self._value(3, 12, 800, 1)
    #enddef


    def minus2g5Button(self):
        return self._value(4, 0, 63, -1)
    #enddef


    def plus2g5Button(self):
        return self._value(4, 0, 63, 1)
    #enddef


    def minus2g6Button(self):
        return self._value(5, -128, 127, -1)
    #enddef


    def plus2g6Button(self):
        return self._value(5, -128, 127, 1)
    #enddef


    def minus2g7Button(self):
        return self._value(6, 0, 10000, -10)
    #enddef


    def plus2g7Button(self):
        return self._value(6, 0, 10000, 10)
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


class PageFansLeds(Page):

    def __init__(self, display):
        self.pageUI = "setup"
        self.pageTitle = "Admin - Fans & LEDs"
        super(PageFansLeds, self).__init__(display)
        self.autorepeat = {
                'minus2g1' : (5, 1), 'plus2g1' : (5, 1),
                'minus2g2' : (5, 1), 'plus2g2' : (5, 1),
                'minus2g3' : (5, 1), 'plus2g3' : (5, 1),
                'minus2g4' : (5, 1), 'plus2g4' : (5, 1),
                'minus2g5' : (5, 1), 'plus2g5' : (5, 1),
                'minus2g6' : (5, 1), 'plus2g6' : (5, 1),
                'minus2g7' : (5, 1), 'plus2g7' : (5, 1),
#                'minus2g8' : (5, 1), 'plus2g8' : (5, 1),
                }
        self.items.update({
                'label1g1' : "Fan 1",
                'label1g2' : "Fan 2",
                'label1g3' : "Fan 3",
                'label1g4' : "Fan 4",
                'label1g5' : "UV LED",
                'label1g6' : "Cam LED",

                'label2g1' : "Fan 1 PWM",
                'label2g2' : "Fan 2 PWM",
                'label2g3' : "Fan 3 PWM",
                'label2g4' : "Fan 4 PWM",
                'label2g5' : "UV LED PWM",
                'label2g6' : "Power LED PWM",
                'label2g7' : "Power LED mode",

                'button4' : "Save",
                'back' : "Back",
                })
        self.callbackPeriod = 0.5
        self.changed = {}
        self.temp = {}
        self.valuesToSave = list(('fan1pwm', 'fan2pwm', 'fan3pwm', 'fan4pwm', 'uvledpwm', 'pwrledpwm'))
    #enddef


    def show(self):
        self.oldValues = {}
        super(PageFansLeds, self).show()
    #enddef


    def menuCallback(self):
        items = {}
        self.temp['fs1'], self.temp['fs2'], self.temp['fs3'], self.temp['fs4'] = self.display.hw.getFans()
        self.temp['uls'] = self.display.hw.getUvLedState()
        self.temp['cls'] = self.display.hw.getCameraLedState()
        self._setItem(items, 'state1g1', self.temp['fs1'])
        self._setItem(items, 'state1g2', self.temp['fs2'])
        self._setItem(items, 'state1g3', self.temp['fs3'])
        self._setItem(items, 'state1g4', self.temp['fs4'])
        self._setItem(items, 'state1g5', self.temp['uls'])
        self._setItem(items, 'state1g6', self.temp['cls'])

        self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm'] = self.display.hw.getFansPwm()
        self.temp['uvledpwm'] = self.display.hw.getUvLedPwm()
        self.temp['pwrledpwm'] = self.display.hw.getPowerLedPwm()
        self.temp['pwrledstt'] = self.display.hw.getPowerLedState()
        self._setItem(items, 'value2g1', self.temp['fan1pwm'])
        self._setItem(items, 'value2g2', self.temp['fan2pwm'])
        self._setItem(items, 'value2g3', self.temp['fan3pwm'])
        self._setItem(items, 'value2g4', self.temp['fan4pwm'])
        self._setItem(items, 'value2g5', self.temp['uvledpwm'])
        self._setItem(items, 'value2g6', self.temp['pwrledpwm'])
        self._setItem(items, 'value2g7', self.temp['pwrledstt'])

        if len(items):
            self.showItems(**items)
        #endif
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        # filter only wanted items
        filtered = { k : v for k, v in filter(lambda t: t[0] in self.valuesToSave, self.changed.iteritems()) }
        self.display.hwConfig.update(**filtered)
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        self.display.config._parseData()
        return super(PageFansLeds, self).backButtonRelease()
    #endif


    def state1g1ButtonRelease(self):
        self._onOff(0, 'fs1')
        self.display.hw.setFans({ 0 : self.temp['fs1'] })
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(1, 'fs2')
        self.display.hw.setFans({ 1 : self.temp['fs2'] })
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(2, 'fs3')
        self.display.hw.setFans({ 2 : self.temp['fs3'] })
    #enddef


    def state1g4ButtonRelease(self):
        self._onOff(3, 'fs4')
        self.display.hw.setFans({ 3 : self.temp['fs4'] })
    #enddef


    def state1g5ButtonRelease(self):
        self._onOff(4, 'uls')
        self.display.hw.uvLed(self.temp['uls'])
    #enddef


    def state1g6ButtonRelease(self):
        self._onOff(5, 'cls')
        self.display.hw.cameraLed(self.temp['cls'])
    #enddef


    def minus2g1Button(self):
        self._value(0, 'fan1pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm']))
    #enddef


    def plus2g1Button(self):
        self._value(0, 'fan1pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm']))
    #enddef


    def minus2g2Button(self):
        self._value(1, 'fan2pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm']))
    #enddef


    def plus2g2Button(self):
        self._value(1, 'fan2pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm']))
    #enddef


    def minus2g3Button(self):
        self._value(2, 'fan3pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm']))
    #enddef


    def plus2g3Button(self):
        self._value(2, 'fan3pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm']))
    #enddef


    def minus2g4Button(self):
        self._value(3, 'fan4pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm']))
    #enddef


    def plus2g4Button(self):
        self._value(3, 'fan4pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'], self.temp['fan4pwm']))
    #enddef


    def minus2g5Button(self):
        self._value(4, 'uvledpwm', 0, 100, -5)
        self.display.hw.setUvLedPwm(self.temp['uvledpwm'])
    #enddef


    def plus2g5Button(self):
        self._value(4, 'uvledpwm', 0, 100, 5)
        self.display.hw.setUvLedPwm(self.temp['uvledpwm'])
    #enddef


    def minus2g6Button(self):
        self._value(5, 'pwrledpwm', 0, 100, -5)
        self.display.hw.setPowerLedPwm(self.temp['pwrledpwm'])
    #enddef


    def plus2g6Button(self):
        self._value(5, 'pwrledpwm', 0, 100, 5)
        self.display.hw.setPowerLedPwm(self.temp['pwrledpwm'])
    #enddef


    def minus2g7Button(self):
        self._value(6, 'pwrledstt', 0, 2, -1)
        self.display.hw.powerLedRaw(self.temp['pwrledstt'])
    #enddef


    def plus2g7Button(self):
        self._value(6, 'pwrledstt', 0, 2, 1)
        self.display.hw.powerLedRaw(self.temp['pwrledstt'])
    #enddef

#endclass


class PageNetworking(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = "Admin - Networking"
        super(PageNetworking, self).__init__(display)
        self.items.update({
                'button1' : "WiFi AP (once)",
                'button2' : "WiFi Client (once)",
                'button3' : "WiFi Off (once)",

                'button6' : "WiFi AP (always)",
                'button7' : "WiFi Client (always)",
                'button8' : "WiFi Off (always)",

                'button11' : "Netinfo",
                'button12' : "State",

                'back' : "Back",
                })
    #enddef


    def button1ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.setWifi,
                continueParmas = { 'mode' : 'ap', 'scope' : 'on' },
                line1 = "This switches WiFi to access point mode",
                line2 = "only until printer's reboot.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def button2ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.setWifi,
                continueParmas = { 'mode' : 'cl', 'scope' : 'on' },
                line1 = "This switches WiFi client (normal) mode",
                line2 = "only until printer's reboot.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def button3ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.setWifi,
                continueParmas = { 'mode' : 'of', 'scope' : 'on' },
                line1 = "This turns WiFi off",
                line2 = "only until printer's reboot.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def button6ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.setWifi,
                continueParmas = { 'mode' : 'ap', 'scope' : 'al' },
                line1 = "This switches WiFi to access point mode",
                line2 = "and sets it as default after printer's reboot.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def button7ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.setWifi,
                continueParmas = { 'mode' : 'cl', 'scope' : 'al' },
                line1 = "This switches WiFi client (normal) mode",
                line2 = "and sets it as default after printer's reboot.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def button8ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.setWifi,
                continueParmas = { 'mode' : 'of', 'scope' : 'al' },
                line1 = "This turns WiFi off and it will be",
                line2 = "disabled after printer's reboot.",
                line3 = "Are you sure?")
        return "confirm"
    #enddef


    def setWifi(self, mode, scope):
        retc = subprocess.call([defines.WiFiCommand, mode, scope])
        if retc:
            self.logger.error("%s failed with code %d", defines.WiFiCommand, retc)
            self.display.page_error.setParams(line1 = "WiFi mode change failed!")
            return "error"
        #endif
        return "_BACK_"
    #enddef


    def button11ButtonRelease(self):
        return "netinfo"
    #enddef


    def button12ButtonRelease(self):
        return "networkstate"
    #enddef

#endclass


class PageNetworkState(Page):

    def __init__(self, display):
        self.pageUI = "sysinfo"
        self.pageTitle = "Network State"
        super(PageNetworkState, self).__init__(display)
    #enddef


    # TODO net state - mode, all ip with devices, all uri (log, debug, display, octoprint)
    def fillData(self):
        items = {}
        devlist = list()
        for addr, dev in self.display.inet.devices.iteritems():
            devlist.append("%s (%s)" % (addr, dev))
        #endfor
        items["line1"] = ", ".join(devlist)
        return items
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageNetworkState, self).show()
    #enddef


    def netChange(self):
        self.showItems(**self.fillData())
    #enddef

#endclass