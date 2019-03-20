# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from time import sleep
import json
import subprocess
import glob
import pydbus
from copy import deepcopy
import time
import re
import urllib2
import tarfile

# TODO: remove?
import shutil

import defines
import libConfig

class Page(object):

    def __init__(self, display):
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.autorepeat = {}
        self.callbackPeriod = None
        self.stack = True
        self.fill()
        try:
            with open(defines.octoprintAuthFile, "r") as f:
                self.octoprintAuth = f.read()
            #endwith
        except Exception:
            self.logger.exception("octoprintAuthFile exception:")
            self.octoprintAuth = None
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


    def setItems(self, **kwargs):
        self.items.update(kwargs)
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


    def okButtonRelease(self):
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
        self.display.shutDown(self.display.hwConfig.autoOff)
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


    # Dynamic USB path, first usb device or None
    def getSavePath(self):
        usbs = glob.glob(os.path.join(defines.mediaRootPath, '*'))

        if len(usbs) > 0:
            return usbs[0]
        else:
            return None
        #endif
    #enddef


    def _onOff(self, index, val):
        self.temp[val] = not self.temp[val]
        self.changed[val] = "on" if self.temp[val] else "off"
        self.showItems(**{ 'state1g%d' % (index + 1) : 1 if self.temp[val] else 0 })
    #enddef


    def _value(self, index, val, valmin, valmax, change, strFce = str):
        if valmin <= self.temp[val] + change <= valmax:
            self.temp[val] += change
            self.changed[val] = str(self.temp[val])
            self.showItems(**{ 'value2g%d' % (index + 1) : strFce(self.temp[val]) })
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
        self.stack = False
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


class PageFindTiltProfiles(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = "Find tilt profiles"
        super(PageFindTiltProfiles, self).__init__(display)
        self.stack = False
    #enddef


    def show(self):
        pageWait = PageWait(self.display,
            line1 = "Searching for homingFast profile",
            line2 = "Please wait...",
            line3 = "")
        pageWait.show()
        profileFast = self.display.hw.findTiltProfile(self.display.hw._tiltProfiles["homingFast"], True, 2000, 75, 10, 24, 4, 10)
        pageWait = PageWait(self.display,
            line1 = "Searching for homingSlow profile",
            line2 = "Please wait...",
            line3 = "")
        pageWait.show()
        profileSlow = self.display.hw.findTiltProfile(self.display.hw._tiltProfiles["homingSlow"], False, 1200, 30, 10, 24, 3, 12)
        if (profileSlow == None) or (profileFast == None):
            resultMsg = "not found"
        else:
            resultMsg = "found"
        #endif
        self.display.page_confirm.setParams(
                continueFce = self.findTiltProfilesStep1,
                line1 = "Fast: %s" % profileFast,
                line2 = "Slow: %s" % profileSlow,
                line3 = "Tilt profiles %s" % resultMsg)
        return "confirm"
    #enddef


    def findTiltProfilesStep1(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Tilt home calibration")
        pageWait.show()
        self.display.hw.tiltHomeCalibrateWait()
        self.display.hw.powerLed("normal")
        return "_BACK_"
    #enddef

#endclass


class PagePrintPreviewBase(Page):

    def __init__(self, display):
        super(PagePrintPreviewBase, self).__init__(display)
    #enddef


    def fillData(self):
        config = self.display.config

        if config.calibrateRegions:
            calibrateRegions = config.calibrateRegions
            calibration = config.calibrateTime
        else:
            calibrateRegions = None
            calibration = None
        #endif

        return {
            'name': config.projectName,
            'calibrationRegions': calibrateRegions,
            'date': os.path.getmtime(config.zipName),
            'layers': config.totalLayers,
            'exposure_time_first_sec': config.expTimeFirst,
            'exposure_time_sec': config.expTime,
            'calibrate_time_sec': calibration
        }
    #enddef

#endclass


class PagePrintPreview(PagePrintPreviewBase):

    def __init__(self, display):
        self.pageUI = "printpreview"
        self.pageTitle = "Project"
        super(PagePrintPreview, self).__init__(display)
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PagePrintPreview, self).show()
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = "Setting start positions")
        pageWait.show()

        self.display.hw.towerSync()
        syncRes = self.display.hw.tiltSyncWait(retries = 2)
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile

        if self.display.hw.towerSyncFailed():
            self.display.hw.motorsRelease()
            self.display.page_error.setParams(
                    line1 = "Tower homing failed!",
                    line2 = "Check printer's hardware.",
                    line3 = "Job was canceled.")
            return "error"
        #endif

        if not syncRes:
            self.display.hw.motorsRelease()
            self.display.page_error.setParams(
                    line1 = "Tilt homing failed!",
                    line2 = "Check printer's hardware.",
                    line3 = "Job was canceled.")
            return "error"
        #endif

        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.tiltUpWait()

        return "printstart"
    #enddef

#endclass


class PagePrintStart(PagePrintPreviewBase):

    def __init__(self, display):
        self.pageUI = "printstart"
        self.pageTitle = "Confirm"
        super(PagePrintStart, self).__init__(display)
    #enddef


    def show(self):
        perc = self.display.hw.calcPercVolume(self.display.config.usedMaterial + defines.resinMinVolume)
        lines = {
                'name' : self.display.config.projectName,
                'line1' : "Please fill resin tank",
                }
        if perc <= 100:
            lines.update({
                    'line2' : "at least at %d %%." % perc,
                    'line3' : "",
                    'line4' : "",
                    })
        else:
            lines.update({
                    'line2' : "to line 100 %.",
                    'line3' : "Refill will be required",
                    'line4' : "during printing.",
                    })
        self.items.update(lines)
        super(PagePrintStart, self).show()
    #enddef


    def changeButtonRelease(self):
        return "change"
    #enddef


    def contButtonRelease(self):
        return "_EXIT_MENU_"
    #enddef


    def backButtonRelease(self):
        self.display.goBack(2)
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
        return "calibration"
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
        self.display.hw.motorsHold()
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
        self.display.hw.motorsHold()
    #enddef


    def tankresButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Tank reset")
        pageWait.show()
        self.display.hw.checkCoverStatus(PageWait(self.display), pageWait)
        retc = self._syncTilt()
        if retc == "error":
            self.display.hw.motorsHold()
            return retc
        #endif
        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.tiltDownWait()
        self.display.hw.tiltUpWait()
        self.display.hw.motorsHold()
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


    def networkButtonRelease(self):
        return "network"
    #enddef


    def recalibrationButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce=self.calibrateContinue,
            line1="Calibrate printer now?")
        return "confirm"
    #enddef


    def advancedsettingsButtonRelease(self):
        return "advancedsettings"
    #enddef


    def supportButtonRelease(self):
        return "support"
    #enddef


    def calibrateContinue(self):
        return "calibration"
    #enddef

#endclass


class PageSetTime(Page):
    def __init__(self, display):
        self.pageUI = "settime"
        self.pageTitle = "Set Time"
        self.timedate = pydbus.SystemBus().get("org.freedesktop.timedate1")
        super(PageSetTime, self).__init__(display)
    # enddef

    def fillData(self):
        return {
            "ntp": self.timedate.NTP,
            "unix_timestamp_sec": time.time(),
            "timezone": self.timedate.Timezone
        }
    # enddef

    def show(self):
        self.items.update(self.fillData())
        super(PageSetTime, self).show()
    # enddef

    def ntpenableButtonRelease(self):
        self.timedate.SetNTP(True, False)
    # enddef

    def ntpdisableButtonRelease(self):
        self.timedate.SetNTP(False, False)
    # enddef

    def settimeButtonSubmit(self, data):
        self.timedate.SetNTP(False, False)
        self.timedate.SetTime(float(data['unix_timestamp_sec']) * 1000000, False, False)

        return "_BACK_"
    # enddef

#endclass


class PageSetTimezone(Page):
    zoneinfo = "/usr/share/zoneinfo/"


    def __init__(self, display):
        self.pageUI = "settimezone"
        self.pageTitle = "Set Timezone"
        self.timedate = pydbus.SystemBus().get("org.freedesktop.timedate1")

        # Available timezones
        regions = [zone.replace(PageSetTimezone.zoneinfo, "") for zone in glob.glob(os.path.join(PageSetTimezone.zoneinfo, "*"))]
        self.timezones = {}
        for region in regions:
            cities = [os.path.basename(city) for city in glob.glob(os.path.join(PageSetTimezone.zoneinfo, region, "*"))]
            self.timezones[region] = cities

        super(PageSetTimezone, self).__init__(display)
    # enddef

    def fillData(self):
        try:
            timezone = self.timedate.Timezone
            region, city = timezone.split('/')
        except:
            timezone = "UTC"
            region = "Etc"
            city = "GTM"

        return {
            "timezone": timezone,
            "region": region,
            "city": city,
            "timezones": self.timezones
        }
    # enddef

    def show(self):
        self.items.update(self.fillData())
        super(PageSetTimezone, self).show()
    # enddef

    def settimezoneButtonSubmit(self, data):
        try:
            timezone = "%s/%s" % (data['region'], data['city'])
        except:
            timezone = data['timezone']

        self.timedate.SetTimezone(timezone, False)

        return "_BACK_"
    # enddef

#endclass


class PageSetHostname(Page):
    def __init__(self, display):
        self.pageUI = "sethostname"
        self.pageTitle = "Set Hostname"
        self.hostname = pydbus.SystemBus().get("org.freedesktop.hostname1")
        super(PageSetHostname, self).__init__(display)
    # enddef

    def fillData(self):
        return {
            "hostname": self.hostname.StaticHostname
        }
    # enddef

    def show(self):
        self.items.update(self.fillData())
        super(PageSetHostname, self).show()
    # enddef

    def sethostnameButtonSubmit(self, data):
        hostname = data['hostname']
        self.hostname.SetStaticHostname(hostname, False)
        self.hostname.SetHostname(hostname, False)

        return "_BACK_"
    # enddef

#endclass


class PageSetLanguage(Page):
    def __init__(self, display):
        self.pageUI = "setlanguage"
        self.pageTitle = "Set language"
        self.locale = pydbus.SystemBus().get("org.freedesktop.locale1")
        super(PageSetLanguage, self).__init__(display)
    # enddef

    def fillData(self):
        try:
            locale = str(self.locale.Locale)
            lang = re.match(".*'LANG=(.*)'.*", locale).groups()[0]
        except:
            lang = ""

        return {
            "locale": lang
        }
    # enddef

    def show(self):
        self.items.update(self.fillData())
        super(PageSetLanguage, self).show()
    # enddef

    def setlocaleButtonSubmit(self, data):
        try:
            self.locale.SetLocale([data['locale']], False)
        except:
            self.logger.error("Setting locale failed")

        return "_BACK_"
    # enddef

#endclass

class PageAdvancedSettings(Page):

    def __init__(self, display):
        self.pageUI = "advancedsettings"
        self.pageTitle = "Advanced Settings"
        super(PageAdvancedSettings, self).__init__(display)
    #enddef


    def show(self):
        self.items.update({'showAdmin': str(self.display.hwConfig.showAdmin)})
        super(PageAdvancedSettings, self).show()
    #enddef


    def towermoveButtonRelease(self):
        return "towermove"
    #enddef


    def tiltmoveButtonRelease(self):
        return "tiltmove"
    #enddef


    def firmwareupdateButtonRelease(self):
        return "firmwareupdate"
    #enddef


    def adminButtonRelease(self):
        return "admin"
    #enddef


    def settimeButtonRelease(self):
        return "settime"
    # enddef


    def settimezoneButtonRelease(self):
        return "settimezone"
    # enddef


    def sethostnameButtonRelease(self):
        return "sethostname"
    # enddef


    def setlanguageButtonRelease(self):
        return "setlanguage"
    # enddef

#endclass


class PageSupport(Page):

    def __init__(self, display):
        self.pageUI = "support"
        self.pageTitle = "Support"
        super(PageSupport, self).__init__(display)
    #enddef


    def manualButtonRelease(self):
        return "manual"
    #enddef


    def videosButtonRelease(self):
        return "videos"
    #enddef


    def sysinfoButtonRelease(self):
        return "sysinfo"
    #enddef


    def aboutButtonRelease(self):
        return "about"
    #enddef

#endclass


class PageFirmwareUpdate(Page):

    def __init__(self, display):
        self.pageUI = "firmwareupdate"
        self.pageTitle = "Firmware Update"
        self.old_items = None
        self.rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
        super(PageFirmwareUpdate, self).__init__(display)
        self.callbackPeriod = 1
    #enddef


    def fillData(self):
        # Get list of available firmware files
        fw_files = glob.glob(os.path.join(defines.mediaRootPath, "**/*.raucb"))

        # Get Rauc flasher status and progress
        operation = None
        progress = None
        try:
            operation = self.rauc.Operation
            progress = self.rauc.Progress
        except Exception as e:
            self.logger.error("Rauc status read failed: " + str(e))
        #endtry

        return {
            'firmwares': fw_files,
            'operation': operation,
            'progress': progress
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageFirmwareUpdate, self).show()
    #enddef


    def menuCallback(self):
        items = self.fillData()
        if self.old_items != items:
            self.showItems(**items)
            self.old_items = items
    #enddef


    def flashButtonSubmit(self, data):
        try:
            fw_url = data['firmware']
        except Exception as e:
            self.logger.error("Error reading data['firmware']: " + str(e))
        #endtry

        self.display.page_confirm.setParams(
            continueFce=self.fetchUpdate,
            continueParmas={'fw_url': fw_url},
            line1="Do you really want to",
            line2="update firmware?")
        return "confirm"
    #enddef


    def fetchUpdate(self, fw_url):
        """Fetches file specified by url info ramdisk while displaying progress and watching for problems. Once the
         fetch is finished the doUpdate is called with fetched file.

        This is implemented as chunked copy from source file descriptor to the deestination file descriptor. The
        progress is updated once the cunk is copied. The source file descriptor is either standard file when the source
        is mounted USB drive or urlopen result."""

        pageWait = PageWait(self.display, line1="Fetching firmware")
        pageWait.show()

        try:
            old_progress = 0
            if fw_url.startswith("http://") or fw_url.startswith("https://"):
                # URL is HTTP, source is url
                self.logger.info("Downloading firmware %s" % fw_url)

                req = urllib2.Request(fw_url, headers={
                    'User-Agent': 'Prusa-SL1'
                })
                source = urllib2.urlopen(req, timeout=10)
                file_size = int(source.info().getheaders("Content-Length")[0])
                block_size = 8 * 1024
            else:
                # URL is file, source is file
                self.logger.info("Copying firmware %s" % fw_url)
                source = open(fw_url, "rb")
                file_size = os.path.getsize(fw_url)
                block_size = 1024 * 1024
            #endif

            with open(defines.firmwareTempFile, 'wb') as firmware_file:
                while True:
                    buffer = source.read(block_size)
                    if not buffer:
                        break
                    #endif
                    firmware_file.write(buffer)

                    progress = int(100 * firmware_file.tell() / file_size)
                    if progress != old_progress:
                        pageWait.showItems(line2="%d%%" % progress)
                        old_progress = progress
                    #endif
                #endwhile
            #endwith

            source.close()
        #endtry
        except Exception as e:
            self.logger.error("Firmware fetch failed: " + str(e))
            self.display.page_error.setParams(
                line2="Firmware fetch failed")
            return "error"
        #endexcept

        return self.doUpdate(defines.firmwareTempFile)
    #enddef


    def doUpdate(self, fw_file):
        self.logger.info("Flashing: " + fw_file)
        try:
            rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
            rauc.Install(fw_file)
        except Exception as e:
            self.logger.error("Rauc install call failed: " + str(e))
        #endtry

        pageWait = PageWait(self.display, line1="Updating firmware")
        pageWait.show()

        try:
            while True:
                operation = self.rauc.Operation
                progress = self.rauc.Progress

                pageWait.showItems(
                    line2=progress[1],
                    line3="%d%%" % progress[0]
                )

                # Check progress for update done
                if progress[1] == 'Installing done.':
                    pageWait.showItems(
                        line1="Update done",
                        line2="Shutting down")
                    sleep(3)
                    self.display.shutDown(self.display.hwConfig.autoOff, reboot=True)
                # endif

                # Check for operation failure
                if progress[1] == 'Installing failed.':
                    raise Exception("Update failed")
                # endif

                # Wait for a while
                sleep(1)
            #endwhile
        #endtry

        except Exception as e:
            self.logger.error("Rauc update failed: " + str(e))
            self.display.page_error.setParams(
                line2="Update failed")
            return "error"
        #endexcept
    #enddef

#endclass


class PageManual(Page):

    def __init__(self, display):
        self.pageUI = "manual"
        self.pageTitle = "Manual"
        super(PageManual, self).__init__(display)
    #enddef


    def show(self):
        self.items.update({
            'manual_url': defines.manualURL
        })
        super(PageManual, self).show()
    # enddef

#endclass


class PageVideos(Page):

    def __init__(self, display):
        self.pageUI = "videos"
        self.pageTitle = "Videos"
        super(PageVideos, self).__init__(display)
    #enddef

    def show(self):
        self.items.update({
            'videos_url': defines.videosURL
        })
        super(PageVideos, self).show()
    # enddef

#endclass


class PageNetwork(Page):

    def __init__(self, display):
        self.pageUI = "network"
        self.pageTitle = "Network"
        super(PageNetwork, self).__init__(display)
    #enddef


    # TODO net state - mode, all ip with devices, all uri (log, debug, display, octoprint)
    def fillData(self):
        devlist = list()
        devlist_structured = []
        for addr, dev in self.display.inet.devices.iteritems():
            devlist.append("%s (%s)" % (addr, dev))
            devlist_structured.append({
                'dev': dev,
                'addr': addr
            })
        #endfor

        wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')

        aps = {}
        for ap in wifisetup.GetAPs():
            aps[ap['ssid']] = ap

        return {
            "line1": ", ".join(devlist),
            "devlist": devlist_structured,
            'wifi_mode': wifisetup.WifiMode,
            'client_ssid': wifisetup.ClientSSID,
            'client_psk': wifisetup.ClientPSK,
            'ap_ssid': wifisetup.APSSID,
            'ap_psk': wifisetup.APPSK,
            'aps': aps.values(),
            'wifi_ssid': wifisetup.WifiConnectedSSID,
            'wifi_signal': wifisetup.WifiConnectedSignal
        }

        return items
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageNetwork, self).show()
    #enddef


    def netChange(self):
        self.showItems(**self.fillData())
    #enddef


    def clientconnectButtonSubmit(self, data):
        self.display.page_confirm.setParams(
            continueFce=self.setclient,
            continueParmas={'ssid': data['client-ssid'], 'psk': data['client-psk']},
            line1="Do you really want to",
            line2="set wifi to client mode?",
            line3 = "It may disconnect web client.")
        return "confirm"
    #enddef


    def apsetButtonSubmit(self, data):
        self.display.page_confirm.setParams(
            continueFce=self.setap,
            continueParmas={'ssid': data['ap-ssid'], 'psk': data['ap-psk']},
            line1="Do you really want to",
            line2="set wifi to ap mode?",
            line3 = "It may disconnect web client.")
        return "confirm"
    #enddef


    def wifioffButtonSubmit(self, data):
        self.display.page_confirm.setParams(
            continueFce=self.wifioff,
            line1="Do you really want to",
            line2="turn off wifi?",
            line3="It may disconnect web client.")
        return "confirm"
    #enddef


    def wifionButtonSubmit(self, data):
        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.StartAP()
            wifisetup.EnableAP()
        except:
            self.logger.error("Setting wifi ap mode (wifi on)")
        # endtry
    #enddef


    def wifioff(self):
        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.StopWifi()
            wifisetup.DisableWifi()
        except:
            self.logger.error("Turning wifi off failed")
        #endtry
        return "_BACK_"
    #enddef


    def setclient(self, ssid, psk):
        pageWait = PageWait(self.display, line2="Setting interface params...")
        pageWait.show()

        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.ClientSSID = ssid
            wifisetup.ClientPSK = psk
            wifisetup.StartClient()
            wifisetup.EnableClient()
        except:
            self.logger.error("Setting wifi client params failed: ssid:%s psk:%s", (ssid, psk))
        #endtry

        # Connecting...
        pageWait.showItems(line2="Connecting...")
        for i in range(1, 10):
            sleep(1)
            for addr, dev in self.display.inet.devices.iteritems():
                if dev == "wlan0":
                    # Connection "ok"
                    return "_BACK_"
                #endif
            #endfor
        #endfor

        # Connection fail
        self.display.page_error.setParams(
            line2="Connection failed")
        return "error"
    #enddef


    def setap(self, ssid, psk):
        pageWait = PageWait(self.display, line2="Setting interface params...")
        pageWait.show()

        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.APSSID = ssid
            wifisetup.APPSK = psk
            wifisetup.StartAP()
            wifisetup.EnableAP()
        except:
            self.logger.error("Setting wifi AP params failed: ssid:%s psk:%s", (ssid, psk))
        #endtry

        # Starting AP...
        pageWait.showItems(line2="Starting AP...")
        for i in range(1, 10):
            sleep(1)
            for addr, dev in self.display.inet.devices.iteritems():
                if dev == "ap0":
                    # AP "ok"
                    return "_BACK_"
                #endif
            #endfor
        #endfor

        # Connection fail
        self.display.page_error.setParams(
            line2="AP failed")
        return "error"
    #enddef

#endclass


class PageQRCode(Page):

    def __init__(self, display):
        self.pageUI = "qrcode"
        self.pageTitle = "QR Code"
        super(PageQRCode, self).__init__(display)
    #enddef

    # TODO: Display parametric qrcode passed from previous page

    def connectButtonRelease(self):
        return "_BACK_"
    #enddef

#endclass


class PagePrint(Page):

    def __init__(self, display, expo):
        self.pageUI = "print"
        self.pageTitle = "Print"
        self.expo = expo
        super(PagePrint, self).__init__(display)
    #enddef


    def fillData(self):
       return {
           'paused': self.expo.paused,
           'pauseunpause': self._pauseunpause_text()
       }
    #enddef


    def show(self):
        self.items.update({'showAdmin': str(self.display.hwConfig.showAdmin)})
        self.items.update(self.fillData())
        super(PagePrint, self).show()
    #enddef


    def feedmeButtonRelease(self):
        self.display.page_feedme.setItems(line1 = "Wait for layer finish please.")
        self.expo.doFeedMe()
        return "feedme"
    # enddef

    def updownButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce=self.doUpAndDown,
            line1 = "Do you really want to",
            line2 = "go platform up and down?",
            line3 = "It may affect the result!")
        return "confirm"
    # enddef

    def doUpAndDown(self):
        self.expo.doUpAndDown()
        self.display.page_systemwait.fill(
            line2 = "Up and down will be executed",
            line3 = "after layer finish")
        return "systemwait"
    #enddef

    def settingsButtonRelease(self):
        return "change"
    #enddef

    def turnoffButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce=self.exitPrint,
            line1 = "Do you really want to",
            line2 = "cancel actual job",
            line3 = "and turn off the printer?")
        return "confirm"
    #enddef


    def pauseunpauseButtonRelease(self):
        if self.expo.paused:
            self.expo.doContinue()
        else:
            self.expo.doPause()
        #endif
        self.showItems(paused=self.expo.paused, pauseunpause=self._pauseunpause_text())
    #enddef


    def adminButtonRelease(self):
        return "admin"
    #enddef


    def exitPrint(self):
        self.expo.doExitPrint()
        self.display.page_systemwait.fill(
            line2 = "Job will be canceled",
            line3 = "after layer finish")
        return "systemwait"
    #enddef


    def _pauseunpause_text(self):
        return 'UnPause' if self.expo.paused else 'Pause'
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
        self.items['total_layers'] = self.display.config.totalLayers
        self.items['layer_height_mm'] = self.display.hwConfig.calcMM(self.display.config.layerMicroSteps)
        if self.display.config.calibrateRegions:
            self.items["line1"] = "Calibration[%d]: %s" % (self.display.config.calibrateRegions, self.display.config.projectName)
            self.items["line3"] = "Exposure times: %d s / %.1f s (+%.1f)" % (int(self.display.config.expTimeFirst), self.display.config.expTime, self.display.config.calibrateTime)
            self.items['calibrate_regions'] = self.display.config.calibrateRegions
            self.items['project_name'] = self.display.config.projectName
            self.items['exp_time_first_sec'] = int(self.display.config.expTimeFirst)
            self.items['exp_time_calibration_sec'] = self.display.config.calibrateTime
            self.items['exp_time_sec'] = self.display.config.expTime
        else:
            self.items["line1"] = "Project: %s" % self.display.config.projectName
            self.items["line3"] = "Exposure times: %d s / %.1f s" % (int(self.display.config.expTimeFirst), self.display.config.expTime)
            self.items['project_name'] = self.display.config.projectName
            self.items['exp_time_first_sec'] = int(self.display.config.expTimeFirst)
            self.items['exp_time_sec'] = self.display.config.expTime
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
        self.autorepeat = {
            "exposaddsecond" : (5, 1),
            "expossubsecond" : (5, 1),
            "exposfirstaddsecond": (5, 1),
            "exposfirstsubsecond": (5, 1),
            "exposcalibrateaddsecond": (5, 1),
            "exposcalibratesubsecond": (5, 1),
        }
        self.expTime = None
        self.expTimeFirst = None
        self.expTimeCalibrate = None
    #enddef


    def show(self):
        self.expTime = self.display.config.expTime
        self.expTimeFirst = self.display.config.expTimeFirst
        if self.display.config.calibrateRegions:
            self.expTimeCalibrate = self.display.config.calibrateTime
        else:
            self.expTimeCalibrate = None
        #endif

        self.items["timeexpos"] = self.expTime
        self.items["timeexposfirst"] = self.expTimeFirst
        self.items["timeexposcalibrate"] = self.expTimeCalibrate

        super(PageChange, self).show()
    #enddef


    def backButtonRelease(self):
        self.display.config.expTime = self.expTime
        self.display.config.expTimeFirst = self.expTimeFirst
        if self.expTimeCalibrate:
            self.display.config.calibrateTime = self.expTimeCalibrate
        return super(PageChange, self).backButtonRelease()
    #endif


    def exposaddsecondButton(self):
        if self.expTime < 60:
            self.expTime = round(self.expTime + 0.5, 1)
        else:
            self.display.hw.beepAlarm(1)
        #endif
        self.showItems(timeexpos = self.expTime)
    #enddef


    def expossubsecondButton(self):
        if self.expTime > 1:
            self.expTime = round(self.expTime - 0.5, 1)
        else:
            self.display.hw.beepAlarm(1)
        #endif
        self.showItems(timeexpos = self.expTime)
    #enddef


    def exposfirstaddsecondButton(self):
        if self.expTimeFirst < 120:
            self.expTimeFirst = round(self.expTimeFirst + 1, 1)
        else:
            self.display.hw.beepAlarm(1)
        #endif
        self.showItems(timeexposfirst=self.expTimeFirst)
    #enddef


    def exposfirstsubsecondButton(self):
        if self.expTimeFirst > 10:
            self.expTimeFirst = round(self.expTimeFirst - 1, 1)
        else:
            self.display.hw.beepAlarm(1)
        #endif
        self.showItems(timeexposfirst=self.expTimeFirst)
    #enddef


    def exposcalibrateaddsecondButton(self):
        if self.expTimeCalibrate < 5:
            self.expTimeCalibrate = round(self.expTimeCalibrate + 0.5, 1)
        else:
            self.display.hw.beepAlarm(1)
        #endif
        self.showItems(timeexposcalibrate=self.expTimeCalibrate)
    #enddef


    def exposcalibratesubsecondButton(self):
        if self.expTimeCalibrate > 0.5:
            self.expTimeCalibrate = round(self.expTimeCalibrate - 0.5, 1)
        else:
            self.display.hw.beepAlarm(1)
        #endif
        self.showItems(timeexposcalibrate=self.expTimeCalibrate)
    #enddef

#endclass


class PageSysInfo(Page):

    def __init__(self, display):
        self.pageUI = "sysinfo"
        self.pageTitle = "System Information"
        super(PageSysInfo, self).__init__(display)
        self.items.update({
                'line1' : "A64 serial number: %s" % self.display.hw.getCPUSerial(),
                'line2' : "A64 system: %s" % self.display.hwConfig.os.name,
                'line3' : "A64 system version: %s" % self.display.hwConfig.os.version,

                'line6' : "Python firmware version: %s" % defines.swVersion,
                'line7' : "", # will be filled from getEvent()
                'line8' : "API Key: %s" % self.octoprintAuth,
                'serial_number': self.display.hw.getCPUSerial(),
                'system_name': self.display.hwConfig.os.name,
                'system_version': self.display.hwConfig.os.version,
                'firmware_version': defines.swVersion,
                'api_key': self.octoprintAuth
                })
    #enddef


    def show(self):
        self.items['line4'] = "MC serial number: %s" % self.display.hw.getControllerSerial()
        self.items['line5'] = "MC version: %s" % self.display.hw.getControllerVersion()
        self.items['controller_version'] = self.display.hw.getControllerVersion()
        self.items['controller_serial'] = self.display.hw.getControllerSerial()
        super(PageSysInfo, self).show()
    #enddef

#endclass


class PageHardwareInfo(Page):

    def __init__(self, display):
        self.pageUI = "sysinfo"
        self.pageTitle = "Hardware Information"
        super(PageHardwareInfo, self).__init__(display)
        self.callbackPeriod = 0.5
    #enddef


    def show(self):
        self.oldValues = {}
        self.items['line1'] = "Tower height: %d (%.2f mm)" % (self.display.hwConfig.towerHeight, self.display.hwConfig.calcMM(self.display.hwConfig.towerHeight))
        self.items['line2'] = "Tilt height: %d" % self.display.hwConfig.tiltHeight
        self.display.hw.resinSensor(True)
        self.skip = 11
        self.items['tower_height'] = self.display.hwConfig.towerHeight
        self.items['tower_height_mm'] = self.display.hwConfig.calcMM(self.display.hwConfig.towerHeight)
        super(PageHardwareInfo, self).show()
    #enddef


    def menuCallback(self):
        items = {}
        if self.skip > 10:
            self._setItem(items, 'line3', "Fans [RPM]:  %s" % "  ".join(map(lambda x: str(x), self.display.hw.getFansRpm())))
            self._setItem(items, 'line4', "MC temperatures [C]:  %s" % "  ".join(map(lambda x: str(x), self.display.hw.getMcTemperatures())))
            self._setItem(items, 'line5', "A64 temperature [C]:  %.1f" % self.display.hw.getCpuTemperature())
            self._setItem(items, 'line6', "Voltages [V]:  %s" % "  ".join(map(lambda x: str(x), self.display.hw.getVoltages())))
            self._setItem(items, 'fans', {'fan%d_rpm' % i: v for i, v in enumerate(self.display.hw.getFansRpm())})
            self._setItem(items, 'temps', {'temp%d_celsius' % i: v for i, v in enumerate(self.display.hw.getMcTemperatures())})
            self._setItem(items, 'cpu_temp', self.display.hw.getCpuTemperature())
            self._setItem(items, 'leds', {'led%d_voltage_volt' % i: v for i, v in enumerate(self.display.hw.getVoltages())})
            self.skip = 0
        #endif
        self._setItem(items, 'line7', "Cover is %s" % ("closed" if self.display.hw.getCoverState() else "opened"))
        self._setItem(items, 'line8', "Power switch is %s" % ("pressed" if self.display.hw.getPowerswitchState() else "released"))
        self._setItem(items, 'line9', "Resin surface is %sin detect range" % ("" if self.display.hw.getResinSensorState() else "not "))
        self._setItem(items, 'resin_sensor_state', self.display.hw.getResinSensorState())
        self._setItem(items, 'cover_state', self.display.hw.getCoverState())
        self._setItem(items, 'power_switch_state', self.display.hw.getPowerswitchState())

        if len(items):
            self.showItems(**items)
        #endif

        self.skip += 1
    #enddef


    def backButtonRelease(self):
        self.display.hw.resinSensor(False)
        return super(PageHardwareInfo, self).backButtonRelease()
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
                    items['mode'] = 'ap'
                    items['ap_ssid'] = wifiData['ssid']
                    items['ap_psk'] = wifiData['psk']
                    items["line2"] = "Setup URL: %s%s" % (ip, defines.wifiSetupURI)
                    items['ap_setup_url'] = "%s%s" % (ip, defines.wifiSetupURI)
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
                items['mode'] = "client"
                items['client_ip'] = ip
                items['client_hostname'] = self.display.inet.getHostname()
                items["qr1label"] = "Logfile"
                items["qr1"] = "http://%s/log" % ip
                items["qr2label"] = "MC debug"
                items["qr2"] = "http://%s/debug" % ip
            #endif
        else:
            # no internet connection
            items['mode'] = None
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
                "line1" : "2018-2019 Prusa Research s.r.o.",
                "line2" : defines.aboutURL,
#                "qr1" : "https://www.prusa3d.com",
                "qr1" : "MECARD:N:Prusa Research s.r.o.;URL:www.prusa3d.com;EMAIL:info@prusa3d.com;;",
                "about_url": defines.aboutURL
                })
    #enddef


    def showadminButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.showadminContinue,
                line1 = "Do you really want to enable admin menu?",
                line2 = "Wrong settings may damage your printer!")
        return "confirm"
    #enddef


    def showadminContinue(self):
        self.display.hwConfig.update(showadmin = "yes")
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        return "_BACK_"
    #enddef 

#endclass


class SourceDir:

    class NotProject(Exception):
        pass
    #endclass

    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.logger = logging.getLogger(__name__)
    #enddef


    def list(self, current_root):
        path = os.path.join(self.root, current_root)

        if not os.path.isdir(path):
            return
        #endif

        for item in os.listdir(path):
            try:
                yield self.processItem(item, path)
            except SourceDir.NotProject:
                continue
            except Exception as e:
                self.logger.debug("Ignoring source project: %s" % str(e))
                continue
            #endtry
        #endfor
    #enddef


    def processItem(self, item, path):
        # Skip . link
        if item.startswith('.'):
            raise SourceDir.NotProject(". dir")
        # endif

        # Skip files that fail to decode as utf-8
        try:
            item.decode('utf-8')
        except Exception as e:
            raise Exception('Invalid filename')

        # Add directory to result
        full_path = os.path.join(path, item)
        if os.path.isdir(full_path):
            return {
                'type': 'dir',
                'name': item,
                'path': item,
                'fullpath': full_path,
                'numitems': len(os.listdir(full_path))
            }
        #endif

        # Add project as result
        (name, extension) = os.path.splitext(item)
        if extension in defines.projectExtensions:
            return {
                'type': 'project',
                'name': name,
                'fullpath': full_path,
                'source': self.name,
                'filename': item,
                'path': item,
                'time': os.path.getmtime(full_path)
            }
        #endif

        raise SourceDir.NotProject("Invalid extension: %s" % name)
    #enddef

#endclass


class PageSrcSelect(Page):

    def __init__(self, display):
        self.pageUI = "sourceselect"
        self.pageTitle = "Projects"
        self.currentRoot = "."
        self.old_items = None
        super(PageSrcSelect, self).__init__(display)
        self.stack = False
        self.callbackPeriod = 1
    #enddef


    def in_root(self):
        return self.currentRoot is "."
    #enddef


    def source_list(self):
        # Get source directories
        sourceDirs = \
            [SourceDir(defines.ramdiskPath, "ramdisk")] + \
            [SourceDir(path, "usb") for path in glob.glob(os.path.join(defines.mediaRootPath, "*"))] + \
            [SourceDir(defines.internalProjectPath, "internal")]

        # Get content items
        dirs = {}
        files = []
        for source_dir in sourceDirs:
            for item in source_dir.list(self.currentRoot):
                if item['type'] is 'dir':
                    if item['name'] in dirs:
                        item['numitems'] += dirs[item['name']]['numitems']
                    dirs[item['name']] = item
                else:
                    files.append(item)
                #endif
        #endfor

        # Flatten dirs, sort by name
        dirs = sorted(dirs.values(), key=lambda x: x['name'])

        # Add <up> virtual directory
        if not self.in_root():
            dirs.insert(0, {
                'type': 'dir',
                'name': '<up>',
                'path': '..'
            })
        #endif

        # Sort files
        files.sort(key=lambda x: x['time'])
        files.reverse()

        # Compose content
        content = dirs
        content += files

        # Number items as choice#
        for i, item in enumerate(content):
            item['choice'] = "choice%d" % i
        #endfor

        return content
    #enddef

    def fillData(self):
        line1 = "Please select project source"

        ip = self.display.inet.getIp()
        if ip != "none" and self.octoprintAuth:
            line2 = "%s%s (%s)" % (ip, defines.octoprintURI, self.octoprintAuth)
        else:
            line2 = "Not connected to network"
        # endif

        return {
            'line1': line1,
            'line2': line2,
            'sources': self.source_list()
        }

    def show(self):
        self.items = self.fillData()
        super(PageSrcSelect, self).show()
    #enddef


    def menuCallback(self):
        items = self.fillData()
        if self.old_items != items:
            self.showItems(**items)
            self.old_items = items
    # enddef


    def sourceButtonSubmit(self, data):
        for item in self.items['sources']:
            if item['choice'] == data['choice']:
                if item['type'] == 'dir':
                    self.currentRoot = os.path.join(self.currentRoot, item['path'])
                    self.currentRoot = os.path.normpath(self.currentRoot)
                    self.logger.info("Current project selection root: %s" % self.currentRoot)
                    return "sourceselect"
                else:
                    return self.loadProject(item['fullpath'])
                #enddef
            #endif
        #endfor
    #enddef


    def netChange(self):
        ip = self.display.inet.getIp()
        if ip != "none" and self.octoprintAuth:
            self.showItems(line2, "%s%s (%s)" % (ip, defines.octoprintURI, self.octoprintAuth))
        else:
            self.showItems(line2, "Not connected to network")
        #endif
    #enddef


    def loadProject(self, project_path):
        pageWait = PageWait(self.display, line2="Reading project data...")
        pageWait.show()
        self.checkConfFile(project_path)
        config = self.display.config

        if not config.configFound:
            sleep(0.5)
            self.display.page_error.setParams(
                line1="Your project has a problem:",
                line2="%s project not found" % project_path,
                line3="Regenerate it and try again.")
            return "error"
        elif config.action != "print":
            sleep(0.5)
            self.display.page_error.setParams(
                line1="Your project has a problem:",
                line2="Invalid project file",
                line3="Regenerate it and try again.")
            return "error"
        elif config.zipError is not None:
            sleep(0.5)
            self.display.page_error.setParams(
                    line1 = "Your project has a problem:",
                    line2 = config.zipError,
                    line3 = "Regenerate it and try again.")
            return "error"
        #endif

        return "printpreview"
    #endef


    def backButtonRelease(self):
        self.currentRoot = "."
        return super(PageSrcSelect, self).backButtonRelease()
    #enddef

#endclass

# TODO: remove me
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
        self.stack = False
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
                'button5' : "Tilt profil calib.",

                'button6' : "Tower home",
                'button7' : "Tower move",
                'button8' : "Tower test",
                'button9' : "Tower profiles",
                'button10' : "Tower home calib.",

                'button11' : "Turn motors off",
                'button12' : "Tune tilt",
                'button13' : "Tilt home test",
                'button14' : "",
                'button15' : "",
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
        self.display.hw.tiltLayerUpWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line2 = "Tilt down")
        self.display.hw.tiltLayerDownWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line2 = "Tilt up")
        self.display.hw.tiltLayerUpWait()
        self.display.hw.beepEcho()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button4ButtonRelease(self):
        return "tiltprofiles"
    #enddef


    def button5ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.button5Continue,
                line1 = "Printer will search for tilt homing profiles.",
                line2 = "Please remove the tank from tilt.")
        return "confirm"
    #enddef


    def button5Continue(self):
        timeout = 60
        self.display.hw.mcc.do("!ena", 3)
        self.display.hw.setTiltProfile('layerRelease')
        pageWait = PageWait(self.display,
            line1 = "Printer warming up",
            line2 = "Time remaining %d s" % timeout,
            line3 = "Please wait...")
        pageWait.show()
        while timeout:
            sleep(1)
            timeout -= 1
            pageWait.showItems(line2 = "Time remaining %d s" % timeout)
        #endwhile
        timeout = 10
        self.display.hw.motorsRelease()
        pageWait = PageWait(self.display,
            line1 = "Printer cooling down",
            line2 = "Time remaining %d s" % timeout,
            line3 = "Please wait...")
        pageWait.show()
        while timeout:
            sleep(1)
            timeout -= 1
            pageWait.showItems(line2 = "Time remaining %d s" % timeout)
        #endwhile
        pageWait = PageWait(self.display,
            line1 = "Searching for homingFast profile",
            line2 = "Please wait...",
            line3 = "")
        pageWait.show()
        profileFast = self.display.hw.findTiltProfile(self.display.hw._tiltProfiles["homingFast"], True, 2000, 70, 10, 32, 3, 12)
        pageWait = PageWait(self.display,
            line1 = "Searching for homingSlow profile",
            line2 = "Please wait...",
            line3 = "")
        pageWait.show()
        profileSlow = self.display.hw.findTiltProfile(self.display.hw._tiltProfiles["homingSlow"], False, 1200, 30, 10, 27, 3, 12)
        if (profileSlow == None) or (profileFast == None):
            resultMsg = "not found. Please adjust them manually."
        else:
            resultMsg = "found."
        #endif
        self.display.page_confirm.setParams(
                continueFce = self.button5Continue2,
                line1 = "Tilt profiles %s" % resultMsg)
        return "confirm"
    #enddef


    def button5Continue2(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Tilt home calibration")
        pageWait.show()
        self.display.hw.tiltHomeCalibrateWait()
        self.display.hw.motorsRelease()
        self.display.hw.powerLed("normal")
        return "_BACK_"
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
        self.display.hw.towerToZero()
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


    def button10ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Tower home calibration")
        pageWait.show()
        self.display.hw.towerHomeCalibrateWait()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button11ButtonRelease(self):
        self.display.hw.motorsRelease()
    #enddef


    def button12ButtonRelease(self):
        return "tunetilt"
    #enddef


    def button13ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Tilt home test")
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif
        for i in xrange(50):
            self.display.hw.tiltSyncWait()
            self.display.hw.tiltMoveAbsolute(3000)
            #self.display.hw.tiltUp()
            while self.display.hw.isTiltMoving():
                sleep(0.1)
            #endwhile
            sleep(2)
        #endfor
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button14ButtonRelease(self):
        pass
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
                'button7' : "",
                'button8' : "",
                'button9' : "",
                'button10' : "Infinite test",

                'button11' : "Black",
                'button12' : "Inverse",
                'button13' : "",
                'button14' : "",
                'button15' : "",
                })
    #enddef


    def show(self):
        self.display.screen.getImgBlack()
        self.display.screen.inverse()
        self.display.hw.uvLed(True)
        self.items['button14'] = "UV off"
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
            self.display.screen.getImg(filename = os.path.join(self.getSavePath(), "test.png"))
        except Exception:
            self.logger.exception("export exception:")
            self.display.hw.beepAlarm(3)
        #endtry
    #enddef


    def button10ButtonRelease(self):
        towerCounter = 0
        tiltCounter = 0
        towerStatus = 0
        tiltMayMove = True
        #up = 0
        #above Display = 1
        #down = 3

        self.display.hw.powerLed("warn")
        pageWait = PageWait(
            self.display,
            line1 = "Infinite test...",
            line2 = "Tower cycles: %d" % towerCounter,
            line3 = "Tilt cycles: %d" % tiltCounter)
        pageWait.show()
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice16_1440x2560.png"))
        self.display.hw.uvLed(True)
        self.display.hw.towerSync()
        while True:
            if not self.display.hw.isTowerMoving():
                if towerStatus == 0:    #tower moved to top
                    towerCounter += 1
                    pageWait.showItems(line2 = "Tower cycles: %d" % towerCounter)
                    self.logger.debug("towerCounter: %d, tiltCounter: %d", towerCounter, tiltCounter)
                    self.display.hw.setTowerPosition(0)
                    self.display.hw.setTowerProfile('homingFast')
                    self.display.hw.towerMoveAbsolute(self.display.hw._towerAboveSurface)
                    towerStatus = 1
                elif towerStatus == 1:  #tower above the display
                    tiltMayMove = False
                    if self.display.hw.isTiltUp():
                        towerStatus = 2
                        self.display.hw.setTiltProfile('layerMoveSlow')
                        self.display.hw.setTowerProfile('homingSlow')
                        self.display.hw.towerToMin()
                    #endif
                elif towerStatus == 2:
                    tiltMayMove = True
                    self.display.hw.towerSync()
                    towerStatus = 0
                #endif
            #endif
            
            if not self.display.hw.isTiltMoving():
                if self.display.hw.getTiltPositionMicroSteps() == 0:
                    tiltCounter += 1
                    pageWait.showItems(line3 = "Tilt cycles: %d" % tiltCounter)
                    self.display.hw.setTiltProfile('moveFast')
                    self.display.hw.tiltUp()
                else:
                    if tiltMayMove:
                        self.display.hw.tiltSyncWait()
                    #endif
                #endif
            #endif
            sleep(0.25)
        #endwhile
    #enddef


    def button11ButtonRelease(self):
        self.display.screen.getImgBlack()
    #enddef


    def button12ButtonRelease(self):
        self.display.screen.inverse()
    #enddef


    def button14ButtonRelease(self):
        state = not self.display.hw.getUvLedState()[0]
        self.showItems(button14 = "UV off" if state else "UV on")
        self.display.hw.uvLed(state)
    #enddef


    def backButtonRelease(self):
        self.display.hw.uvLed(False)
        self.display.screen.getImgBlack()
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
                'button4' : "Hardware setup",
                'button5' : "Exposure setup",

                'button6' : "Flash MC",
                'button7' : "Erase MC EEPROM",
                'button8' : "",
                'button9' : "Hardware info",
                'button10' : "Networking",

                'button11' : "Net update",
                'button12' : "",
                'button13' : "Resin sensor test",
                'button14' : "Download examples",
                'button15' : "Factory reset",
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
        return "setuphw"
    #enddef


    def button5ButtonRelease(self):
        return "setupexpo"
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
        self.display.hw.flashMC(self.display.page_systemwait, self.display.actualPage)
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


    def button9ButtonRelease(self):
        return "hwinfo"
    #enddef


    def button10ButtonRelease(self):
        return "networking"
    #enddef


    def button11ButtonRelease(self):
        return "netupdate"
    #enddef


    def button12ButtonRelease(self):
        pass
    #enddef


    def button13ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Moving platform to top")
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line2 = "Tilt home", line3 = "")
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.setTiltProfile('layerMoveSlow')
        self.display.hw.tiltUpWait()
        self.display.hw.powerLed("normal")

        self.display.page_confirm.setParams(
                continueFce = self.button13Continue,
                line1 = "Is tank filled and secured",
                line2 = "with both screws?")
        return "confirm"
    #enddef


    def button13Continue(self):
        # TODO vyzadovat zavreny kryt po celou dobu!
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = "Measuring", line3 = "Do NOT TOUCH the printer")
        pageWait.show()
        volume = self.display.hw.getResinVolume()
        self.display.hw.powerLed("normal")
        if not volume:
            self.display.page_error.setParams(
                    line1 = "Resin measure failed!",
                    line2 = "Is tank filled and secured",
                    line3 = "with both screws?")
            return "error"
        #endif

        self.display.page_confirm.setParams(
                continueFce = self.backButtonRelease,
                line1 = "Measured resin volume: %d ml" % volume)
        return "confirm"
    #enddef


    def button14ButtonRelease(self):
        try:
            if not os.path.isdir(defines.internalProjectPath):
                os.makedirs(defines.internalProjectPath)

            self.downloadURL(defines.examplesURL, defines.examplesArchivePath, title="Fetching examples")

            pageWait = PageWait(self.display, line1="Decompressing examples")
            pageWait.show()
            pageWait.showItems(line1="Extracting examples")
            with tarfile.open(defines.examplesArchivePath) as tar:
                tar.extractall(path=defines.internalProjectPath)
            pageWait.showItems(line1="Cleaning up")
            os.remove(defines.examplesArchivePath)

            return "_BACK_"

        except Exception as e:
            self.logger.error("Exaples fetch failed: " + str(e))
            self.display.page_error.setParams(
                line2="Examples fetch failed")
            return "error"
    #enddef


    def downloadURL(self, url, dest, title='Fetching'):
        pageWait = PageWait(self.display, line1=title, line2="0%")
        pageWait.show()

        self.logger.info("Downloading %s" % url)

        req = urllib2.Request(url)
        req.add_header('User-Agent', 'Prusa-SL1')
        source = urllib2.urlopen(req, timeout=10)
        file_size = int(source.info().getheaders("Content-Length")[0])
        block_size = 8 * 1024

        with open(dest, 'wb') as file:
            old_progress = 0
            while True:
                buffer = source.read(block_size)
                if not buffer:
                    break
                # endif
                file.write(buffer)

                progress = int(100 * file.tell() / file_size)
                if progress != old_progress:
                    pageWait.showItems(line2="%d%%" % progress)
                    old_progress = progress
                # endif
            # endwhile
        # endwith
    #enddef


    def button15ButtonRelease(self):
        pageWait = PageWait(self.display, line1 = "Please wait...")
        pageWait.show()
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait(3)
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        
        #move tilt and tower to packing position
        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.tiltMoveAbsolute(defines.defaultTiltHeight)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.setTowerProfile('moveFast')
        self.display.hw.towerMoveAbsolute(self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(74))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        #at this height may be screwed down tank and inserted protective foam
        self.display.page_confirm.setParams(
            continueFce = self.button15Continue,
            line1 = "Do you really want to do factory reset?",
            line2 = "All settings will be deleted!")
        return "confirm"
    #enddef


    def button15Continue(self):
        #slightly press the foam against printers base
        self.display.hw.towerMoveAbsolute(self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(93))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hwConfig.update(
            towerheight = self.display.hwConfig.calcMicroSteps(defines.defaultTowerHeight),
            tiltheight = defines.defaultTiltHeight,
            calibrated = "no",
            showadmin = "no"
            #TODO force wizard
        )
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        self.display.shutDown(True)
    #enddef

#endclass


class PageNetUpdate(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = "Admin - Net update"
        super(PageNetUpdate, self).__init__(display)

        self.firmwares = list(enumerate(defines.netFirmwares))

        # Create items for updating firmwares
        self.items.update({
            "button%s" % (i + 1): "Update to %s" % firmware['name'] for (i, firmware) in self.firmwares
        })

        # Create action handlers
        for (i, firmware) in self.firmwares:
            self.makeUpdateButton(i + 1, firmware['name'], firmware['url'])
        #endfor
    #enddef


    def makeUpdateButton(self, i, name, url):
        setattr(self.__class__, 'button%dButtonRelease' % i, lambda x: x.update(name, url))
    #enddef


    def update(self, name, url):
        self.display.page_confirm.setParams(
            continueFce=self.display.page_firmwareupdate.fetchUpdate,
            continueParmas={'fw_url': url},
            line1="Updating to %s" % name,
            line3="Proceed update?")
        return "confirm"
    #enddef

#endclass


class PageSetup(Page):

    def __init__(self, display):
        self.pageUI = "setup"
        super(PageSetup, self).__init__(display)
        self.autorepeat = {
                'minus2g1' : (5, 1), 'plus2g1' : (5, 1),
                'minus2g2' : (5, 1), 'plus2g2' : (5, 1),
                'minus2g3' : (5, 1), 'plus2g3' : (5, 1),
                'minus2g4' : (5, 1), 'plus2g4' : (5, 1),
                'minus2g5' : (5, 1), 'plus2g5' : (5, 1),
                'minus2g6' : (5, 1), 'plus2g6' : (5, 1),
                'minus2g7' : (5, 1), 'plus2g7' : (5, 1),
                'minus2g8' : (5, 1), 'plus2g8' : (5, 1),
                }
        self.items.update({
                'button1' : "Export",
                'button2' : "Import",
                'button4' : "Save",
                'back' : "Back",
                })
        self.changed = {}
        self.temp = {}
    #enddef


    def button1ButtonRelease(self):
        ''' export '''
        if not self.display.hwConfig.writeFile(os.path.join(self.getSavePath(), defines.hwConfigFileName)):
            self.display.hw.beepAlarm(3)
        #endif
    #enddef


    def button2ButtonRelease(self):
        ''' import '''
        try:
            with open(os.path.join(self.getSavePath(), defines.hwConfigFileName), "r") as f:
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
        self.display.config._parseData()    # <- WHY? FIXME
        return super(PageSetup, self).backButtonRelease()
    #endif
#enddef


class PageSetupHw(PageSetup):

    def __init__(self, display):
        self.pageTitle = "Admin - Hardware Setup"
        super(PageSetupHw, self).__init__(display)
        self.items.update({
                'label1g1' : "Fan check",
                'label1g2' : "Cover check",
                'label1g3' : "MC version check",
                'label1g4' : "Use resin sensor",

                'label2g1' : "Screw (mm/rot)",
                'label2g2' : "Tilt msteps",
                'label2g3' : "Calib. tower offset [mm]",
                'label2g8' : "MC board version",
                })
    #enddef


    def show(self):
        self.temp['screwmm'] = self.display.hwConfig.screwMm
        self.temp['tiltheight'] = self.display.hwConfig.tiltHeight
        self.temp['calibtoweroffset'] = self.display.hwConfig.calibTowerOffset
        self.temp['mcboardversion'] = self.display.hwConfig.MCBoardVersion

        self.items['value2g1'] = str(self.temp['screwmm'])
        self.items['value2g2'] = str(self.temp['tiltheight'])
        self.items['value2g3'] = self.strOffset(self.temp['calibtoweroffset'])
        self.items['value2g8'] = str(self.temp['mcboardversion'])

        self.temp['fancheck'] = self.display.hwConfig.fanCheck
        self.temp['covercheck'] = self.display.hwConfig.coverCheck
        self.temp['mcversioncheck'] = self.display.hwConfig.MCversionCheck
        self.temp['resinsensor'] = self.display.hwConfig.resinSensor

        self.items['state1g1'] = 1 if self.temp['fancheck'] else 0
        self.items['state1g2'] = 1 if self.temp['covercheck'] else 0
        self.items['state1g3'] = 1 if self.temp['mcversioncheck'] else 0
        self.items['state1g4'] = 1 if self.temp['resinsensor'] else 0

        super(PageSetupHw, self).show()
    #enddef


    def state1g1ButtonRelease(self):
        self._onOff(0, 'fancheck')
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(1, 'covercheck')
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(2, 'mcversioncheck')
    #enddef


    def state1g4ButtonRelease(self):
        self._onOff(3, 'resinsensor')
    #enddef


    def minus2g1Button(self):
        self._value(0, 'screwmm', 2, 8, -1)
    #enddef


    def plus2g1Button(self):
        self._value(0, 'screwmm', 2, 8, 1)
    #enddef


    def minus2g2Button(self):
        self._value(1, 'tiltheight', 1, 6000, -1)
    #enddef


    def plus2g2Button(self):
        self._value(1, 'tiltheight', 1, 6000, 1)
    #enddef


    def strOffset(self, value):
        return "%+.3f" % self.display.hwConfig.calcMM(value)
    #enddef


    def minus2g3Button(self):
        self._value(2, 'calibtoweroffset', -400, 400, -1, self.strOffset)
    #enddef


    def plus2g3Button(self):
        self._value(2, 'calibtoweroffset', -400, 400, 1, self.strOffset)
    #enddef


    def minus2g8Button(self):
        self._value(7, 'mcboardversion', 4, 5, -1)
    #enddef


    def plus2g8Button(self):
        self._value(7, 'mcboardversion', 4, 5, 1)
    #enddef

#endclass


class PageSetupExposure(PageSetup):

    def __init__(self, display):
        self.pageTitle = "Admin - Exposure Setup"
        super(PageSetupExposure, self).__init__(display)
        self.items.update({
                'label1g1' : "Blink exposure",
                'label1g2' : "Per-Partes expos.",
                'label1g3' : "Use tilt",

                'label2g1' : "Warm up mins",
                'label2g2' : "Layer trigger [s]",
                'label2g3' : "Limit for fast tilt [%]",
                'label2g4' : "Layer tower hop [mm]",
                'label2g5' : "Delay before expos. [s]",
                'label2g6' : "Delay after expos. [s]",
                'label2g7' : "Up&down wait [s]",
                'label2g8' : "Up&down every n-th l.",
                })
    #enddef


    def show(self):
        self.temp['warmup'] = self.display.hwConfig.warmUp
        self.temp['trigger'] = self.display.hwConfig.trigger
        self.temp['limit4fast'] = self.display.hwConfig.limit4fast
        self.temp['layertowerhop'] = self.display.hwConfig.layerTowerHop
        self.temp['delaybeforeexposure'] = self.display.hwConfig.delayBeforeExposure
        self.temp['delayafterexposure'] = self.display.hwConfig.delayAfterExposure
        self.temp['upanddownwait'] = self.display.hwConfig.upAndDownWait
        self.temp['upanddowneverylayer'] = self.display.hwConfig.upAndDownEveryLayer

        self.items['value2g1'] = str(self.temp['warmup'])
        self.items['value2g2'] = self.strTenth(self.temp['trigger'])
        self.items['value2g3'] = str(self.temp['limit4fast'])
        self.items['value2g4'] = self.strZHop(self.temp['layertowerhop'])
        self.items['value2g5'] = self.strTenth(self.temp['delaybeforeexposure'])
        self.items['value2g6'] = self.strTenth(self.temp['delayafterexposure'])
        self.items['value2g7'] = str(self.temp['upanddownwait'])
        self.items['value2g8'] = str(self.temp['upanddowneverylayer'])

        self.temp['blinkexposure'] = self.display.hwConfig.blinkExposure
        self.temp['perpartesexposure'] = self.display.hwConfig.perPartes
        self.temp['tilt'] = self.display.hwConfig.tilt

        self.items['state1g1'] = 1 if self.temp['blinkexposure'] else 0
        self.items['state1g2'] = 1 if self.temp['perpartesexposure'] else 0
        self.items['state1g3'] = 1 if self.temp['tilt'] else 0

        super(PageSetupExposure, self).show()
    #enddef


    def state1g1ButtonRelease(self):
        self._onOff(0, 'blinkexposure')
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(1, 'perpartesexposure')
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(2, 'tilt')
        if not self.temp['tilt'] and not self.temp['layertowerhop']:
            self.temp['layertowerhop'] = self.display.hwConfig.calcMicroSteps(5)
            self.changed['layertowerhop'] = str(self.temp['layertowerhop'])
            self.showItems(**{ 'value2g4' : self.strZHop(self.temp['layertowerhop']) })
        #endif
    #enddef


    def minus2g1Button(self):
        self._value(0, 'warmup', 0, 30, -1)
    #enddef


    def plus2g1Button(self):
        self._value(0, 'warmup', 0, 30, 1)
    #enddef


    def strTenth(self, value):
        return "%.1f" % (value / 10.0)
    #enddef


    def minus2g2Button(self):
        self._value(1, 'trigger', 0, 20, -1, self.strTenth)
    #enddef


    def plus2g2Button(self):
        self._value(1, 'trigger', 0, 20, 1, self.strTenth)
    #enddef


    def minus2g3Button(self):
        self._value(2, 'limit4fast', 0, 100, -1)
    #enddef


    def plus2g3Button(self):
        self._value(2, 'limit4fast', 0, 100, 1)
    #enddef


    def strZHop(self, value):
        return "%.3f" % self.display.hwConfig.calcMM(value)
    #enddef


    def minus2g4Button(self):
        self._value(3, 'layertowerhop', 0, 8000, -20, self.strZHop)
        if not self.temp['tilt'] and not self.temp['layertowerhop']:
            self.temp['tilt'] = True
            self.changed['tilt'] = "on"
            self.showItems(**{ 'state1g3' : 1 })
        #endif
    #enddef


    def plus2g4Button(self):
        self._value(3, 'layertowerhop', 0, 8000, 20, self.strZHop)
    #enddef


    def minus2g5Button(self):
        self._value(4, 'delaybeforeexposure', 0, 300, -1, self.strTenth)
    #enddef


    def plus2g5Button(self):
        self._value(4, 'delaybeforeexposure', 0, 300, 1, self.strTenth)
    #enddef


    def minus2g6Button(self):
        self._value(5, 'delayafterexposure', 0, 300, -1, self.strTenth)
    #enddef


    def plus2g6Button(self):
        self._value(5, 'delayafterexposure', 0, 300, 1, self.strTenth)
    #enddef


    def minus2g7Button(self):
        self._value(6, 'upanddownwait', 0, 600, -1)
    #enddef


    def plus2g7Button(self):
        self._value(6, 'upanddownwait', 0, 600, 1)
    #enddef


    def minus2g8Button(self):
        self._value(7, 'upanddowneverylayer', 0, 500, -1)
    #enddef


    def plus2g8Button(self):
        self._value(7, 'upanddowneverylayer', 0, 500, 1)
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
        self.pageUI = "towermovecalibration"
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
        self.display.hw.setTiltProfile('layerMoveSlow')
        self.display.hw.tiltUpWait()
        pageWait.showItems(line2 = "Moving platform down")
        self.display.hw.setTowerProfile('moveFast')
        self.display.hw.towerMoveAbsolute(self.display.hw._towerCalibPos) # move quickly to safe distance
        while not self.display.hw.isTowerOnPosition():
            sleep(0.25)
            pageWait.showItems(line3 = self.display.hw.getTowerPosition())
        #endwhile
        self.items["value"] = self.display.hw.getTowerPosition()
        self.display.hw.powerLed("normal")
        self.moving = False
    #enddef


    def okButtonRelease(self):
        position = self.display.hw.getTowerPositionMicroSteps()
        if position is None:
            self.logger.error("Invalid tower position to save!")
            self.display.hw.beepAlarm(3)
        else:
            towerHeight = self.display.hw._towerEnd - self.display.hw.getTowerPositionMicroSteps()
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


class PageCalibration(Page):
    def __init__(self, display):
        self.pageUI = "home"
        self.pageTitle = "Calibration"
        super(PageCalibration, self).__init__(display)
        self.stack = False
    #enddef


    def prepare(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = "Printer homing",
            line2 = "Please wait...")
        pageWait.show()
        
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait(2)
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        self.display.hw.powerLed("normal")

        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep2,
            imageName = "06_tighten_knob.jpg",
            line1 = "Insert the platfom and secure it with black knob.")
        return "confirm"
    #enddef


    def recalibrateStep2(self):
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep3,
            imageName = "01_loosen_screws.jpg",
            line1 = "Loosen small screws on the console. Be careful not to unscrew them completely.")
        return "confirm"
    #enddef


    def recalibrateStep3(self):
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep4,
            imageName = "02_place_bed.jpg",
            line1 = "Unscrew the tank and turn it 90 degrees on the base so it lies across tilt.")
        return "confirm"
    #enddef


    def recalibrateStep4(self):
        self.display.hw.powerLed("warn")
        self.display.hw.tiltMoveAbsolute(self.display.hw._tiltCalibStart)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.powerLed("normal")
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep5,
            imageName = "03_proper_aligment.jpg",
            line1 = "Move tilt up until the tank gets lifted by 0.1 mm above the base.")
        return "confirm"
    #enddef


    def recalibrateStep5(self):
        return "tiltcalib"
    #endef

#endclass


class PageTiltCalib(MovePage):

    def __init__(self, display):
        self.pageUI = "tiltmovecalibration"
        self.pageTitle = "Tank Calibration"
        super(PageTiltCalib, self).__init__(display)
        self.stack = False
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
    #enddef


    def show(self):
        self.display.hw.setTiltProfile('moveSlow')
        self.items["value"] = self.display.hw.getTiltPosition()
        self.moving = False
        super(PageTiltCalib, self).show()
    #enddef


    def okButtonRelease(self):
        position = self.display.hw.getTiltPositionMicroSteps()
        if position is None:
            self.logger.error("Invalid tilt position to save!")
            self.display.hw.beepAlarm(3)
        else:
            self.display.hwConfig.tiltHeight = position
        #endif
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep2,
            imageName = "08_clean.jpg",
            line1 = "Make sure the platform, tank and tilt are perfectly clean.")
        return "confirm"
    #endif


    def _up(self, slowMoving):
        if not self.moving:
            self.display.hw.tiltMoveAbsolute(self.display.hw._tiltEnd)
            self.moving = True
        else:
            if self.display.hw.getTiltPosition() == self.display.hw._tiltEnd:
                self.display.hw.beepAlarm(1)
            #endif
        #endif
        self.showItems(value = self.display.hw.getTiltPosition())
    #enddef


    def _down(self, slowMoving):
        if not self.moving:
            self.display.hw.tiltMoveAbsolute(self.display.hw._tiltCalibStart)
            self.moving = True
        else:
            if self.display.hw.getTiltPosition() == self.display.hw._tiltCalibStart:
                self.display.hw.beepAlarm(1)
            #endif
        #endif
        self.showItems(value = self.display.hw.getTiltPosition())
    #enddef


    def _stop(self):
        self.display.hw.tiltStop()
        self.moving = False
    #enddef


    def recalibrateStep2(self):
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep3,
            imageName = "04_tighten_screws.jpg",
            line1 = "Screw down the tank. Make sure you tighten both screws evenly.")
        return "confirm"
    #enddef


    def recalibrateStep3(self):
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep4,
            imageName = "06_tighten_knob.jpg",
            line1 = "Check if the platform is properly secured with black knob.")
        return "confirm"
    #enddef


    def recalibrateStep4(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = "Platform calibration",
            line2 = "Keep it as horizontal as possible!",
            line3 = "")
        pageWait.show()
        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.setTiltCurrent(defines.tiltCalibCurrent)
        self.display.hw.setTowerPosition(0)
        self.display.hw.setTowerProfile('homingFast')
        self.display.hw.towerMoveAbsolute(self.display.hw._towerAboveSurface)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.logger.debug("tower position above: %d", self.display.hw.getTowerPositionMicroSteps())
        if self.display.hw.getTowerPositionMicroSteps() != self.display.hw._towerAboveSurface:
            self.display.hw.beepAlarm(3)
            self.display.hw.towerSync()
            while not self.display.hw.isTowerSynced():
                sleep(0.25)
            #endwhile
            self.display.page_confirm.setParams(
                continueFce = self.okButtonRelease,
                line1 = "Tower not at expected position.",
                line2 = "Is the platform and tank secured on position?",
                line3 = "Click continue and read the instructions carefully.")
            return "confirm"
        #endif
        self.display.hw.setTowerProfile('homingSlow')
        self.display.hw.towerToMin()
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.logger.debug("tower position min: %d", self.display.hw.getTowerPositionMicroSteps())
        if self.display.hw.getTowerPositionMicroSteps() <= self.display.hw._towerMin:
            self.display.hw.beepAlarm(3)
            self.display.hw.towerSync()
            while not self.display.hw.isTowerSynced():
                sleep(0.25)
            #endwhile
            self.display.page_confirm.setParams(
                continueFce = self.okButtonRelease,
                line1 = "Tower not at expected position.",
                line2 = "Is the platform and tank secured on position?",
                line3 = "Click continue and read the instructions carefully.")
            return "confirm"
        #endif
        self.display.hw.towerMoveAbsolute(self.display.hw.getTowerPositionMicroSteps() + self.display.hw._towerCalibPos * 3)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.towerToMin()
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.towerMoveAbsolute(self.display.hw.getTowerPositionMicroSteps() + self.display.hw._towerCalibPos)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.logger.debug("tower position: %d", self.display.hw.getTowerPositionMicroSteps())
        self.display.hwConfig.towerHeight = -self.display.hw.getTowerPositionMicroSteps()
        self.display.hw.setTowerProfile('homingFast')
        self.display.hw.powerLed("normal")
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep5,
            imageName = "05_align_platform.jpg",
            line1 = "Turn the platform to align it with exposition display.")
        return "confirm"
    #enddef


    def recalibrateStep5(self):
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep6,
            imageName = "07_tighten_screws.jpg",
            line1 = "Tighten small srews on the console litle by little. Be careful to tighten them evenly as much as possible.")
        return "confirm"
    #enddef


    def recalibrateStep6(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = "Please wait...",
            line2 = "",
            line3 = "")
        pageWait.show()
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait(2)
        self.display.hw.tiltMoveAbsolute(self.display.hwConfig.tiltHeight)
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        self.display.hwConfig.calibrated = True
        self.display.hwConfig.update(
            towerheight = self.display.hwConfig.towerHeight,
            tiltheight = self.display.hwConfig.tiltHeight,
            calibrated = "yes")
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.setTowerProfile('moveFast')
        self.display.hw.motorsHold()
        self.display.hw.powerLed("normal")
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep7,
            line1 = "All done,",
            line2 = "happy printing!")
        return "confirm"
    #enddef


    def recalibrateStep7(self):
        return "_BACK_"
    #enddef
#endclass

class PageTowerOffset(MovePage):

    def __init__(self, display):
        self.pageUI = "towermovecalibration"
        self.pageTitle = "Tower offset"
        super(PageTowerOffset, self).__init__(display)
        self.stack = False
        self.autorepeat = { "upslow" : (1, 1), "upslow" : (1, 1), "downslow" : (1, 1), "downslow" : (1, 1) }
    #enddef


    def show(self):
        self.display.hw.setTowerProfile('moveSlow')
        self.display.hw.setTowerPosition(0)
        self.items["value"] = self.display.hw.getTowerPosition()
        self.moving = False
        super(PageTowerOffset, self).show()
    #enddef


    def okButtonRelease(self):
        offset = int(self.display.hwConfig.calcMM(self.display.hw.getTowerPositionMicroSteps()) * 1000.0)
        self.display.hwConfig.towerHeight = -self.display.hwConfig.towerHeight - self.display.hw.getTowerPositionMicroSteps()
        self.display.hwConfig.calibrated = True
        self.display.hwConfig.update(
            calibtoweroffset = offset,
            towerheight = self.display.hwConfig.towerHeight,
            tiltheight = self.display.hwConfig.tiltHeight,
            calibrated = "yes")
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.setTowerProfile('moveFast')
        self.display.hw.motorsHold()
        self.display.hw.powerLed("normal")
        self.display.page_confirm.setParams(
            continueFce = self.towerOffsetStep1,
            line1 = "All done,",
            line2 = "happy printing!",
            line3 = "")
        return "confirm"
    #enddef


    def towerOffsetStep1(self):
        return "_BACK_"
    #enddef


    def _up(self, slowMoving):
        if not self.moving:
            self.display.hw.towerMoveAbsolute(self.display.hw._towerCalibMaxOffset)
            self.moving = True
        else:
            if self.display.hw.getTowerPositionMicroSteps() == self.display.hw._towerCalibMaxOffset:
                self.display.hw.beepAlarm(1)
            #endif
        #endif
        self.showItems(value = self.display.hw.getTowerPosition())
    #enddef


    def _down(self, slowMoving):
        if not self.moving:
            self.display.hw.towerMoveAbsolute(-self.display.hw._towerCalibMaxOffset)
            self.moving = True
        else:
            if self.display.hw.getTowerPositionMicroSteps() == -self.display.hw._towerCalibMaxOffset:
                self.display.hw.beepAlarm(1)
            #endif
        #endif
        self.showItems(value = self.display.hw.getTowerPosition())
    #enddef


    def _stop(self):
        self.display.hw.towerStop()
        self.moving = False
    #enddef

#endclass


class ProfilesPage(Page):

    def __init__(self, display, items = None):
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
        self.items.update(items if items else {
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
        self.nameIndexes = set()
        self.profileItems = 7
    #enddef


    def _value(self, index, valmin, valmax, change):
        if valmin <= self.profiles[self.actualProfile][index] + change <= valmax:
            self.profiles[self.actualProfile][index] += change
            if index in self.nameIndexes:
                self.showItems(**{ 'value2g%d' % (index + 1) : str(self.profilesNames[self.profiles[self.actualProfile][index]]) })
            else:
                self.showItems(**{ 'value2g%d' % (index + 1) : str(self.profiles[self.actualProfile][index]) })
            #endif
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

        for i in xrange(self.profileItems):
            if i in self.nameIndexes:
                data["value2g%d" % (i + 1)] = str(self.profilesNames[int(self.profiles[self.actualProfile][i])])
            else:
                data["value2g%d" % (i + 1)] = str(self.profiles[self.actualProfile][i])
            #endif
        #endfor

        self.showItems(**data)
    #enddef


    def button1ButtonRelease(self):
        ''' export '''
        try:
            with open(os.path.join(self.getSavePath(), self.profilesFilename), "w") as f:
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
            with open(os.path.join(self.getSavePath(), self.profilesFilename), "r") as f:
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
        self._value(0, 0, 20000, -10)
    #enddef


    def plus2g1Button(self):
        self._value(0, 0, 20000, 10)
    #enddef


    def minus2g2Button(self):
        self._value(1, 0, 20000, -10)
    #enddef


    def plus2g2Button(self):
        self._value(1, 0, 20000, 10)
    #enddef


    def minus2g3Button(self):
        self._value(2, 0, 600, -1)
    #enddef


    def plus2g3Button(self):
        self._value(2, 0, 600, 1)
    #enddef


    def minus2g4Button(self):
        self._value(3, 0, 600, -1)
    #enddef


    def plus2g4Button(self):
        self._value(3, 0, 600, 1)
    #enddef


    def minus2g5Button(self):
        self._value(4, 0, 63, -1)
    #enddef


    def plus2g5Button(self):
        self._value(4, 0, 63, 1)
    #enddef


    def minus2g6Button(self):
        self._value(5, -128, 127, -1)
    #enddef


    def plus2g6Button(self):
        self._value(5, -128, 127, 1)
    #enddef


    def minus2g7Button(self):
        self._value(6, 0, 4000, -10)
    #enddef


    def plus2g7Button(self):
        self._value(6, 0, 4000, 10)
    #enddef

#endclass


class PageTiltProfiles(ProfilesPage):

    def __init__(self, display):
        self.profilesFilename = "tilt_profiles.json"
        self.profilesNames = display.hw.getTiltProfilesNames()
        self.profiles = None
        self.pageTitle = "Admin - Tilt Profiles"
        super(PageTiltProfiles, self).__init__(display)
    #enddef


    def show(self):
        super(PageTiltProfiles, self).show()
        if not self.profiles:
            self.profiles = self.display.hw.getTiltProfiles()
        #endif
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
        self.profiles = None
        return super(PageTiltProfiles, self).backButtonRelease()
    #enddef


    def backButtonRelease(self):
        self.display.page_tiltmove.changeProfiles(True)
        self.profiles = None
        return super(PageTiltProfiles, self).backButtonRelease()
    #endif

#endclass


class PageTowerProfiles(ProfilesPage):

    def __init__(self, display):
        self.profilesFilename = "tower_profiles.json"
        self.profilesNames = display.hw.getTowerProfilesNames()
        self.profiles = None
        self.pageTitle = "Admin - Tower Profiles"
        super(PageTowerProfiles, self).__init__(display)
    #enddef


    def show(self):
        super(PageTowerProfiles, self).show()
        if not self.profiles:
            self.profiles = self.display.hw.getTowerProfiles()
        #endif
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
        self.profiles = None
        return super(PageTowerProfiles, self).backButtonRelease()
    #enddef


    def backButtonRelease(self):
        self.display.page_towermove.changeProfiles(True)
        self.profiles = None
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
                'minus2g8' : (5, 1), 'plus2g8' : (5, 1),
                }
        self.items.update({
                'label1g1' : "Fan 1",
                'label1g2' : "Fan 2",
                'label1g3' : "Fan 3",
                'label1g5' : "UV LED",
                'label1g7' : "Trigger",

                'label2g1' : "Fan 1 PWM",
                'label2g2' : "Fan 2 PWM",
                'label2g3' : "Fan 3 PWM",
                'label2g5' : "UV current [mA]",
                'label2g6' : "Power LED PWM",
                'label2g7' : "Power LED mode",
                'label2g8' : "Power LED speed",

                'button4' : "Save",
                'back' : "Back",
                })
        self.callbackPeriod = 0.5
        self.changed = {}
        self.temp = {}
        self.valuesToSave = list(('fan1pwm', 'fan2pwm', 'fan3pwm', 'uvcurrent', 'pwrledpwm'))
    #enddef


    def show(self):
        self.oldValues = {}
        super(PageFansLeds, self).show()
    #enddef


    def menuCallback(self):
        items = {}
        self.temp['fs1'], self.temp['fs2'], self.temp['fs3'] = self.display.hw.getFans()
        self.temp['uls'] = self.display.hw.getUvLedState()[0]
        self.temp['cls'] = self.display.hw.getCameraLedState()
        self._setItem(items, 'state1g1', self.temp['fs1'])
        self._setItem(items, 'state1g2', self.temp['fs2'])
        self._setItem(items, 'state1g3', self.temp['fs3'])
        self._setItem(items, 'state1g5', self.temp['uls'])
        self._setItem(items, 'state1g7', self.temp['cls'])

        self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'] = self.display.hw.getFansPwm()
        self.temp['uvcurrent'] = self.display.hw.getUvLedCurrent()
        self.temp['pwrledpwm'] = self.display.hw.getPowerLedPwm()
        self.temp['pwrledmd'] = self.display.hw.getPowerLedMode()
        self.temp['pwrledspd'] = self.display.hw.getPowerLedSpeed()
        self._setItem(items, 'value2g1', self.temp['fan1pwm'])
        self._setItem(items, 'value2g2', self.temp['fan2pwm'])
        self._setItem(items, 'value2g3', self.temp['fan3pwm'])
        self._setItem(items, 'value2g5', self.temp['uvcurrent'])
        self._setItem(items, 'value2g6', self.temp['pwrledpwm'])
        self._setItem(items, 'value2g7', self.temp['pwrledmd'])
        self._setItem(items, 'value2g8', self.temp['pwrledspd'])

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
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(1, 'fs2')
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(2, 'fs3')
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g5ButtonRelease(self):
        self._onOff(4, 'uls')
        self.display.hw.uvLed(self.temp['uls'])
    #enddef


    def state1g7ButtonRelease(self):
        self._onOff(6, 'cls')
        self.display.hw.cameraLed(self.temp['cls'])
    #enddef


    def minus2g1Button(self):
        self._value(0, 'fan1pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def plus2g1Button(self):
        self._value(0, 'fan1pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def minus2g2Button(self):
        self._value(1, 'fan2pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def plus2g2Button(self):
        self._value(1, 'fan2pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def minus2g3Button(self):
        self._value(2, 'fan3pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def plus2g3Button(self):
        self._value(2, 'fan3pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def minus2g5Button(self):
        self._value(4, 'uvcurrent', 0, 800.1, -3.2)
        self.display.hw.setUvLedCurrent(self.temp['uvcurrent'])
    #enddef


    def plus2g5Button(self):
        self._value(4, 'uvcurrent', 0, 800.1, 3.2)
        self.display.hw.setUvLedCurrent(self.temp['uvcurrent'])
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
        self._value(6, 'pwrledmd', 0, 3, -1)
        self.display.hw.powerLedMode(self.temp['pwrledmd'])
    #enddef


    def plus2g7Button(self):
        self._value(6, 'pwrledmd', 0, 3, 1)
        self.display.hw.powerLedMode(self.temp['pwrledmd'])
    #enddef


    def minus2g8Button(self):
        self._value(7, 'pwrledspd', 1, 64, -1)
        self.display.hw.setPowerLedSpeed(self.temp['pwrledspd'])
    #enddef


    def plus2g8Button(self):
        self._value(7, 'pwrledspd', 1, 64, 1)
        self.display.hw.setPowerLedSpeed(self.temp['pwrledspd'])
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
                'button4' : "",
                'button5' : "MC2Net (bootloader)",

                'button6' : "WiFi AP (always)",
                'button7' : "WiFi Client (always)",
                'button8' : "WiFi Off (always)",
                'button9' : "",
                'button10' : "MC2Net (firmware)",

                'button11' : "Netinfo",
                'button12' : "State",
                'button13' : "",
                'button14' : "",
                'button15' : "",
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


    def button5ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.mc2net,
                continueParmas = { 'bootloader' : True },
                line1 = "This shuts down GUI and connect",
                line2 = "the MC bootloader to TCP port.",
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
            self.display.hw.mcc.reset()
        #endif
        pid = subprocess.Popen([
            defines.Mc2NetCommand,
            defines.motionControlDevice,
            str(defines.socatPort),
            str(baudrate)]).pid
        self.display.shutDown(False)
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


    def button10ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.mc2net,
                continueParmas = { 'bootloader' : False },
                line1 = "This shuts down GUI and connect",
                line2 = "the motion controller to TCP port.",
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


class PageFeedMe(Page):

    def __init__(self, display, expo):
        self.pageUI = "error"
        self.pageTitle = "Feed me"
        super(PageFeedMe, self).__init__(display)
        self.expo = expo
        self.items.update({
            'line2' : "Fill the tank and press back.",
            })
    #enddef


    def show(self):
        super(PageFeedMe, self).show()
        self.display.hw.powerLed("error")
    #enddef


    def backButtonRelease(self):
        self.display.hw.powerLed("normal")
        self.expo.setResinVolume(defines.resinFilled)
        self.expo.doContinue()
        return super(PageFeedMe, self).backButtonRelease()
    #enddef


    def turnoffButtonRelease(self):
        self.display.hw.powerLed("normal")
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


class PageTuneTilt(ProfilesPage):

    def __init__(self, display):
        self.profilesFilename = "tilt_tune_profiles.json"
        self.profilesNames = display.hw.getTiltProfilesNames()
        self.pageTitle = "Admin - Tilt Tune"
        super(PageTuneTilt, self).__init__(display, items = {
                "label1g1" : 'down slow',
                "label1g2" : 'down fast',
                "label1g3" : 'up',

                "label2g1" : "init profile",
                "label2g2" : "offset steps",
                "label2g3" : "offset delay [ms]",
                "label2g4" : "finish profile",
                "label2g5" : "tilt cycles",
                "label2g6" : "tilt delay [ms]",
                "label2g7" : "homing tolerance",
                "label2g8" : "homing cycles",

                "button1" : "Export",
                "button2" : "Import",
                "button4" : "Save",
                "back" : "Back",
                })
        self.nameIndexes = set((0,3))
        self.profileItems = 8
    #enddef


    def show(self):
        super(PageTuneTilt, self).show()
        self.profiles = deepcopy(self.display.hwConfig.tuneTilt)
        self._setProfile()
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        self.display.hwConfig.update(
            tiltdownlargefill = ' '.join(str(n) for n in self.profiles[0]),
            tiltdownsmallfill = ' '.join(str(n) for n in self.profiles[1]),
            tiltup = ' '.join(str(n) for n in self.profiles[2])
        )
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        self.display.hwConfig._parseData()
        return super(PageTuneTilt, self).backButtonRelease()
    #enddef


    def backButtonRelease(self):
        self.display.page_tiltmove.changeProfiles(True)
        return super(PageTuneTilt, self).backButtonRelease()
    #endif


    def state1g4ButtonRelease(self):
        pass
    #enddef


    def state1g5ButtonRelease(self):
        pass
    #enddef


    def state1g6ButtonRelease(self):
        pass
    #enddef


    def state1g7ButtonRelease(self):
        pass
    #enddef


    def state1g8ButtonRelease(self):
        pass
    #enddef


    #init profile
    def minus2g1Button(self):
        self._value(0, 0, 7, -1)
    #enddef

    def plus2g1Button(self):
        self._value(0, 0, 7, 1)
    #enddef


    #offset steps
    def minus2g2Button(self):
        self._value(1, 0, 2000, -10)
    #enddef

    def plus2g2Button(self):
        self._value(1, 0, 2000, 10)
    #enddef


    #offset delay [ms]
    def minus2g3Button(self):
        self._value(2, 0, 4000, -10)
    #enddef

    def plus2g3Button(self):
        self._value(2, 0, 4000, 10)
    #enddef


    #finish profile
    def minus2g4Button(self):
        self._value(3, 0, 7, -1)
    #enddef

    def plus2g4Button(self):
        self._value(3, 0, 7, 1)
    #enddef


    #tilt cycles
    def minus2g5Button(self):
        self._value(4, 1, 10, -1)
    #enddef

    def plus2g5Button(self):
        self._value(4, 1, 10, 1)
    #enddef


    #tilt delay [ms]
    def minus2g6Button(self):
        self._value(5, 0, 4000, -10)
    #enddef

    def plus2g6Button(self):
        self._value(5, 0, 4000, 10)
    #enddef


    #homing tolerance
    def minus2g7Button(self):
        self._value(6, 0, 512, -1)
    #enddef
    
    def plus2g7Button(self):
        self._value(6, 0, 512, 1)
    #enddef


    #homing cycles
    def minus2g8Button(self):
        self._value(7, 1, 10, -1)
    #enddef
    
    def plus2g8Button(self):
        self._value(7, 1, 10, 1)
    #enddef

#endclass


class PageMedia(Page):

    def __init__(self, display):
        self.base_path = defines.multimediaRootPath
        self.path = None
        super(PageMedia, self).__init__(display)
    #enddef

    def setMedia(self, relative_path):
        self.path = relative_path
    #enddef

    def fillData(self):
        return {
            'relative_path': self.path,
            'base_path': self.base_path,
            'absolute_path': os.path.join(self.base_path, self.path)
        }
    #enddef

    def show(self):
        self.items.update(self.fillData())
        super(PageMedia, self).show()
    #enddef

#endclass

class PageImage(PageMedia):

    def __init__(self, display):
        self.pageUI = "image"
        self.pageTitle = "Image"
        self.path = None
        super(PageImage, self).__init__(display)
    #enddef

#endclass


class PageVideo(PageMedia):

    def __init__(self, display):
        self.pageUI = "video"
        self.pageTitle = "Video"
        self.path = None
        super(PageVideo, self).__init__(display)
    #enddef

#endclass
