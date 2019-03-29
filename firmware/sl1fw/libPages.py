# part of SL1 firmware
# -*- coding: utf-8 -*-
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from time import sleep
import json
import subprocess
import signal
import glob
import pydbus
from copy import deepcopy
import time
import re
import urllib2
import tarfile

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
    #enddef


    @property
    def octoprintAuth(self):
        try:
            with open(defines.octoprintAuthFile, "r") as f:
                return f.read()
            #endwith
        except IOError as e:
            self.logger.exception("octoprintAuthFile exception: %s" % str(e))
            return None
        #endtry
    #enddef


    def fill(self):
        self.items = {
                "image_version" : self.display.hwConfig.os.versionId,
                "page_title" : self.pageTitle,
                "save_path" : self.getSavePath(),
                }
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
                text = _("Do you really want to turn off the printer?"))
        return "confirm"
    #enddef


    def turnoffContinue(self):
        pageWait = PageWait(self.display, line1 = _("Shutting down"))
        pageWait.show()
        self.display.shutDown(True)
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
        self.changed[val] = str(self.temp[val])
        self.showItems(**{ 'state1g%d' % (index + 1) : int(self.temp[val]) })
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
                items[index] = int(value)
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
            pageWait.showItems(line2 = self.display.hw.getTowerPosition())
        #endwhile
        if self.display.hw.towerSyncFailed():
            self.display.page_error.setParams(
                    text = _("""Tower homing failed!

Check printer's hardware."""))
            return "error"
        #endif
        return "_SELF_"
    #enddef


    def _syncTilt(self):
        if not self.display.hw.tiltSyncWait(retries = 2):
            self.display.page_error.setParams(
                    text = _("""Tilt homing failed!

Check printer's hardware."""))
            return "error"
        #endif
        return "_SELF_"
    #enddef


    def _strZHop(self, value):
        return "%.3f" % self.display.hwConfig.calcMM(value)
    #enddef


    def _strOffset(self, value):
        return "%+.3f" % self.display.hwConfig.calcMM(value)
    #enddef


    def _strTenth(self, value):
        return "%.1f" % (value / 10.0)
    #enddef

#endclass


class PageWait(Page):

    def __init__(self, display, **kwargs):
        self.pageUI = "wait"
        self.pageTitle = _("Wait")
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
        self.pageTitle = _("Confirm")
        super(PageConfirm, self).__init__(display)
        self.stack = False
    #enddef


    def setParams(self, **kwargs):
        self.continueFce = kwargs.pop("continueFce", None)
        self.continueParams = kwargs.pop("continueParams", dict())
        self.backFce = kwargs.pop("backFce", None)
        self.backParams = kwargs.pop("backParams", dict())
        self.fill()
        self.items.update(kwargs)
    #enddef


    def contButtonRelease(self):
        if self.continueFce is None:
            return "_EXIT_MENU_"
        else:
            return self.continueFce(**self.continueParams)
        #endif
    #enddef


    def backButtonRelease(self):
        if self.backFce is None:
            return "_BACK_"
        else:
            return self.backFce(**self.backParams)
        #endif
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
        self.pageTitle = _("Project")
        super(PagePrintPreview, self).__init__(display)
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PagePrintPreview, self).show()
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Setting start positions"))
        pageWait.show()

        self.display.hw.towerSync()
        syncRes = self.display.hw.tiltSyncWait(retries = 2)
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile

        if self.display.hw.towerSyncFailed():
            self.display.hw.motorsRelease()
            self.display.page_error.setParams(
                    text = _("""Tower homing failed!

Check printer's hardware.

Job was canceled."""))
            return "error"
        #endif

        if not syncRes:
            self.display.hw.motorsRelease()
            self.display.page_error.setParams(
                    text = _("""Tilt homing failed!

Check printer's hardware.

Job was canceled."""))
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
        self.pageTitle = _("Confirm")
        super(PagePrintStart, self).__init__(display)
    #enddef


    def show(self):
        perc = self.display.hw.calcPercVolume(self.display.config.usedMaterial + defines.resinMinVolume)
        lines = {
                'name' : self.display.config.projectName,
                }
        if perc <= 100:
            lines.update({
                'text' : _("Please fill resin tank at least at %d %%.") % perc
                })
        else:
            lines.update({
                'text' : _("""Please fill resin tank to line 100 %.

Refill will be required during printing."""),
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


class PageStart(Page):

    def __init__(self, display):
        self.pageUI = "start"
        self.pageTitle = _("Start")
        super(PageStart, self).__init__(display)
    #enddef

#endclass


class PageHome(Page):

    def __init__(self, display):
        self.pageUI = "home"
        self.pageTitle = _("Home")
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
# FIXME temporaily disabled until it works perfectly on all printers
#        if self.display.hwConfig.showWizard:
#            self.display.page_confirm.setParams(
#                    continueFce = self.showWizard,
#                    text = _("""Printer needs to be set up!
#
#Go through wizard now?"""))
#            return "confirm"
        #endif
        if not self.display.hwConfig.calibrated:
            self.display.page_confirm.setParams(
                    continueFce = self.printContinue,
                    text = _("""Printer is not calibrated!

Calibrate now?"""))
            return "confirm"
        #endif

        return "sourceselect"
    #enddef


    def showWizard(self):
        return "wizard"
    #enddef


    def printContinue(self):
        return "calibration"
    #enddef

#endclass


class PageControl(Page):

    def __init__(self, display):
        self.pageUI = "control"
        self.pageTitle = _("Control")
        super(PageControl, self).__init__(display)
    #enddef


    def show(self):
        self.moving = False
        super(PageControl, self).show()
    #enddef


    def topButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = _("Moving platform to top"))
        pageWait.show()
        retc = self._syncTower(pageWait)
        self.display.hw.motorsHold()
        self.display.hw.powerLed("normal")
        return retc
    #enddef


    def tankresButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line2 = _("Tank reset"))
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


    def disablesteppersButtonRelease(self):
        self.display.hw.motorsRelease()
    #enddef

#endclass


class PageSettings(Page):

    def __init__(self, display):
        self.pageUI = "settings"
        self.pageTitle = _("Settings")
        super(PageSettings, self).__init__(display)
    #enddef


    def networkButtonRelease(self):
        return "network"
    #enddef


    def recalibrationButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce = self.calibrateContinue,
            text = _("Calibrate printer now?"))
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


class PageTimeSettings(Page):

    def __init__(self, display):
        self.pageUI = "timesettings"
        self.pageTitle = _("Time Settings")
        self.timedate = pydbus.SystemBus().get("org.freedesktop.timedate1")
        super(PageTimeSettings, self).__init__(display)
    #enddef


    def fillData(self):
        return {
            "ntp": self.timedate.NTP,
            "unix_timestamp_sec": time.time(),
            "timezone": self.timedate.Timezone
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageTimeSettings, self).show()
    #enddef


    def ntpenableButtonRelease(self):
        self.timedate.SetNTP(True, False)
    #enddef


    def ntpdisableButtonRelease(self):
        self.timedate.SetNTP(False, False)
    #enddef


    def settimeButtonSubmit(self, data):
        return "settime"
    #enddef


    def setdateButtonSubmit(self, data):
        return "setdate"
    #enddef


    def settimezoneButtonSubmit(self, data):
        return "settimezone"
    #enddef

#endclass


class PageSetTimeBase(Page):

    def __init__(self, display):
        self.timedate = pydbus.SystemBus().get("org.freedesktop.timedate1")
        super(PageSetTimeBase, self).__init__(display)
    #enddef


    def fillData(self):
        return {
            "unix_timestamp_sec": time.time(),
            "timezone": self.timedate.Timezone
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetTimeBase, self).show()
    #enddef


    def settimeButtonSubmit(self, data):
        self.timedate.SetNTP(False, False)
        self.timedate.SetTime(float(data['unix_timestamp_sec']) * 1000000, False, False)

        return "_BACK_"
    #enddef

#endclass


class PageSetTime(PageSetTimeBase):

    def __init__(self, display):
        self.pageUI = "settime"
        self.pageTitle = _("Set Time")
        super(PageSetTime, self).__init__(display)
    #enddef

#endclass


class PageSetDate(PageSetTimeBase):

    def __init__(self, display):
        self.pageUI = "setdate"
        self.pageTitle = _("Set Date")
        super(PageSetDate, self).__init__(display)
    #enddef

#endclass


class PageSetTimezone(Page):
    zoneinfo = "/usr/share/zoneinfo/"

    def __init__(self, display):
        self.pageUI = "settimezone"
        self.pageTitle = _("Set Timezone")
        self.timedate = pydbus.SystemBus().get("org.freedesktop.timedate1")

        # Available timezones
        regions = [zone.replace(PageSetTimezone.zoneinfo, "") for zone in glob.glob(os.path.join(PageSetTimezone.zoneinfo, "*"))]
        self.timezones = {}
        for region in regions:
            cities = [os.path.basename(city) for city in glob.glob(os.path.join(PageSetTimezone.zoneinfo, region, "*"))]
            self.timezones[region] = cities

        super(PageSetTimezone, self).__init__(display)
    #enddef


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
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetTimezone, self).show()
    #enddef


    def settimezoneButtonSubmit(self, data):
        try:
            timezone = "%s/%s" % (data['region'], data['city'])
        except:
            timezone = data['timezone']

        self.timedate.SetTimezone(timezone, False)

        return "_BACK_"
    #enddef

#endclass


class PageSetHostname(Page):

    def __init__(self, display):
        self.pageUI = "sethostname"
        self.pageTitle = _("Set Hostname")
        self.hostname = pydbus.SystemBus().get("org.freedesktop.hostname1")
        super(PageSetHostname, self).__init__(display)
    #enddef


    def fillData(self):
        return {
            "hostname": self.hostname.StaticHostname
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetHostname, self).show()
    #enddef


    def sethostnameButtonSubmit(self, data):
        hostname = data['hostname']
        self.hostname.SetStaticHostname(hostname, False)
        self.hostname.SetHostname(hostname, False)

        return "_BACK_"
    #enddef

#endclass


class PageSetLanguage(Page):

    def __init__(self, display):
        self.pageUI = "setlanguage"
        self.pageTitle = _("Set Language")
        self.locale = pydbus.SystemBus().get("org.freedesktop.locale1")
        super(PageSetLanguage, self).__init__(display)
    #enddef


    def fillData(self):
        try:
            locale = str(self.locale.Locale)
            lang = re.match(".*'LANG=(.*)'.*", locale).groups()[0]
        except:
            lang = ""

        return {
            "locale": lang
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetLanguage, self).show()
    #enddef


    def setlocaleButtonSubmit(self, data):
        try:
            self.locale.SetLocale([data['locale']], False)
        except:
            self.logger.error("Setting locale failed")

        return "_BACK_"
    #enddef

#endclass


class PageAdvancedSettings(Page):

    def __init__(self, display):
        self.pageUI = "advancedsettings"
        self.pageTitle = _("Advanced Settings")
        super(PageAdvancedSettings, self).__init__(display)
    #enddef


    def show(self):
        self.items.update({ 'showAdmin' : int(self.display.hwConfig.showAdmin) })
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


    def timesettingsButtonRelease(self):
        return "timesettings"
    #enddef


    def sethostnameButtonRelease(self):
        return "sethostname"
    #enddef


    def setlanguageButtonRelease(self):
        return "setlanguage"
    #enddef

#endclass


class PageSupport(Page):

    def __init__(self, display):
        self.pageUI = "support"
        self.pageTitle = _("Support")
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
        self.pageTitle = _("Firmware Update")
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
            continueFce = self.fetchUpdate,
            continueParams = { 'fw_url': fw_url },
            text = _("Do you really want to update firmware?"))
        return "confirm"
    #enddef


    def fetchUpdate(self, fw_url):
        """Fetches file specified by url info ramdisk while displaying progress and watching for problems. Once the
         fetch is finished the doUpdate is called with fetched file.

        This is implemented as chunked copy from source file descriptor to the deestination file descriptor. The
        progress is updated once the cunk is copied. The source file descriptor is either standard file when the source
        is mounted USB drive or urlopen result."""

        pageWait = PageWait(self.display, line1 = _("Fetching firmware"))
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
                        pageWait.showItems(line2 = "%d%%" % progress)
                        old_progress = progress
                    #endif
                #endwhile
            #endwith

            source.close()
        #endtry
        except Exception as e:
            self.logger.error("Firmware fetch failed: " + str(e))
            self.display.page_error.setParams(
                    text = _("Firmware fetch failed!"))
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

        pageWait = PageWait(self.display, line1 = _("Updating firmware"))
        pageWait.show()

        try:
            while True:
                operation = self.rauc.Operation
                progress = self.rauc.Progress

                pageWait.showItems(
                    line2 = progress[1],
                    line3 = "%d%%" % progress[0]
                )

                # Check progress for update done
                if progress[1] == 'Installing done.':
                    pageWait.showItems(
                        line1 = _("Update done"),
                        line2 = _("Shutting down"))
                    sleep(3)
                    self.display.shutDown(True, reboot=True)
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
                    text = _("Update failed!"))
            return "error"
        #endexcept
    #enddef

#endclass


class PageManual(Page):

    def __init__(self, display):
        self.pageUI = "manual"
        self.pageTitle = _("Manual")
        super(PageManual, self).__init__(display)
        self.items.update({
            'manual_url': defines.manualURL,
            #'text' : "",
        })
    #enddef

#endclass


class PageVideos(Page):

    def __init__(self, display):
        self.pageUI = "videos"
        self.pageTitle = _("Videos")
        super(PageVideos, self).__init__(display)
        self.items.update({
            'videos_url': defines.videosURL,
            #'text' : "",
        })
    #enddef

#endclass


class PageNetwork(Page):

    def __init__(self, display):
        self.pageUI = "network"
        self.pageTitle = _("Network")
        super(PageNetwork, self).__init__(display)
    #enddef


    # TODO net state - mode, all ip with devices, all uri (log, debug, display, octoprint)
    def fillData(self):
        devlist_structured = []
        for addr, dev in self.display.inet.devices.iteritems():
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
            continueFce = self.setclient,
            continueParams = { 'ssid': data['client-ssid'], 'psk': data['client-psk'] },
            text = _("""Do you really want to set wifi to client mode?

It may disconnect web client."""))
        return "confirm"
    #enddef


    def apsetButtonSubmit(self, data):
        self.display.page_confirm.setParams(
            continueFce = self.setap,
            continueParams = { 'ssid': data['ap-ssid'], 'psk': data['ap-psk'] },
            text = _("""Do you really want to set wifi to ap mode?

It may disconnect web client."""))
        return "confirm"
    #enddef


    def wifioffButtonSubmit(self, data):
        self.display.page_confirm.setParams(
            continueFce = self.wifioff,
            text = _("""Do you really want to turn off wifi?

It may disconnect web client."""))
        return "confirm"
    #enddef


    def wifionButtonSubmit(self, data):
        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.StartAP()
            wifisetup.EnableAP()
        except:
            self.logger.error("Setting wifi ap mode (wifi on)")
        #endtry
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
        pageWait = PageWait(self.display, line1 = _("Setting interface params..."))
        pageWait.show()

        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.ClientSSID = ssid
            wifisetup.ClientPSK = psk
            wifisetup.StartClient()
            wifisetup.EnableClient()
        except:
            self.logger.error("Setting wifi client params failed: ssid:%s psk:%s", ssid, psk)
        #endtry

        # Connecting...
        pageWait.showItems(line1 = _("Connecting..."))
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
                text = _("Connection failed!"))
        return "error"
    #enddef


    def setap(self, ssid, psk):
        pageWait = PageWait(self.display, line1 = _("Setting interface params..."))
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
        pageWait.showItems(line1 = _("Starting AP..."))
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
                text = _("AP failed!"))
        return "error"
    #enddef

#endclass


class PageQRCode(Page):

    def __init__(self, display):
        self.pageUI = "qrcode"
        self.pageTitle = _("QR Code")
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
        self.pageTitle = _("Print")
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
        self.items.update({ 'showAdmin' : int(self.display.hwConfig.showAdmin) })
        self.items.update(self.fillData())
        super(PagePrint, self).show()
    #enddef


    def feedmeButtonRelease(self):
        self.display.page_feedme.setItems(text = _("Wait for layer finish please."))
        self.expo.doFeedMe()
        return "feedme"
    #enddef


    def updownButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce = self.doUpAndDown,
            text = _("""Do you really want to go platform up and down?

It may affect the result!"""))
        return "confirm"
    #enddef


    def doUpAndDown(self):
        self.expo.doUpAndDown()
        self.display.page_systemwait.fill(
            line1 = _("Up and down will be executed after layer finish."))
        return "systemwait"
    #enddef


    def settingsButtonRelease(self):
        return "change"
    #enddef


    def turnoffButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce = self.exitPrint,
            text = _("Do you really want to cancel actual job?"))
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
            line1 = _("Job will be canceled after layer finish"))
        return "systemwait"
    #enddef


    def _pauseunpause_text(self):
        return 'UnPause' if self.expo.paused else 'Pause'
    #enddef

#endclass


class PageChange(Page):

    def __init__(self, display):
        self.pageUI = "change"
        self.pageTitle = _("Change Exposure Times")
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
        #endif
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
        self.pageTitle = _("System Information")
        super(PageSysInfo, self).__init__(display)
        self.items.update({
                'serial_number': self.display.hw.getCPUSerial(),
                'system_name': self.display.hwConfig.os.name,
                'system_version': self.display.hwConfig.os.version,
                'firmware_version': defines.swVersion,
                'api_key': self.octoprintAuth
                })
        self.callbackPeriod = 0.5
        self.skip = 11
    #enddef


    def show(self):
        self.oldValues = {}
        self.items['controller_version'] = self.display.hw.getControllerVersion()
        self.items['controller_serial'] = self.display.hw.getControllerSerial()
        self.display.hw.resinSensor(True)
        self.skip = 11
        super(PageSysInfo, self).show()
    #enddef


    def menuCallback(self):
        items = {}
        if self.skip > 10:
            self._setItem(items, 'fans', {'fan%d_rpm' % i: v for i, v in enumerate(self.display.hw.getFansRpm())})
            self._setItem(items, 'temps', {'temp%d_celsius' % i: v for i, v in enumerate(self.display.hw.getMcTemperatures())})
            self._setItem(items, 'cpu_temp', self.display.hw.getCpuTemperature())
            self._setItem(items, 'leds', {'led%d_voltage_volt' % i: v for i, v in enumerate(self.display.hw.getVoltages())})
            self.skip = 0
        #endif
        self._setItem(items, 'resin_sensor_state', self.display.hw.getResinSensorState())
        self._setItem(items, 'cover_state', self.display.hw.isCoverClosed())
        self._setItem(items, 'power_switch_state', self.display.hw.getPowerswitchState())

        if len(items):
            self.showItems(**items)
        #endif

        self.skip += 1
    #enddef


    def backButtonRelease(self):
        self.display.hw.resinSensor(False)
        return super(PageSysInfo, self).backButtonRelease()
    #enddef

#endclass


class PageNetInfo(Page):

    def __init__(self, display):
        self.pageUI = "netinfo"
        self.pageTitle = _("Network Information")
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
                    items["line1"] = _("SSID: %(ssid)s  password: %(pass)s") % { 'ssid' : wifiData['ssid'], 'pass' : wifiData['psk'] }
                    items['mode'] = 'ap'
                    items['ap_ssid'] = wifiData['ssid']
                    items['ap_psk'] = wifiData['psk']
                    items["line2"] = _("Setup URL: %s") % (ip + defines.wifiSetupURI)
                    items['ap_setup_url'] = "%s%s" % (ip, defines.wifiSetupURI)
                    items["qr1label"] = _("WiFi")
                    items["qr1"] = "WIFI:S:%s;T:WPA;P:%s;H:false;" % (wifiData['ssid'], wifiData['psk'])
                    items["qr2label"] = _("Setup URL")
                    items["qr2"] = "http://%s%s" % (ip, defines.wifiSetupURI)
                except Exception:
                    self.logger.exception("wifi setup file exception:")
                    items["line1"] = _("Error reading WiFi setup!")
                    items["line2"] = ""
                    items["qr1label"] = ""
                    items["qr1"] = ""
                    items["qr2label"] = ""
                    items["qr2"] = ""
                #endtry
            else:
                # client mode
                ip = self.display.inet.getIp()
                items["line1"] = _("IP address: %s") % ip
                items["line2"] = _("Hostname: %s") % self.display.inet.getHostname()
                items['mode'] = "client"
                items['client_ip'] = ip
                items['client_hostname'] = self.display.inet.getHostname()
                items["qr1label"] = _("Logfile")
                items["qr1"] = "http://%s/log" % ip
                items["qr2label"] = _("MC debug")
                items["qr2"] = "http://%s/debug" % ip
            #endif
        else:
            # no internet connection
            items['mode'] = None
            items["line1"] = _("Not connected to network")
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
        self.pageTitle = _("About")
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
                text = _("""Do you really want to enable admin menu?

Wrong settings may damage your printer!"""))
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
        #endtry

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
        self.pageTitle = _("Projects")
        self.currentRoot = "."
        self.old_items = None
        super(PageSrcSelect, self).__init__(display)
        self.stack = False
        self.callbackPeriod = 1
    #enddef


    def in_root(self):
        return self.currentRoot == "."
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
                if item['type'] == 'dir':
                    if item['name'] in dirs:
                        item['numitems'] += dirs[item['name']]['numitems']
                    #endif
                    dirs[item['name']] = item
                else:
                    files.append(item)
                #endif
            #endfor
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
        ip = self.display.inet.getIp()
        if ip != "none" and self.octoprintAuth:
            text = "%s%s (%s)" % (ip, defines.octoprintURI, self.octoprintAuth)
        else:
            text = _("Not connected to network")
        #endif

        return {
            'text': text,
            'sources': self.source_list()
        }
    #enddef


    def show(self):
        self.items = self.fillData()
        super(PageSrcSelect, self).show()
    #enddef


    def menuCallback(self):
        items = self.fillData()
        if self.old_items != items:
            self.showItems(**items)
            self.old_items = items
    #enddef


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
            self.showItems(text, "%s%s (%s)" % (ip, defines.octoprintURI, self.octoprintAuth))
        else:
            self.showItems(text, _("Not connected to network"))
        #endif
    #enddef


    def loadProject(self, project_path):
        pageWait = PageWait(self.display, line1 = _("Reading project data..."))
        pageWait.show()
        self.checkConfFile(project_path)
        config = self.display.config

        if not config.configFound:
            sleep(0.5)
            self.display.page_error.setParams(
                    text = _("""Your project has a problem: %s project not found.

Regenerate it and try again.""") % project_path)
            return "error"
        elif config.zipError is not None:
            sleep(0.5)
            self.display.page_error.setParams(
                    text = _("""Your project has a problem: %s

Regenerate it and try again.""") % config.zipError)
            return "error"
        #endif

        return "printpreview"
    #endef


    def backButtonRelease(self):
        self.currentRoot = "."
        return super(PageSrcSelect, self).backButtonRelease()
    #enddef

#endclass


class PageError(Page):

    # TODO PageFatalError with pageUI = "error" (poweroff)

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Error")
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


    def contButtonRelease(self):
        self.display.hw.powerLed("normal")
        return super(PageError, self).backButtonRelease()
    #enddef

#endclass


class PageTiltTower(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = _("Tilt & Tower")
        super(PageTiltTower, self).__init__(display)
        self.items.update({
                'button1' : _("Tilt home"),
                'button2' : _("Tilt move"),
                'button3' : _("Tilt test"),
                'button4' : _("Tilt profiles"),
                'button5' : _("Tilt home calib."),

                'button6' : _("Tower home"),
                'button7' : _("Tower move"),
                'button8' : _("Tower test"),
                'button9' : _("Tower profiles"),
                'button10' : _("Tower home calib."),

                'button11' : _("Turn motors off"),
                'button12' : _("Tune tilt"),
                'button13' : _("Tilt home test"),
                'button14' : _("Tower offset"),
                'button15' : "",
                })
    #enddef


    def button1ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tilt home"))
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
        pageWait = PageWait(self.display, line1 = _("Tilt sync"))
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = _("Tilt up"))
        self.display.hw.tiltLayerUpWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = _("Tilt down"))
        self.display.hw.tiltLayerDownWait()
        self.display.hw.beepEcho()
        sleep(1)
        pageWait.showItems(line1 = _("Tilt up"))
        self.display.hw.tiltLayerUpWait()
        self.display.hw.beepEcho()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button4ButtonRelease(self):
        return "tiltprofiles"
    #enddef


    def button5ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tilt home calibration"))
        pageWait.show()
        self.display.hw.tiltHomeCalibrateWait()
        self.display.hw.motorsRelease()
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button6ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Moving platform to top"))
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
        pageWait = PageWait(self.display, line1 = _("Moving platform to top"))
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line1 = _("Moving platform to zero"))
        self.display.hw.towerToZero()
        while not self.display.hw.isTowerOnZero():
            sleep(0.25)
            pageWait.showItems(line2 = self.display.hw.getTowerPosition())
        #endwhile
        self.display.hw.powerLed("normal")
        return "_SELF_"
    #enddef


    def button9ButtonRelease(self):
        return "towerprofiles"
    #enddef


    def button10ButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tower home calibration"))
        pageWait.show()
        self.display.hw.towerHomeCalibrateWait()
        self.display.hw.motorsRelease()
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
        pageWait = PageWait(self.display, line1 = _("Tilt home test"))
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
        return "toweroffset"
    #enddef

#endclass


class PageDisplay(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = _("Display")
        super(PageDisplay, self).__init__(display)
        self.items.update({
                'button1' : _("Chess 8"),
                'button2' : _("Chess 16"),
                'button3' : _("Grid 8"),
                'button4' : _("Grid 16"),
                'button5' : _("Maze"),

                'button6' : "USB:/test.png",
                'button7' : "Prusa logo",
                'button8' : "",
                'button9' : "",
                'button10' : _("Infinite test"),

                'button11' : _("Black"),
                'button12' : _("Inverse"),
                'button13' : "",
                'button14' : "",
                'button15' : "",
                })
    #enddef


    def show(self):
        self.display.screen.getImgBlack()
        self.display.screen.inverse()
        self.display.hw.uvLed(True)
        self.items['button14'] = _("UV off")
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


    def button7ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "logo_1440x2560.png"))
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
        pageWait = PageWait(self.display,
            line1 = _("Infinite test..."),
            line2 = _("Tower cycles: %d") % towerCounter,
            line3 = _("Tilt cycles: %d") % tiltCounter)
        pageWait.show()
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice16_1440x2560.png"))
        self.display.hw.uvLed(True)
        self.display.hw.towerSync()
        while True:
            if not self.display.hw.isTowerMoving():
                if towerStatus == 0:    #tower moved to top
                    towerCounter += 1
                    pageWait.showItems(line2 = _("Tower cycles: %d") % towerCounter)
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
                    pageWait.showItems(line3 = _("Tilt cycles: %d") % tiltCounter)
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
        self.showItems(button14 = _("UV off") if state else _("UV on"))
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
        self.pageTitle = _("Admin Home")
        super(PageAdmin, self).__init__(display)
        self.items.update({
                'button1' : _("Tilt & Tower"),
                'button2' : _("Display"),
                'button3' : _("Fans & LEDs"),
                'button4' : _("Hardware setup"),
                'button5' : _("Exposure setup"),

                'button6' : _("Flash MC"),
                'button7' : _("Erase MC EEPROM"),
                'button8' : _("MC2Net (bootloader)"),
                'button9' : _("MC2Net (firmware)"),
                'button10' : _("Resin sensor test"),

                'button11' : _("Net update"),
                'button12' : _("Download examples"),
                'button13' : _("Wizard"),
                'button14' : _("Change API-key"),
                'button15' : _("Factory reset"),
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
                text = _("""This overwrites the motion controller with supplied firmware.

Are you sure?"""))
        return "confirm"
    #enddef


    def button6Continue(self):
        self.display.hw.flashMC(self.display.page_systemwait, self.display.actualPage)
        return "_BACK_"
    #enddef


    def button7ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.button7Continue,
                text = _("""This will erase all profiles and other motion controller settings.

Are you sure?"""))
        return "confirm"
    #enddef


    def button7Continue(self):
        pageWait = PageWait(self.display, line1 = _("Erasing EEPROM"))
        pageWait.show()
        self.display.hw.eraseEeprom()
        return "_BACK_"
    #enddef


    def button8ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.mc2net,
                continueParams = { 'bootloader' : True },
                text = _("""This stops GUI and connect the MC bootloader to TCP port.


Are you sure?"""))
        return "confirm"
    #enddef


    def button9ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.mc2net,
                continueParams = { 'bootloader' : False },
                text = _("""This stops GUI and connect the motion controller to TCP port.

Are you sure?"""))
        return "confirm"
    #enddef


    def mc2net(self, bootloader = False):
        ip = self.display.inet.getIp()
        if ip == "none":
            self.display.page_error.setParams(
                    text = _("Not connected to network"))
            return "error"
        #endif

        baudrate = 19200 if bootloader else 115200
        if bootloader:
            self.display.hw.mcc.reset()
        #endif

        self.display.hw.switchToDummy()

        pid = subprocess.Popen([
            defines.Mc2NetCommand,
            defines.motionControlDevice,
            str(defines.socatPort),
            str(baudrate)], preexec_fn=os.setsid).pid

        self.display.page_confirm.setParams(
                continueFce = self.mc2netStop,
                continueParams = { 'pid' : pid },
                backFce = self.mc2netStop,
                backParams = { 'pid' : pid },
                text = _("""Baudrate is %(br)d.

Serial line is redirected to %(ip)s:%(port)d.

Press Continue when done.""") % { 'br' : baudrate, 'ip' : ip, 'port' : defines.socatPort })
        return "confirm"
    #enddef


    def mc2netStop(self, pid):
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        self.display.hw.switchToMC(self.display.page_systemwait, self.display.actualPage)
        return "_BACK_"
    #enddef


    def button10ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.button10Continue,
                text = _("Is tank filled and secured with both screws?"))
        return "confirm"
    #enddef


    def button10Continue(self):
        # TODO vyzadovat zavreny kryt po celou dobu!
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Moving platform to top"))
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line1 = _("Tilt home"), line2 = "")
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.setTiltProfile('layerMoveSlow')
        self.display.hw.tiltUpWait()

        pageWait.showItems(line2 = _("Measuring"), line3 = _("Do NOT TOUCH the printer"))
        volume = self.display.hw.getResinVolume()
        self.display.hw.powerLed("normal")
        if not volume:
            self.display.page_error.setParams(
                    text = _("""Resin measure failed!

Is tank filled and secured with both screws?"""))
            return "error"
        #endif

        self.display.page_confirm.setParams(
                continueFce = self.backButtonRelease,
                text = _("Measured resin volume: %d ml") % volume)
        return "confirm"
    #enddef


    def button11ButtonRelease(self):
        return "netupdate"
    #enddef


    def button12ButtonRelease(self):
        try:
            if not os.path.isdir(defines.internalProjectPath):
                os.makedirs(defines.internalProjectPath)
            #endif

            self.downloadURL(defines.examplesURL, defines.examplesArchivePath, title = _("Fetching examples"))

            pageWait = PageWait(self.display, line1 = _("Decompressing examples"))
            pageWait.show()
            pageWait.showItems(line1 = _("Extracting examples"))
            with tarfile.open(defines.examplesArchivePath) as tar:
                tar.extractall(path=defines.internalProjectPath)
            pageWait.showItems(line1 = _("Cleaning up"))
            os.remove(defines.examplesArchivePath)

            return "_BACK_"

        except Exception as e:
            self.logger.error("Exaples fetch failed: " + str(e))
            self.display.page_error.setParams(
                text = _("Examples fetch failed"))
            return "error"
    #enddef


    def downloadURL(self, url, dest, title = None):
        if not title:
            title = _("Fetching")
        #endif
        pageWait = PageWait(self.display, line1 = title, line2 = "0%")
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
                    pageWait.showItems(line2 = "%d%%" % progress)
                    old_progress = progress
                # endif
            # endwhile
        # endwith
    #enddef


    def button13ButtonRelease(self):
        return "wizard"
    #enddef


    def button14ButtonRelease(self):
        return "setapikey"
    #enddef


    def button15ButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce = self.button15Continue,
            text = _("""Do you really want to do factory reset?

All settings will be deleted!"""))
        return "confirm"
    #enddef


    def button15Continue(self):
        pageWait = PageWait(self.display, line1 = _("Please wait..."))
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
        #slightly press the foam against printers base
        self.display.hw.towerMoveAbsolute(self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(93))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hwConfig.update(
            towerheight = self.display.hwConfig.calcMicroSteps(defines.defaultTowerHeight),
            tiltheight = defines.defaultTiltHeight,
            calibrated = "no",
            showadmin = "no",
            showwizard = "yes"
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
        self.pageTitle = _("Net Update")
        super(PageNetUpdate, self).__init__(display)

        self.firmwares = list(enumerate(defines.netFirmwares))

        # Create items for updating firmwares
        self.items.update({
            "button%s" % (i + 1): _("Update to %s") % _(firmware['name']) for (i, firmware) in self.firmwares
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
            continueFce = self.display.page_firmwareupdate.fetchUpdate,
            continueParams = { 'fw_url': url },
            text = _("""Updating to %s.

Proceed update?""") % name)
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
                'button1' : _("Export"),
                'button2' : _("Import"),
                'button4' : _("Save"),
                'back' : _("Back"),
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
        self.pageTitle = _("Hardware Setup")
        super(PageSetupHw, self).__init__(display)
        self.items.update({
                'label1g1' : _("Fan check"),
                'label1g2' : _("Cover check"),
                'label1g3' : _("MC version check"),
                'label1g4' : _("Use resin sensor"),

                'label2g1' : _("Screw (mm/rot)"),
                'label2g2' : _("Tilt msteps"),
                'label2g3' : _("Calib. tower offset [mm]"),
                'label2g8' : _("MC board version"),
                })
    #enddef


    def show(self):
        self.temp['screwmm'] = self.display.hwConfig.screwMm
        self.temp['tiltheight'] = self.display.hwConfig.tiltHeight
        self.temp['calibtoweroffset'] = self.display.hwConfig.calibTowerOffset
        self.temp['mcboardversion'] = self.display.hwConfig.MCBoardVersion

        self.items['value2g1'] = str(self.temp['screwmm'])
        self.items['value2g2'] = str(self.temp['tiltheight'])
        self.items['value2g3'] = self._strOffset(self.temp['calibtoweroffset'])
        self.items['value2g8'] = str(self.temp['mcboardversion'])

        self.temp['fancheck'] = self.display.hwConfig.fanCheck
        self.temp['covercheck'] = self.display.hwConfig.coverCheck
        self.temp['mcversioncheck'] = self.display.hwConfig.MCversionCheck
        self.temp['resinsensor'] = self.display.hwConfig.resinSensor

        self.items['state1g1'] = int(self.temp['fancheck'])
        self.items['state1g2'] = int(self.temp['covercheck'])
        self.items['state1g3'] = int(self.temp['mcversioncheck'])
        self.items['state1g4'] = int(self.temp['resinsensor'])

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


    def minus2g3Button(self):
        self._value(2, 'calibtoweroffset', -400, 400, -1, self._strOffset)
    #enddef


    def plus2g3Button(self):
        self._value(2, 'calibtoweroffset', -400, 400, 1, self._strOffset)
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
        self.pageTitle = _("Exposure Setup")
        super(PageSetupExposure, self).__init__(display)
        self.items.update({
                'label1g1' : _("Blink exposure"),
                'label1g2' : _("Per-Partes expos."),
                'label1g3' : _("Use tilt"),

                'label2g1' : _("Warm up mins"),
                'label2g2' : _("Layer trigger [s]"),
                'label2g3' : _("Limit for fast tilt [%]"),
                'label2g4' : _("Layer tower hop [mm]"),
                'label2g5' : _("Delay before expos. [s]"),
                'label2g6' : _("Delay after expos. [s]"),
                'label2g7' : _("Up&down wait [s]"),
                'label2g8' : _("Up&down every n-th l."),
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
        self.items['value2g2'] = self._strTenth(self.temp['trigger'])
        self.items['value2g3'] = str(self.temp['limit4fast'])
        self.items['value2g4'] = self._strZHop(self.temp['layertowerhop'])
        self.items['value2g5'] = self._strTenth(self.temp['delaybeforeexposure'])
        self.items['value2g6'] = self._strTenth(self.temp['delayafterexposure'])
        self.items['value2g7'] = str(self.temp['upanddownwait'])
        self.items['value2g8'] = str(self.temp['upanddowneverylayer'])

        self.temp['blinkexposure'] = self.display.hwConfig.blinkExposure
        self.temp['perpartesexposure'] = self.display.hwConfig.perPartes
        self.temp['tilt'] = self.display.hwConfig.tilt

        self.items['state1g1'] = int(self.temp['blinkexposure'])
        self.items['state1g2'] = int(self.temp['perpartesexposure'])
        self.items['state1g3'] = int(self.temp['tilt'])

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
            self.showItems(**{ 'value2g4' : self._strZHop(self.temp['layertowerhop']) })
        #endif
    #enddef


    def minus2g1Button(self):
        self._value(0, 'warmup', 0, 30, -1)
    #enddef


    def plus2g1Button(self):
        self._value(0, 'warmup', 0, 30, 1)
    #enddef


    def minus2g2Button(self):
        self._value(1, 'trigger', 0, 20, -1, self._strTenth)
    #enddef


    def plus2g2Button(self):
        self._value(1, 'trigger', 0, 20, 1, self._strTenth)
    #enddef


    def minus2g3Button(self):
        self._value(2, 'limit4fast', 0, 100, -1)
    #enddef


    def plus2g3Button(self):
        self._value(2, 'limit4fast', 0, 100, 1)
    #enddef


    def minus2g4Button(self):
        self._value(3, 'layertowerhop', 0, 8000, -20, self._strZHop)
        if not self.temp['tilt'] and not self.temp['layertowerhop']:
            self.temp['tilt'] = True
            self.changed['tilt'] = "on"
            self.showItems(**{ 'state1g3' : 1 })
        #endif
    #enddef


    def plus2g4Button(self):
        self._value(3, 'layertowerhop', 0, 8000, 20, self._strZHop)
    #enddef


    def minus2g5Button(self):
        self._value(4, 'delaybeforeexposure', 0, 300, -1, self._strTenth)
    #enddef


    def plus2g5Button(self):
        self._value(4, 'delaybeforeexposure', 0, 300, 1, self._strTenth)
    #enddef


    def minus2g6Button(self):
        self._value(5, 'delayafterexposure', 0, 300, -1, self._strTenth)
    #enddef


    def plus2g6Button(self):
        self._value(5, 'delayafterexposure', 0, 300, 1, self._strTenth)
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
        self.pageTitle = _("System Fatal Error")
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
        self.pageTitle = _("Tower Move")
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


class PageTiltMove(MovePage):

    def __init__(self, display):
        self.pageUI = "tiltmove"
        self.pageTitle = _("Tilt Move")
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
        self.pageTitle = _("Calibration")
        super(PageCalibration, self).__init__(display)
        self.stack = False
    #enddef


    def prepare(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = _("Printer homing"),
            line2 = _("Please wait..."))
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
            text = _("Insert the platfom and secure it with black knob."))
        return "confirm"
    #enddef


    def recalibrateStep2(self):
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep3,
            backFce = self.prepare,
            imageName = "01_loosen_screws.jpg",
            text = _("Loosen small screws on the cantilever. Be careful not to unscrew them completely."))
        return "confirm"
    #enddef


    def recalibrateStep3(self):
        self.display.page_confirm.setParams(
            continueFce = self.recalibrateStep4,
            backFce = self.recalibrateStep2,
            imageName = "02_place_bed.jpg",
            text = _("Unscrew the tank and turn it 90 degrees on the base so it lies across tilt."))
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
            backFce = self.recalibrateStep3,
            imageName = "03_proper_aligment.jpg",
            text = _("In next step move tilt up until the tank gets lifted. Resin tank needs be in direct contact with tilt, but still lie flat on printer."))
        return "confirm"
    #enddef


    def recalibrateStep5(self):
        return "tiltcalib"
    #endef

#endclass


class PageTiltCalib(MovePage):

    def __init__(self, display):
        self.pageUI = "tiltmovecalibration"
        self.pageTitle = _("Tank Calibration")
        super(PageTiltCalib, self).__init__(display)
        self.stack = False
        self.autorepeat = { "upslow" : (3, 1), "downslow" : (3, 1) }
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
            continueFce = self.tiltCalibStep2,
            backFce = self.tiltCalibAgain,
            imageName = "08_clean.jpg",
            text = _("Make sure the platform, tank and tilt are PERFECTLY clean."))
        return "confirm"
    #endif


    def backButtonRelease(self):
        return "calibration"
    #enddef


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


    def tiltCalibAgain(self):
        return "tiltcalib"
    #enddef


    def tiltCalibStep2(self):
        self.display.page_confirm.setParams(
            continueFce = self.tiltCalibStep3,
            backFce = self.okButtonRelease,
            imageName = "04_tighten_screws.jpg",
            text = _("Screw down the tank. Make sure you tighten both screws evenly."))
        return "confirm"
    #enddef


    def tiltCalibStep3(self):
        self.display.page_confirm.setParams(
            continueFce = self.tiltCalibStep4,
            backFce = self.tiltCalibStep2,
            imageName = "06_tighten_knob.jpg",
            text = _("Check if the platform is properly secured with black knob."))
        return "confirm"
    #enddef


    def tiltCalibStep4(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = _("Platform calibration"),
            line2 = _("Keep it as horizontal as possible!"))
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
                text = _("""Tower not at expected position.

Is the platform and tank secured on position?

Click continue and read the instructions carefully."""))
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
                text = _("""Tower not at expected position.

Is the platform and tank secured on position?

Click continue and read the instructions carefully."""))
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
            continueFce = self.tiltCalibStep5,
            backFce = self.tiltCalibStep3,
            imageName = "05_align_platform.jpg",
            text = _("Turn the platform to align it with exposition display."))
        return "confirm"
    #enddef


    def tiltCalibStep5(self):
        self.display.page_confirm.setParams(
            continueFce = self.tiltCalibStep6,
            backFce = self.tiltCalibStep4,
            imageName = "07_tighten_screws.jpg",
            text = _("Tighten small screws on the cantilever little by little. Be careful to tighten them evenly as much as possible."))
        return "confirm"
    #enddef


    def tiltCalibStep6(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Please wait..."))
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
            continueFce = self.tiltCalibStep7,
            backFce = self.tiltCalibStep5,
            text = _("All done, happy printing!"))
        return "confirm"
    #enddef


    def tiltCalibStep7(self):
        return "_BACK_"
    #enddef
#endclass

class PageTowerOffset(MovePage):

    def __init__(self, display):
        self.pageUI = "towermovecalibration"
        self.pageTitle = _("Tower Offset")
        super(PageTowerOffset, self).__init__(display)
        self.stack = False
        self.autorepeat = { "upslow" : (3, 1), "downslow" : (3, 1) }
    #enddef


    def show(self):
        self.tmpTowerOffset = self.display.hwConfig.calibTowerOffset
        self.items["value"] = self._strOffset(self.tmpTowerOffset)
        super(PageTowerOffset, self).show()
    #enddef


    def _value(self, change):
        if -400 <= self.tmpTowerOffset + change <= 400:
            self.tmpTowerOffset += change
            self.showItems(**{ 'value' : self._strOffset(self.tmpTowerOffset) })
        else:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def upslowButton(self):
        self._value(1)
    #enddef


    def upslowButtonRelease(self):
        pass
    #enddef


    def downslowButton(self):
        self._value(-1)
    #enddef


    def downslowButtonRelease(self):
        pass
    #enddef


    def okButtonRelease(self):
        self.display.hwConfig.calibTowerOffset = self.tmpTowerOffset
        self.display.hwConfig.update(calibtoweroffset = self.display.hwConfig.calibTowerOffset)
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        return "_BACK_"
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

                "button1" : _("Export"),
                "button2" : _("Import"),
                "button3" : _("Test"),
                "button4" : _("Save"),
                "back" : _("Back"),
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
        self.pageTitle = _("Tilt Profiles")
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
        self.pageTitle = _("Tower Profiles")
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
        self.pageTitle = _("Fans & LEDs")
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
                'label1g1' : _("UV LED fan"),
                'label1g2' : _("Blower fan"),
                'label1g3' : _("Rear fan"),
                'label1g5' : _("UV LED"),
                'label1g7' : _("Trigger"),

                'label2g1' : _("UV LED fan PWM"),
                'label2g2' : _("Blower fan PWM"),
                'label2g3' : _("Rear fan PWM"),
                'label2g5' : _("UV current [mA]"),
                'label2g6' : _("Power LED PWM"),
                'label2g7' : _("Power LED mode"),
                'label2g8' : _("Power LED speed"),

                'button4' : _("Save"),
                'back' : _("Back"),
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


class PageFeedMe(Page):

    def __init__(self, display, expo):
        self.pageUI = "feedme"
        self.pageTitle = _("Feed me")
        super(PageFeedMe, self).__init__(display)
        self.expo = expo
        self.items.update({
            'text' : _("Fill the tank and press back."),
            })
    #enddef


    def show(self):
        super(PageFeedMe, self).show()
        self.display.hw.powerLed("error")
    #enddef


    def backButtonRelease(self):
        self.display.hw.powerLed("normal")
        self.expo.doContinue()
        return super(PageFeedMe, self).backButtonRelease()
    #enddef


    def refilledButtonRelease(self):
        self.display.hw.powerLed("normal")
        self.expo.setResinVolume(defines.resinFilled)
        self.expo.doContinue()
        return super(PageFeedMe, self).backButtonRelease()
    #enddef

#endclass


class PageTuneTilt(ProfilesPage):

    def __init__(self, display):
        self.profilesFilename = "tilt_tune_profiles.json"
        self.profilesNames = display.hw.getTiltProfilesNames()
        self.pageTitle = _("Tilt Tune")
        super(PageTuneTilt, self).__init__(display, items = {
                "label1g1" : _("Down slow"),
                "label1g2" : _("Down fast"),
                "label1g3" : _("Up"),

                "label2g1" : _("init profile"),
                "label2g2" : _("offset steps"),
                "label2g3" : _("offset delay [ms]"),
                "label2g4" : _("finish profile"),
                "label2g5" : _("tilt cycles"),
                "label2g6" : _("tilt delay [ms]"),
                "label2g7" : _("homing tolerance"),
                "label2g8" : _("homing cycles"),

                "button1" : _("Export"),
                "button2" : _("Import"),
                "button4" : _("Save"),
                "back" : _("Back"),
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
        self.pageTitle = _("Image")
        self.path = None
        super(PageImage, self).__init__(display)
    #enddef

#endclass


class PageVideo(PageMedia):

    def __init__(self, display):
        self.pageUI = "video"
        self.pageTitle = _("Video")
        self.path = None
        super(PageVideo, self).__init__(display)
    #enddef

#endclass


class PageSetApikey(Page):

    def __init__(self, display):
        self.pageUI = "setapikey"
        self.pageTitle = _("Set API-key")
        super(PageSetApikey, self).__init__(display)
    #enddef

    def fillData(self):
        return {
            'api_key': self.octoprintAuth
        }
    #enddef

    def show(self):
        self.items.update(self.fillData())
        super(PageSetApikey, self).show()
    #enddef

    def setapikeyButtonSubmit(self, data):
        apikey = data['api_key']

        try:
            subprocess.check_call(["/bin/api-keygen.sh", apikey])
        except subprocess.CalledProcessError as e:
            self.display.page_error.setParams(
                text = _("Octoprint apikey change failed"))
            return "error"

        return "_BACK_"
    #enddef

#endclass


class PageWizard(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Printer Setup")
        super(PageWizard, self).__init__(display)
        self.stack = False
    #enddef


    def prepare(self):
        self.display.page_confirm.setParams(
            continueFce = self.wizardStep1,
            text = _("""Welcome to initial wizard.

This procedure will check and set up all features.

Continue?"""))
        return "confirm"
    #enddef


    def wizardStep1(self):
        self.display.hwConfig.fanCheck = False
        self.display.hw.uvLed(False)
        self.display.hw.powerLed("warn")
        homeStatus = 0

        #tilt home check
        pageWait = PageWait(self.display,
            line1 = _("Tilt home check"),
            line2 = _("Please wait..."))
        pageWait.show()
        for i in xrange(3):
            self.display.hw.mcc.do("!tiho")
            while self.display.hw.mcc.doGetInt("?tiho") > 0:
                sleep(0.25)
            #endwhile
            homeStatus = self.display.hw.mcc.doGetInt("?tiho")
            if homeStatus == -2:
                self.display.page_error.setParams(
                    text = _("""Tilt endstop not reached!

Please check if tilt motor and optical endstop are connected properly."""))
                self.display.hw.motorsRelease()
                return "error"
            elif homeStatus == 0:
                self.display.hw.tiltHomeCalibrateWait()
                self.display.hw.setTiltPosition(0)
                break
            #endif
        #endfor
        if homeStatus == -3:
            self.display.page_error.setParams(
                text = ("""Tilt home check failed!

Please contact support.

Tilt profiles needs to be changed."""))
            self.display.hw.motorsRelease()
            return "error"
        #endif

        #tilt length measure
        pageWait.showItems(line1 = _("Tilt axis check"))
        self.display.hw.setTiltProfile("homingFast")
        self.display.hw.tiltMoveAbsolute(self.display.hw._tiltEnd)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.tiltMoveAbsolute(self.display.hw._tiltMin)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        #MC moves tilt by 256 steps forward in last step of !tiho
        if self.display.hw.getTiltPosition() < -256  or self.display.hw.getTiltPosition() > 0:
            self.display.page_error.setParams(
                text = _("""Tilt axis check failed!

Current position: %d

Please check if tilting mechanism can move smoothly in whole range.""")) % self.display.hw.getTiltPosition()
	    self.display.hw.motorsRelease()
            return "error"
        #endif
        self.display.hw.tiltMoveAbsolute(defines.defaultTiltHeight)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile

        #tower home check
        pageWait.showItems(line1 = _("Tower home check"))
        for i in xrange(3):
            self.display.hw.mcc.do("!twho")
            while self.display.hw.mcc.doGetInt("?twho") > 0:
                sleep(0.25)
            #endwhile
            homeStatus = self.display.hw.mcc.doGetInt("?twho")
            if homeStatus == -2:
                self.display.page_error.setParams(
                    text = _("""Tower endstop not reached!

Please check if tower motor is connected properly."""))
                self.display.hw.motorsRelease()
                return "error"
            elif homeStatus == 0:
                self.display.hw.towerHomeCalibrateWait()
                self.display.hw.setTowerPosition(self.display.hw._towerEnd)
                break
            #endif
        #endfor
        if homeStatus == -3:
            self.display.page_error.setParams(
                text = _("""Tower home check failed!

Please contact support.

Tower profiles needs to be changed."""))
            self.display.hw.motorsRelease()
            return "error"
        #endif
        self.display.hw.powerLed("normal")
        self.display.page_confirm.setParams(
            continueFce=self.wizardStep2,
            text = _("""Screw down the resin tank and remove platform.

Make sure the tank is empty and clean."""))
        return "confirm"

    #enddef


    def wizardStep2(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = _("Tower axis check"),
            line2 = _("Please wait..."))
        pageWait.show()
        self.display.hw.setTowerProfile("homingFast")
        self.display.hw.towerMoveAbsolute(0)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        #stop 10 mm before endstop to change sensitive profile
        self.display.hw.towerMoveAbsolute(self.display.hw._towerEnd - 8000)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.setTowerProfile("homingSlow")
        self.display.hw.towerMoveAbsolute(self.display.hw._towerMax)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        position = self.display.hw.getTowerPositionMicroSteps()
        #MC moves tower by 1024 steps forward in last step of !twho
        if position < self.display.hw._towerEnd or position > self.display.hw._towerEnd + 1024 + 127: #add tolerance half fullstep
            self.display.page_error.setParams(
                text = _("""Tower axis check failed!

Current position: %d

Please check if ballscrew can move smoothly in whole range.""") % position)
            self.display.hw.motorsRelease()
            return "error"
        #endif

        #fan check
        self.display.hw.uvLed(False)
        pageWait.showItems(line1 = _("Fan check"))
        self.display.hwConfig.fanCheck = False
        self.display.hw.setFansPwm((0, 0, 0))
        self.display.hw.setFans((True, True, True))
        sleep(6)    #wait for fans to stop
        rpm = self.display.hw.getFansRpm()
        if rpm[0] != 0 or rpm[1] != 0 or rpm[2] != 0:
            self.display.page_error.setParams(
                text = _("""RPM detected even when fans are off.

Check if all fans are properly connected.

RPM data: %s""")) % rpm
            return "error"
        #endif
                        #fan1        fan2        fan3
        fanLimits = [[50,150], [1200, 1500], [150, 300]]
        hwConfig = libConfig.HwConfig()
        self.display.hw.setFansPwm((hwConfig.fan1Pwm, hwConfig.fan2Pwm, hwConfig.fan3Pwm))   #use default PWM. TODO measure fans in range of values
        sleep(6)    #let the fans spin up
        rpm = self.display.hw.getFansRpm()
        for i in xrange(3):
            if not fanLimits[i][0] <= rpm[i] <= fanLimits[i][1]:
                if i == 0:
                    fanName = _("UV LED")
                elif i == 1:
                    fanName = _("blower")
                else:
                    fanName = _("rear")
                #endif
                self.display.page_error.setParams(
                    text = _("""RPM of %(fan)s fan not in range!

Please check if the fan is connected correctly.

RPM data: %(rpm)s""") % { 'fan' : fanName, 'rpm' : rpm })
                self.display.hw.setFansPwm((0, 0, 0))
                return "error"
            #endif
        #endfor
        self.display.hwConfig.fanCheck = True

        #temperature check
        pageWait.showItems(line1 = _("Temperature check"))
        temperatures = self.display.hw.getMcTemperatures()
        for i in xrange(2):
            if not self.display.hw._minAmbientTemp < temperatures[i] < self.display.hw._maxAmbientTemp:
                if i == 0:
                    sensorName = _("UV LED")
                else:
                    sensorName = _("Ambient")
                #endif
                self.display.page_error.setParams(
                    text = _(u"""%(sensor)s temperature not in range!

Please check if temperature sensors are connected correctly. Keep printer at room temperature (15 - 35 °C).

Measured: %(temp).1f""") % { 'sensor' : sensorName, 'temp' : temperatures[i] })
                return "error"
            #endif
        #endfor
        if abs(temperatures[0] - temperatures[1]) > self.display.hw._maxTempDiff:
            self.display.page_error.setParams(
                text = _(u"""Measured temperatures differ too much!

Please check if temperature sensor are connected correctly. Keep printer at room temperature (15 - 35 °C).

Data: %(first).1f, %(second).1f""") % { 'first' : temperatures[0], 'second' : temperatures[1] })
            return "error"
        #endif
        if self.display.hw.getCpuTemperature() > self.display.hw._maxA64Temp:
            self.display.page_error.setParams(
                text = _("""A64 temperature is too high (%.1f)!

Shutting down in 10 seconds...""") % self.display.hw.getCpuTemperature())
            sleep(10)
            self.display.shutDown(True)
            return "error"
        #endif
        self.display.hw.powerLed("normal")
        self.display.page_confirm.setParams(
            continueFce = self.wizardStep3,
            text = _("""Please close the orange cover.

Make sure the tank is empty and clean."""))
        return "confirm"
    #enddef


    def wizardStep3(self):
        self.display.hw.powerLed("warn")
        if not self.display.hw.isCoverClosed():
            self.display.page_error.setParams(
                text = _("""Orange cover not closed!

Please check the connection of cover switch."""))
            self.display.hw.uvLed(False)
            return "error"
        #endif

        # UV LED VA
        pageWait = PageWait(self.display,
            line1 = _("UV LED check"),
            line2 = _("Please wait..."))
        pageWait.show()
        self.display.hw.setUvLedCurrent(0)
        self.display.hw.uvLed(True)
        uvCurrents = [0, 300, 600]
        # PWM            0           300         600
        uv1Limit = [[14.0,17.4],[15.6,18.8],[16.1,19.5]]     #uv led 1st row voltage limits
        uv2Limit = [[13.8,14.7],[15.1,16.7],[15.9,17.7]]     #uv led 2nd row voltage limits
        uv3Limit = [[13.8,14.1],[14.8,16.2],[15.8,16.9]]     #uv led 3rd row voltage limits
        for i in xrange(3):
            self.display.hw.setUvLedCurrent(uvCurrents[i])
            sleep(3)
            voltages = self.display.hw.getVoltages()
            if not (uv1Limit[i][0] < voltages[0] < uv1Limit[i][1] or uv2Limit[i][0] < voltages[1] < uv2Limit[i][1] or uv3Limit[i][0] < voltages[2] < uv3Limit[i][1]):
                self.display.page_error.setParams(
                    text = _("""UV LED current out of range!

Please check if UV LED panel is connected propely.

Voltage data: %(row)d, %(value)s""") % { 'row' : i, 'value' : voltages})
                self.display.hw.uvLed(False)
                return "error"
            #endif
        #endfor

        # UV LED temperature check
        pageWait.showItems(line1 = _("UV LED warmup check"))
        self.display.hw.setUvLedCurrent(700)
        for countdown in xrange(120, 0, -1):
            pageWait.showItems(line2 = _("Please wait %d s") % countdown)
            sleep(1)
            temps = self.display.hw.getMcTemperatures()
            if temps[self.display.hw._ledTempIdx] > self.display.hw._maxUVTemp:
                self.display.page_error.setParams(
                    text = _("""UV LED too hot!

Please check if UV LED panel is connected propely with heatsing.

Temperature data: %s""") % temps)
                self.display.hw.uvLed(False)
                return "error"
            #endif
        #endfor
        self.display.hw.setUvLedCurrent(self.display.hwConfig.uvCurrent)
        self.display.hw.powerLed("normal")

        #exposure display check
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "logo_1440x2560.png"))
        self.display.page_confirm.setParams(
            continueFce = self.wizardStep4,
            text = _("""Can you see company logo on the exposure display through orange cover?

DO NOT open the cover."""))
        return "confirm"
    #enddef


    def wizardStep4(self):
        self.display.screen.getImgBlack()
        self.display.hw.uvLed(False)
        self.display.page_confirm.setParams(
            continueFce = self.wizardStep5,
            text = _("Leave resin tank screwed in place and insert platform in 60 degree angle."))
        return "confirm"
    #enddef


    def wizardStep5(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = _("Resin sensor check"),
            line2 = _("Please wait..."),
            line3 = _("DO NOT touch the printer"))
        pageWait.show()
        self.display.hw.towerSync()
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        self.display.hw.setTowerPosition(self.display.hwConfig.calcMicroSteps(defines.defaultTowerHeight))
        volume = self.display.hw.getResinVolume()
        if not 110 <= volume <= 190:    #to work properly even with loosen rocker brearing
            self.display.page_error.setParams(
                text = _("""Resin sensor not working properly!

Please check if sensor is properly connected.

Measured %d ml.""") % volume)
            self.display.hw.motorsRelease()
            return "error"
        #endif
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait()
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        self.display.hwConfig.update(showwizard = "no")
        if not self.display.hwConfig.writeFile():
            self.display.hw.beepAlarm(3)
            sleep(1)
            self.display.hw.beepAlarm(3)
        #endif
        self.display.page_confirm.setParams(
            continueFce = self.wizardStep6,
            text = _("""Printer is succesfully checked.

Continue to calibration?"""))
        return "confirm"
    #enddef


    def wizardStep6(self):
        return "calibration"
    #enddef

#endclass
