# part of SL1 firmware
# -*- coding: utf-8 -*-
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from time import time, sleep
from datetime import datetime
import json
import toml
import subprocess
import signal
import glob
import pydbus
from copy import deepcopy
import re
import urllib2
import tarfile
import zipfile
import shutil
import paho.mqtt.publish as mqtt

import defines
import libConfig


class Page(object):

    def __init__(self, display):
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.autorepeat = {}
        self.stack = True
        self.fill()

        self.updateDataPeriod = None

        # callback options
        self.callbackPeriod = 0.5
        self.checkPowerbutton = True
        self.checkCover = False
        self.checkCoverOveride = False   # to force off when exposure is in progress
        self.checkCooling = False

        # vars for checkCoverCallback()
        self.checkCoverBeepDelay = 2
        self.checkCoverWarnOnly = True
        self.checkCoverUVOn = False
        # vars for powerButtonCallback()
        self.powerButtonCount = 0
        # vars for checkCoolingCallback()
        self.checkCooligSkip = 20   # 10 sec
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
                'image_version' : self.display.hwConfig.os.versionId,
                'page_title' : self.pageTitle,
                }
    #enddef


    def prepare(self):
        pass
    #enddef


    def leave(self, newPage):
        '''Override this to modify page this page is left for. This is used to show confirm page instead and return to
        newPage later.'''
        return newPage
    #enddef


    def show(self):
        # renew save path every time when page is shown, it may change
        self.items['save_path'] = self.getSavePath()
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
                checkPowerbutton = False,
                text = _("Do you really want to turn off the printer?"))
        return "confirm"
    #enddef


    def turnoffContinue(self):
        self.display.shutDown(True)
    #enddef


    def netChange(self):
        pass
    #enddef


    # Dynamic USB path, first usb device or None
    def getSavePath(self):
        usbs = glob.glob(os.path.join(defines.mediaRootPath, '*'))

        if len(usbs) > 0 and os.path.ismount(usbs[0]):
            return usbs[0]
        else:
            self.logger.debug("getSavePath returning None, no media seems present")
            return None
        #endif
    #enddef


    def downloadURL(self, url, dest, title=None, timeout_sec=10):
        """Fetches file specified by url info destination while displaying progress. This is implemented as chunked
        copy from source file descriptor to the deestination file descriptor. The progress is updated once the cunk is
        copied. The source file descriptor is either standard file when the source is mounted USB drive or urlopen
        result."""

        if not title:
            title = _("Fetching")
        #endif
        pageWait = PageWait(self.display, line1=title, line2="0%")
        pageWait.show()

        self.logger.info("Downloading %s" % url)

        if url.startswith("http://") or url.startswith("https://"):
            # URL is HTTP, source is url
            req = urllib2.Request(url)
            req.add_header('User-Agent', 'Prusa-SL1')
            req.add_header('Prusa-SL1-version', self.display.hwConfig.os.versionId)
            req.add_header('Prusa-SL1-serial', self.display.hw.cpuSerialNo)
            source = urllib2.urlopen(req, timeout=timeout_sec)
            try:
                file_size = int(source.info().getheaders("Content-Length")[0])
            except:
                file_size = 1
            block_size = 8 * 1024
        else:
            # URL is file, source is file
            self.logger.info("Copying firmware %s" % url)
            source = open(url, "rb")
            file_size = os.path.getsize(url)
            block_size = 1024 * 1024
        #endif

        with open(dest, 'wb') as file:
            old_progress = 0
            while True:
                buffer = source.read(block_size)
                if not buffer or buffer == '':
                    break
                #endif
                file.write(buffer)

                progress = int(100 * file.tell() / file_size)
                if progress != old_progress:
                    pageWait.showItems(line2="%d%%" % progress)
                    old_progress = progress
                #endif
            #endwhile
        #endwith

        source.close()
    #enddef


    def ensureCoverIsClosed(self):
        if not self.display.hwConfig.coverCheck or self.display.hw.isCoverClosed():
            return
        #endif
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
                line1 = _("Close the orange cover."),
                line2 = _("If the cover is closed, please check the connection of the cover switch."))
        pageWait.show()
        self.display.hw.beepAlarm(3)
        #endif
        while not self.display.hw.isCoverClosed():
            sleep(0.5)
        #endwhile
        self.display.hw.powerLed("normal")
    #enddef


    def saveLogsToUSB(self):
        save_path = self.getSavePath()
        if save_path is None:
            self.display.page_error.setParams(text=_("No USB storage present"))
            return "error"
        #endif

        pageWait = PageWait(self.display, line1=_("Saving logs"))
        pageWait.show()

        timestamp = str(int(time()))
        serial = self.display.hw.cpuSerialNo
        log_file = os.path.join(save_path, "log.%s.%s.txt.gz" % (serial, timestamp))

        try:
            subprocess.check_call(
                ["/bin/sh", "-c", "journalctl | gzip > %s; sync" % log_file])
        except subprocess.CalledProcessError as e:
            self.display.page_error.setParams(text=_("Log save failed"))
            return "error"
        #endexcept

        return "_BACK_"
    #enddef


    def _onOff(self, index, val):
        if isinstance(self.temp[val], libConfig.MyBool):
            self.temp[val].inverse()
        else:
            self.temp[val] = not self.temp[val]
        #endif
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
            if isinstance(value, bool):
                items[index] = int(value)
            elif isinstance(value, dict):
                items[index] = value
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

Check the printer's hardware."""))
            return "error"
        #endif
        return "_SELF_"
    #enddef


    def _syncTilt(self):
        if not self.display.hw.tiltSyncWait(retries = 2):
            self.display.page_error.setParams(
                    text = _("""Tilt homing failed!

Check the printer's hardware."""))
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


    def countRemainTime(self, actualLayer, slowLayers):
        config = self.display.config
        hwConfig = self.display.hwConfig
        timeRemain = 0
        fastLayers = config.totalLayers - actualLayer - slowLayers
        # first 3 layers with expTimeFirst
        long1 = 3 - actualLayer
        if long1 > 0:
            timeRemain += long1 * (config.expTimeFirst - config.expTime)
            self.logger.debug("long1: %d  timeRemain: %f", long1, timeRemain)
        #endif
        # fade layers (approx)
        long2 = config.fadeLayers + 3 - actualLayer
        if long2 > 0:
            timeRemain += long2 * ((config.expTimeFirst - config.expTime) / 2 - config.expTime)
            self.logger.debug("long2: %d  timeRemain: %f", long2, timeRemain)
        #endif
        timeRemain += fastLayers * hwConfig.tiltFastTime
        self.logger.debug("fastLayers: %d  timeRemain: %f", fastLayers, timeRemain)
        timeRemain += slowLayers * hwConfig.tiltSlowTime
        self.logger.debug("slowLayers: %d  timeRemain: %f", slowLayers, timeRemain)
        # FIXME slice2 and slice3
        timeRemain += (fastLayers + slowLayers) * (
                config.calibrateRegions * config.calibrateTime
                + config.expTime
                + hwConfig.delayBeforeExposure
                + hwConfig.delayAfterExposure)
        self.logger.debug("timeRemain: %f", timeRemain)
        return int(round(timeRemain / 60))
    #enddef


    def callback(self):

        state = False
        if self.checkPowerbutton:
            state = True
            retc = self.powerButtonCallback()
            if retc:
                return retc
            #endif
        #endif

        expoInProgress = self.display.expo.inProgress()

        if not self.checkCoverOveride and (self.checkCover or expoInProgress):
            state = True
            retc = self.checkCoverCallback()
            if retc:
                return retc
            #endif
        #endif

        if self.checkCooling or (expoInProgress and self.display.checkCoolingExpo):
            state = True
            retc = self.checkCoolingCallback(expoInProgress)
            if retc:
                return retc
            #endif
        #endif

        if not state:
            # just read status from the MC to prevent the power LED pulsing
            self.display.hw.getPowerswitchState()
        #endif
    #enddef


    def powerButtonCallback(self):
        if not self.display.hw.getPowerswitchState():
            if self.powerButtonCount:
                self.powerButtonCount = 0
                self.display.hw.powerLed("normal")
            #endif
            return
        #endif

        if self.powerButtonCount > 3:
            self.display.hw.powerLed("normal")
            self.display.hw.beepEcho()
            return self.turnoffButtonRelease()
        #endif

        if not self.powerButtonCount:
            self.display.hw.powerLed("off")
            self.display.hw.beepEcho()
        #endif

        self.powerButtonCount += 1
    #enddef


    def checkCoverCallback(self):
        if not self.display.hwConfig.coverCheck or self.display.hw.isCoverClosed():
            self.checkCoverBeepDelay = 2
            return
        #endif

        if self.checkCoverWarnOnly:
            if self.checkCoverBeepDelay > 1:
                self.display.hw.beepAlarm(2)
                self.checkCoverBeepDelay = 0
            else:
                self.checkCoverBeepDelay += 1
            #endif
        else:
            self.display.hw.uvLed(False)
            self.display.hw.powerLed("warn")
            pageWait = PageWait(self.display, line1 = _("Close the orange cover."))
            pageWait.show()
            self.display.hw.beepAlarm(3)
            while not self.display.hw.isCoverClosed():
                sleep(0.5)
            #endwhile
            self.display.hw.powerLed("normal")
            self.show()
            if self.checkCoverUVOn:
                self.display.hw.uvLed(True)
            #endif
        #endif
    #enddef


    def checkCoolingCallback(self, expoInProgress):
        if self.checkCooligSkip < 20:
            self.checkCooligSkip += 1
            return
        #endif
        self.checkCooligSkip = 0

        # UV LED temperature test
        temp = self.display.hw.getUvLedTemperature()
        if temp < 0:
            if expoInProgress:
                self.display.expo.doPause()
                self.display.checkCoolingExpo = False
                backFce = self.exitPrint
                addText = _("Actual job will be canceled.")
            else:
                self.display.hw.uvLed(False)
                backFce = self.backButtonRelease
                addText = ""
            #endif

            self.display.page_error.setParams(
                    backFce = backFce,
                    text = _("""Reading of UV LED temperature has failed!

This value is essential for the UV LED lifespan and printer safety.

Please contact tech support!

%s""") % addText)
            return "error"
        #endif

        if temp > self.display.hw._maxUVTemp:
            if expoInProgress:
                self.display.expo.doPause()
            else:
                self.display.hw.uvLed(False)
            #enddef
            self.display.hw.powerLed("error")
            pageWait = PageWait(self.display, line1 = _("UV LED OVERHEAT!"), line2 = _("Cooling down..."))
            pageWait.show()
            self.display.hw.beepAlarm(3)
            while(temp > self.display.hw._maxUVTemp - 10): # hystereze
                pageWait.showItems(line3 = _("Temperature is %.1f C") % temp)
                sleep(10)
                temp = self.display.hw.getUvLedTemperature()
            #endwhile
            self.display.hw.powerLed("normal")
            self.show()
            if expoInProgress:
                self.display.expo.doContinue()
            #enddef
        #endif

        # fans test
        if not self.display.hwConfig.fanCheck or self.display.fanErrorOverride:
            return
        #endif

        fansState = self.display.hw.getFansError()
        if any(fansState):
            failedFans = []
            for num, state in enumerate(fansState):
                if state:
                    failedFans.append(self.display.hw.getFanName(num))
                #endif
            #endfor

            self.display.fanErrorOverride = True

            if expoInProgress:
                backFce = self.exitPrint
                addText = _("""Expect overheating, but the print may continue.

If you don't want to continue, please press the Back button on top of the screen and the actual job will be canceled.""")
            else:
                backFce = self.backButtonRelease
                addText = ""
            #endif

            self.display.page_confirm.setParams(
                    backFce = backFce,
                    continueFce = self.backButtonRelease,
                    beep = True,
                    text = _("""Failed: %(what)s

Please contact tech support!

%(addText)s""") % { 'what' : ", ".join(failedFans), 'addText' : addText })
            return "confirm"
        #endif
    #enddef


    def exitPrint(self):
        self.display.expo.doExitPrint()
        self.display.expo.canceled = True
        self.display.page_systemwait.fill(
            line1 = _("Job will be canceled after layer finish"))
        return "systemwait"
    #enddef


    def ramdiskCleanup(self):
        project_files = []
        for ext in defines.projectExtensions:
            project_files.extend(glob.glob(defines.ramdiskPath + "/*" + ext))
        #endfor
        for project_file in project_files:
            self.logger.debug("removing '%s'", project_file)
            try:
                os.remove(project_file)
            except Exception as e:
                self.logger.exception("ramdiskCleanup() exception:")
            #endtry
        #endfor
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
        self.beep = kwargs.pop("beep", False)
        self.checkPowerbutton = kwargs.pop("checkPowerbutton", True)
        self.fill()
        self.items.update(kwargs)
    #enddef


    def show(self):
        super(PageConfirm, self).show()
        if self.beep:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def contButtonRelease(self):
        if self.continueFce is None:
            return "_EXIT_"
        else:
            return self.continueFce(**self.continueParams)
        #endif
    #enddef


    def backButtonRelease(self):
        if self.backFce is None:
            return super(PageConfirm, self).backButtonRelease()
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
            'name' : config.projectName,
            'calibrationRegions' : calibrateRegions,
            'date' : config.modificationTime,
            'layers' : config.totalLayers,
            'layer_height_first_mm' : self.display.hwConfig.calcMM(config.layerMicroStepsFirst),
            'layer_height_mm' : self.display.hwConfig.calcMM(config.layerMicroSteps),
            'exposure_time_first_sec' : config.expTimeFirst,
            'exposure_time_sec' : config.expTime,
            'calibrate_time_sec' : calibration,
            'print_time_min' : self.countRemainTime(0, config.layersSlow),
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


    def copyAndCheckZip(self, config):
        confirm = None
        newZipName = None
        if config.zipName:
            # check free space
            statvfs = os.statvfs(defines.ramdiskPath)
            ramdiskFree = statvfs.f_frsize * statvfs.f_bavail - 10*1024*1024 # for other files
            self.logger.debug("Ramdisk free space: %d bytes" % ramdiskFree)
            try:
                filesize = os.path.getsize(config.zipName)
                self.logger.debug("Zip file size: %d bytes" % filesize)
            except Exception:
                self.logger.exception("filesize exception:")
                return (_("""Can't read from the USB drive.

Check it and try again."""), None, None)
            #endtry

            try:
                if ramdiskFree < filesize:
                    raise Exception("Not enough free space in the ramdisk!")
                #endif
                (dummy, filename) = os.path.split(config.zipName)
                newZipName = os.path.join(defines.ramdiskPath, filename)
                if os.path.normpath(newZipName) != os.path.normpath(config.zipName):
                    shutil.copyfile(config.zipName, newZipName)
                #endif
            except Exception:
                self.logger.exception("copyfile exception:")
                confirm = _("""Loading the file into the printer's memory failed.

The project will be printed from USB drive.

DO NOT remove the USB drive!""")
                newZipName = config.zipName
            #endtry
        #endif

        try:
            zf = zipfile.ZipFile(newZipName, 'r')
            badfile = zf.testzip()
            zf.close()
            if badfile is not None:
                self.logger.error("Corrupted file: %s", badfile)
                return (_("""Corrupted data detected.

Re-export the file and try again."""), None, None)
            #endif
        except Exception as e:
            self.logger.exception("zip read exception:")
            return (_("""Can't read project data.

Re-export the file and try again."""), None, None)
        #endtry

        return (None, confirm, newZipName)
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Checking temperatures"))
        pageWait.show()

        temperatures = self.display.hw.getMcTemperatures()
        for i in xrange(2):
            if temperatures[i] < 0:
                self.display.page_error.setParams(
                    backFce = self.backButtonRelease,
                    text = _("""Can't read %s

Please check if temperature sensors are connected correctly.""") % self.display.hw.getSensorName(i))
                return "error"
            #endif
        #endfor

        if temperatures[1] < self.display.hw._minAmbientTemp:
            self.display.page_confirm.setParams(
                    continueFce = self.contButtonContinue1,
                    text = _("""Ambient temperature is under recommended value.

You should heat up the resin and/or increase the exposure times.

Do you want to continue?"""))
            return "confirm"
        #endif

        if temperatures[1] > self.display.hw._maxAmbientTemp:
            self.display.page_confirm.setParams(
                    continueFce = self.contButtonContinue1,
                    text = _("""Ambient temperature is over recommended value.

You should move the printer to cooler place.

Do you want to continue?"""))
            return "confirm"
        #endif

        return self.contButtonContinue1()
    #enddef


    def contButtonContinue1(self):
        pageWait = PageWait(self.display,
                line1 = _("Checking project data..."),
                line2 = _("Setting start positions..."),
                line3 = _("Checking fans..."))
        pageWait.show()

        fanStartTime = datetime.now()
        self.display.hw.startFans()
        self.display.hw.towerSync()
        self.display.hw.tiltSync()

        # Remove old projects from ramdisk
        self.ramdiskCleanup()
        (error, confirm, zipName) = self.copyAndCheckZip(self.display.config)

        while not self.display.hw.isTowerSynced() or not self.display.hw.isTiltSynced():
            sleep(0.25)
        #endwhile

        if error:
            self.display.page_error.setParams(
                    backFce = self.backButtonRelease,
                    text = error)
            return "error"
        #endif

        pageWait.showItems(line1 = _("Project data OK"))

        if self.display.hw.towerSyncFailed():
            self.display.page_error.setParams(
                    backFce = self.backButtonRelease,
                    text = _("""Tower homing failed!

Check the printer's hardware.

The print job was canceled."""))
            return "error"
        #endif

        if self.display.hw.tiltSyncFailed():
            self.display.page_error.setParams(
                    backFce = self.backButtonRelease,
                    text = _("""Tilt homing failed!

Check the printer's hardware.

The print job was canceled."""))
            return "error"
        #endif

        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.tiltUpWait()
        pageWait.showItems(line2 = _("Start positions OK"))

        fansRunningTime = (datetime.now() - fanStartTime).total_seconds()
        if fansRunningTime < defines.fanStartStopTime:
            sleepTime = defines.fanStartStopTime - fansRunningTime
            self.logger.debug("Waiting %.2f secs for fans", sleepTime)
            sleep(sleepTime)
        #endif

        fansState = self.display.hw.getFansError()
        if any(fansState):
            failedFans = []
            for num, state in enumerate(fansState):
                if state:
                    failedFans.append(self.display.hw.getFanName(num))
                #endif
            #endfor
            self.display.page_error.setParams(
                    backFce = self.backButtonRelease,
                    text = _("""Failed: %s

Check if fans are connected properly and can rotate without resistance.""" % ", ".join(failedFans)))
            return "error"
        #endif

        pageWait.showItems(line3 = _("Fans OK"))
        self.display.fanErrorOverride = False
        self.display.checkCoolingExpo = True
        self.display.expo.setProject(zipName)

        if confirm:
            self.display.page_confirm.setParams(
                    backFce = self.backButtonRelease,
                    continueFce = self.contButtonContinue2,
                    beep = True,
                    text = confirm)
            return "confirm"
        #endif

        return self.contButtonContinue2()
    #enddef

    def contButtonContinue2(self):
        self.display.config.logAllItems()
        return "printstart"
    #enddef

    def backButtonRelease(self):
        self.display.hw.motorsRelease()
        self.display.hw.stopFans()
        self.ramdiskCleanup()
        self.display.goBack(2)
    #enddef

#endclass


class PagePrintStart(PagePrintPreviewBase):

    def __init__(self, display):
        self.pageUI = "printstart"
        self.pageTitle = _("Confirm")
        super(PagePrintStart, self).__init__(display)
    #enddef


    def show(self):
        self.percReq = self.display.hw.calcPercVolume(self.display.config.usedMaterial + defines.resinMinVolume)
        lines = {
                'name' : self.display.config.projectName,
                }
        if self.percReq <= 100:
            lines.update({
                'text' : _("Please fill the resin tank to at least %d %% and close the cover.") % self.percReq
                })
        else:
            lines.update({
                'text' : _("""Please fill the resin tank to the 100 % mark and close the cover.

Resin will have to be added during this print job."""),
                })
        self.items.update(lines)
        super(PagePrintStart, self).show()
    #enddef


    def changeButtonRelease(self):
        return "change"
    #enddef


    def backButtonRelease(self):
        self.display.hw.motorsRelease()
        self.display.hw.stopFans()
        self.ramdiskCleanup()
        self.display.goBack(3)
    #enddef


    def contButtonRelease(self):

        if not self.display.expo.loadProject():
            self.display.page_error.setParams(
                    backFce = self.backButtonRelease,
                    text = _("""Can't read data of your project.

Regenerate it and try again."""))
            return "error"
        #endif

        self.ensureCoverIsClosed()
        self.pageWait = PageWait(self.display, line1 = _("Do not open the orange cover!"))
        self.pageWait.show()

        if self.display.hwConfig.resinSensor:
            self.pageWait.showItems(line2 = _("Measuring resin volume"), line3 = _("Do NOT TOUCH the printer"))
            volume = self.display.hw.getResinVolume()
            fail = True

            if not volume:
                text = _("""Resin measuring failed!

Is there the correct amount of resin in the tank?

Is the tank secured with both screws?""")
            elif volume < defines.resinMinVolume:
                text = _("""Resin volume is too low!

Add enough resin so it reaches at least the %d %% mark and try again.""") % self.display.hw.calcPercVolume(defines.resinMinVolume)
            elif volume > defines.resinMaxVolume:
                text = _("""Resin volume is too high!

Remove some resin from the tank and try again.""")
            else:
                fail = False
            #endif

            if fail:
                self.pageWait.showItems(line1 = _("There is a problem with resin volume..."), line2 = _("Moving platform up"))
                self.display.hw.setTowerProfile('moveFast')
                self.display.hw.towerToTop()
                while not self.display.hw.isTowerOnTop():
                    sleep(0.25)
                    self.pageWait.showItems(line3 = self.display.hw.getTowerPosition())
                #endwhile
                self.display.page_error.setParams(
                        backFce = self.backButtonRelease,
                        text = text)
                return "error"
            #endif

            percMeas = self.display.hw.calcPercVolume(volume)
            self.logger.debug("requested: %d, measured: %d", self.percReq, percMeas)
            self.pageWait.showItems(line2 = _("Measured resin volume is approx. %d %%") % percMeas)
            self.display.expo.setResinVolume(volume)

            if percMeas < self.percReq:
                self.display.page_confirm.setParams(
                        backFce = self.backButtonRelease,
                        continueFce = self.contButtonContinue1,
                        beep = True,
                        text = _("""Your tank fill is approx %(measured)d %%

For your project is %(requested)d %% requested. Refill may be required during printing.""") \
                        % { 'measured' : percMeas, 'requested' : self.percReq})
                return "confirm"
            #endif
        else:
            self.pageWait.showItems(line2 = _("Resin volume measurement is turned off"))
        #endif

        return self.contButtonContinue2()
    #enddef


    def contButtonContinue1(self):
        self.pageWait.show()
        return self.contButtonContinue2()
    #enddef


    def contButtonContinue2(self):
        if self.display.hwConfig.tilt:
            self.pageWait.showItems(line3 = _("Moving tank down"))
            self.display.hw.tiltDownWait()
        #endif

        self.pageWait.showItems(line3 = _("Moving platform down"))
        self.display.hw.setTowerProfile('moveFast')
        self.display.hw.towerToPosition(0.25)
        while not self.display.hw.isTowerOnPosition():
            sleep(0.25)
        #endwhile

        if self.display.hwConfig.tilt:
            self.pageWait.showItems(line3 = _("Resin stirring"))
            self.display.hw.stirResin()
        #endif

        return "print"
    #enddef

#endclass


class PageStart(Page):

    def __init__(self, display):
        self.pageUI = "splash"
        self.pageTitle = ""
        super(PageStart, self).__init__(display)
    #enddef

#endclass


class PageHome(Page):

    def __init__(self, display):
        self.pageUI = "home"
        self.pageTitle = _("Home")
        super(PageHome, self).__init__(display)
        # meni se i z libPrinter!
        self.readyBeep = True
    #enddef


    def show(self):
        super(PageHome, self).show()
        if self.readyBeep:
            self.display.hw.beepRepeat(2)
            self.readyBeep = False
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
        return "wizard1"
    #enddef


    def printContinue(self):
        return "calibration1"
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
        pageWait = PageWait(self.display, line2 = _("Moving platform to the top"))
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
        # assume tilt is up (there may be error from print)
        self.display.hw.setTiltPosition(self.display.hw._tiltEnd)
        self.display.hw.tiltLayerDownWait(True)
        self.display.hw.tiltSyncWait()
        self.display.hw.tiltLayerUpWait()
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
        return "calibration1"
    #enddef

#endclass


class PageTimeDateBase(Page):

    def __init__(self, display):
        self._timedate = None
        super(PageTimeDateBase, self).__init__(display)
    #enddef


    @property
    def timedate(self):
        if not self._timedate:
            self._timedate = pydbus.SystemBus().get("org.freedesktop.timedate1")
        #endif
        return self._timedate
    #enddef

#endclass


class PageTimeSettings(PageTimeDateBase):

    def __init__(self, display):
        self.pageUI = "timesettings"
        self.pageTitle = _("Time Settings")
        super(PageTimeSettings, self).__init__(display)
    #enddef


    def fillData(self):
        return {
            'ntp' : self.timedate.NTP,
            'unix_timestamp_sec' : time(),
            'timezone' : self.timedate.Timezone,
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


class PageSetTimeBase(PageTimeDateBase):

    def __init__(self, display):
        super(PageSetTimeBase, self).__init__(display)
    #enddef


    def fillData(self):
        return {
            'unix_timestamp_sec' : time(),
            'timezone' : self.timedate.Timezone,
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


class PageSetTimezone(PageTimeDateBase):
    zoneinfo = "/usr/share/zoneinfo/"

    def __init__(self, display):
        self.pageUI = "settimezone"
        self.pageTitle = _("Set Timezone")

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
            'timezone' : timezone,
            'region' : region,
            'city' : city,
            'timezones' : self.timezones,
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
        self._hostname = None
        super(PageSetHostname, self).__init__(display)
    #enddef


    @property
    def hostname(self):
        if not self._hostname:
            self._hostname = pydbus.SystemBus().get("org.freedesktop.hostname1")
        #endif
        return self._hostname
    #enddef


    def fillData(self):
        return {
            'hostname' : self.hostname.StaticHostname,
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
        self._locale = None
        super(PageSetLanguage, self).__init__(display)
    #enddef


    @property
    def locale(self):
        if not self._locale:
            self._locale = pydbus.SystemBus().get("org.freedesktop.locale1")
        #endif
        return self._locale
    #enddef


    def fillData(self):
        try:
            locale = str(self.locale.Locale)
            lang = re.match(".*'LANG=(.*)'.*", locale).groups()[0]
        except:
            lang = ""

        return {
            'locale' : lang,
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


def item_updater(str_func = None):
    def new_decorator(func):
        def new_func(self, value):
            func(self, value)

            key = func.__name__
            if str_func:
                value = str_func(getattr(self, func.__name__))
            else:
                value = getattr(self, func.__name__)
            #endif

            self.showItems(**{key: value})
        #enddef
        return new_func
    #enddef
    return new_decorator
#enddef


def value_saturate(min, max):
    def new_decorator(func):
        def new_func(self, value):
            if not min <= value <= max:
                self.display.hw.beepAlarm(1)
                return
            else:
                func(self, value)
            #enddif
        #enddef
        return new_func
    #enddef
    return new_decorator
#enddef


class PageAdvancedSettings(Page):

    def __init__(self, display):
        self.pageUI = "advancedsettings"
        self.pageTitle = _("Advanced Settings")
        self._display_test = False
        self.configwrapper = None
        self._calibTowerOffset_mm = None
        self.confirmReturnPending = False
        super(PageAdvancedSettings, self).__init__(display)

        self.autorepeat = {
            'minus_tiltsensitivity': (5, 1), 'plus_tiltsensitivity': (5, 1),
            'minus_towersensitivity': (5, 1), 'plus_towersensitivity': (5, 1),
            'minus_fasttiltlimit': (5, 1), 'plus_fasttiltlimit': (5, 1),
            'minus_toweroffset': (5, 1), 'plus_toweroffset': (5, 1),
            'minus_rearfanspeed': (5, 1), 'plus_rearfanspeed': (5, 1),
        }
    #enddef


    @property
    def tilt_sensitivity(self):
        return self.configwrapper.tiltSensitivity
    #enddef

    @tilt_sensitivity.setter
    @value_saturate(-2, 2)
    @item_updater()
    def tilt_sensitivity(self, value):
        self.configwrapper.tiltSensitivity = value
    #enddef


    @property
    def tower_sensitivity(self):
        return self.configwrapper.towerSensitivity
    #enddef

    @tower_sensitivity.setter
    @value_saturate(-2, 2)
    @item_updater()
    def tower_sensitivity(self, value):
        self.configwrapper.towerSensitivity = value
    #enddef


    @property
    def fast_tilt_limit(self):
        return self.configwrapper.limit4fast
    #enddef

    @fast_tilt_limit.setter
    @value_saturate(0, 100)
    @item_updater()
    def fast_tilt_limit(self, value):
        self.configwrapper.limit4fast = value
    #enddef


    @property
    def tower_offset(self):
        if self._calibTowerOffset_mm is None:
            self._calibTowerOffset_mm = self.display.hwConfig.calcMM(self.configwrapper.calibTowerOffset)
        #endif
        return self._calibTowerOffset_mm
    #enddef

    @tower_offset.setter
    @value_saturate(-0.5, 0.5)
    @item_updater(str_func=lambda x: "%+.3f" % x)
    def tower_offset(self, value):
        self._calibTowerOffset_mm = value
        self.configwrapper.calibTowerOffset = self.display.hwConfig.calcMicroSteps(value)
    #enddef


    @property
    def rear_fan_speed(self):
        return self.configwrapper.fan3Pwm
    #enddef

    @rear_fan_speed.setter
    @value_saturate(0, 100)
    @item_updater()
    def rear_fan_speed(self, value):
        self.configwrapper.fan3Pwm = value
        # TODO: This is wrong, it would be nice to have API to set just one fan
        self.display.hw.setFansPwm((self.configwrapper.fan1Pwm,
                                   self.configwrapper.fan2Pwm,
                                   self.configwrapper.fan3Pwm))
        self.display.hw.setFans((False, False, True))
    #enddef


    @property
    def auto_power_off(self):
        return self.configwrapper.autoOff
    #enddef

    @auto_power_off.setter
    @item_updater()
    def auto_power_off(self, value):
        self.configwrapper.autoOff = value
    #enddef


    @property
    def cover_check(self):
        return self.configwrapper.coverCheck
    #enddef

    @cover_check.setter
    @item_updater()
    def cover_check(self, value):
        self.configwrapper.coverCheck = value
    #enddef


    @property
    def resin_sensor(self):
        return self.configwrapper.resinSensor
    #enddef

    @resin_sensor.setter
    @item_updater()
    def resin_sensor(self, value):
        self.configwrapper.resinSensor = value
    #enddef


    def show(self):
        if self.configwrapper is None or not self.confirmReturnPending:
            self.configwrapper = libConfig.ConfigHelper(self.display.hwConfig)
        else:
            self.confirmReturnPending = False
        #endif
        self._calibTowerOffset_mm = None

        self.items.update({
            'showAdmin': self.display.show_admin, # TODO: Remove once client uses show_admin
            'show_admin': self.display.show_admin,
            'tilt_sensitivity': self.tilt_sensitivity,
            'tower_sensitivity': self.tower_sensitivity,
            'fast_tilt_limit': self.fast_tilt_limit,
            'tower_offset': "%+.3f" % self.tower_offset,
            'rear_fan_speed': self.rear_fan_speed,
            'auto_power_off': self.auto_power_off,
            'cover_check': self.cover_check,
            'resin_sensor': self.resin_sensor,
        })
        super(PageAdvancedSettings, self).show()
    #enddef


    # Move platform
    def towermoveButtonRelease(self):
        return "towermove"
    #enddef


    # Move resin tank
    def tiltmoveButtonRelease(self):
        return "tiltmove"
    #enddef


    # Time settings
    def timesettingsButtonRelease(self):
        return "timesettings"
    #enddef


    # Change language (TODO: Not in the graphical design, not yet implemented properly)
    def setlanguageButtonRelease(self):
        return "setlanguage"
    #enddef


    # Hostname
    def sethostnameButtonRelease(self):
        return "sethostname"
    #enddef


    # Change name/password
    def setremoteaccessButtonRelease(self):
        return "setlogincredentials"
    #enddef


    # Tilt sensitivity
    def minus_tiltsensitivityButton(self):
        self.tilt_sensitivity -= 1
    #enddef
    def plus_tiltsensitivityButton(self):
        self.tilt_sensitivity += 1
    #enddef


    # Tower sensitivity
    def minus_towersensitivityButton(self):
        self.tower_sensitivity -= 1
    # enddef
    def plus_towersensitivityButton(self):
        self.tower_sensitivity += 1
    # enddef


    # Limit for fast tilt
    def minus_fasttiltlimitButton(self):
        self.fast_tilt_limit -= 1
    #enddef
    def plus_fasttiltlimitButton(self):
        self.fast_tilt_limit += 1
    #enddef


    # Tower offset
    # TODO: Adjust in mm, compute steps
    # Currently we are adjusting steps, but showing mm. This in counterintuitive.
    def minus_toweroffsetButton(self):
        self.tower_offset -= 0.001
    #enddef
    def plus_toweroffsetButton(self):
        self.tower_offset += 0.001
    #enddef


    # Display test
    def displaytestButtonRelease(self):
        return "displaytest"
    #enddef

    # Rear fan speed
    def minus_rearfanspeedButton(self):
        self.rear_fan_speed -= 1
    #enddef
    def plus_rearfanspeedButton(self):
        self.rear_fan_speed += 1
    #enddef


    # Auto power off
    def autopoweroffButtonRelease(self):
        self.auto_power_off = not self.auto_power_off
    #enddef


    # Cover check
    def covercheckButtonRelease(self):
        if self.cover_check:
            self.display.page_confirm.setParams(
                continueFce=self.disableCoverCheck,
                backFce=self._doConfirmReturn,
                text=_("Disable the cover sensor?\n"
                       "\n"
                       "CAUTION: This may lead to unwanted exposure to UV light. This action is not recommended!"))
            return "confirm"
        else:
            self.cover_check = True
        #endif
    #enddef


    def disableCoverCheck(self):
        self.cover_check = False
        return self._doConfirmReturn()
    #enddef


    def _doConfirmReturn(self):
        self.confirmReturnPending = True
        return "_BACK_"
    #enddef


    # Resin Sensor
    def resinsensorButtonRelease(self):
        if self.resin_sensor:
            self.display.page_confirm.setParams(
                continueFce=self.disableResinSensor,
                backFce=self._doConfirmReturn,
                text=_("Disable the resin sensor?\n"
                       "\n"
                       "CAUTION: This may lead to failed prints or resin tank overflow! This action is not recommended!"))
            return "confirm"
        else:
            self.resin_sensor = True
        #endif
    #enddef


    def disableResinSensor(self):
        self.resin_sensor = False
        return self._doConfirmReturn()
    #enddef


    # Firmware update
    def firmwareupdateButtonRelease(self):
        return "firmwareupdate"
    #enddef


    # Factory reset
    def factoryresetButtonRelease(self):
        return "factoryreset"
    #enddef


    # Admin
    def adminButtonRelease(self):
        if self.display.show_admin:
            return "admin"
        #endif
    #enddef


    # Logs export to usb
    def exportlogstoflashdiskButtonRelease(self):
        return self.saveLogsToUSB()
    #enddef


    # Show wizard
    def wizardButtonRelease(self):
        return "wizard1"
    #enddef


    # Back
    def leave(self, newPage):
        self.display.hw.stopFans()
        if self.configwrapper.changed() and newPage != "confirm":
            self.display.page_confirm.setParams(
                continueFce = self._savechanges,
                continueParams={'newPage': newPage},
                backFce = self._discardchanges,
                backParams={'newPage': newPage},
                text = _("Save changes"))
            return "confirm"
        else:
            return newPage
        #endif
    #enddef


    def _savechanges(self, newPage):
        sensitivity_changed = self.configwrapper.changed('towersensitivity') or self.configwrapper.changed('tiltsensitivity')
        if not self.configwrapper.commit():
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif

        if sensitivity_changed:
            self.logger.info("Motor sensitivity changed. Updating profiles.")
            self._updatesensitivity()
        #endif

        # TODO: This is wrong, display should handle this for us.
        if newPage == "_BACK_":
            self.display.goBack(2)
        else:
            self.display.setPage(newPage)
        #endif
    #enddef


    def _discardchanges(self, newPage):
        # TODO: This is wrong, it would be nice to have API to set just one fan
        self.display.hw.setFansPwm((self.display.hwConfig.fan1Pwm,
                                    self.display.hwConfig.fan2Pwm,
                                    self.display.hwConfig.fan3Pwm))

        # TODO: This is wrong, display should halde this for us.
        if newPage == "_BACK_":
            self.display.goBack(2)
        else:
            self.display.setPage(newPage)
        #endif
    #enddef


    def _updatesensitivity(self):
        # adjust tilt profiles
        profiles = self.display.hw.getTiltProfiles()
        self.logger.debug("profiles %s", profiles)
        profiles[0][4] = self.display.hw._tiltAdjust['homingFast'][self.display.hwConfig.tiltSensitivity + 2][0]
        profiles[0][5] = self.display.hw._tiltAdjust['homingFast'][self.display.hwConfig.tiltSensitivity + 2][1]
        profiles[1][4] = self.display.hw._tiltAdjust['homingSlow'][self.display.hwConfig.tiltSensitivity + 2][0]
        profiles[1][5] = self.display.hw._tiltAdjust['homingSlow'][self.display.hwConfig.tiltSensitivity + 2][1]
        self.display.hw.setTiltProfiles(profiles)
        self.logger.debug("profiles %s", profiles)

        # adjust tower profiles
        profiles = self.display.hw.getTowerProfiles()
        self.logger.debug("profiles %s", profiles)
        profiles[0][4] = self.display.hw._towerAdjust['homingFast'][self.display.hwConfig.towerSensitivity + 2][0]
        profiles[0][5] = self.display.hw._towerAdjust['homingFast'][self.display.hwConfig.towerSensitivity + 2][1]
        profiles[1][4] = self.display.hw._towerAdjust['homingSlow'][self.display.hwConfig.towerSensitivity + 2][0]
        profiles[1][5] = self.display.hw._towerAdjust['homingSlow'][self.display.hwConfig.towerSensitivity + 2][1]
        self.display.hw.setTowerProfiles(profiles)
        self.logger.debug("profiles %s", profiles)
    #enddef

#endclass


class PageFactoryReset(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Factory reset")
        super(PageFactoryReset, self).__init__(display)
        self.items.update({
            'text' : _("""Do you really want to perform the factory reset?

All settings will be deleted!""")})
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Please wait..."),
                line2 = _("Printer is being reset to factory defaults"))
        pageWait.show()
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait(3)
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile

        # move tilt and tower to packing position
        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.tiltMoveAbsolute(defines.defaultTiltHeight)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.setTowerProfile('moveFast')
        self.display.hw.towerMoveAbsolute(
            self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(74))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile

        # at this height may be screwed down tank and inserted protective foam
        self.display.page_confirm.setParams(
            continueFce = self.factoryResetStep2,
            text = _("""All settings will be deleted and the printer will shut down.

Continue?"""))
        return "confirm"
    #enddef


    def factoryResetStep2(self):
        pageWait = PageWait(self.display, line1 = _("Please wait..."),
                line2 = _("Printer returns to factory defaults."))
        pageWait.show()
        # slightly press the foam against printers base
        self.display.hw.towerMoveAbsolute(
            self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(93))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        topic = "prusa/sl1/factoryConfig"
        printerConfig = {
            "osVersion": self.display.hwConfig.os.versionId,
            "sl1fwVersion": defines.swVersion,
            "a64SerialNo": self.display.hw.cpuSerialNo,
            "mcSerialNo": self.display.hw.mcSerialNo,
            "mcFwVersion": self.display.hw.mcVersion,
            "mcBoardRev": self.display.hw.mcRevision,
            "towerHeight": self.display.hwConfig.towerHeight,
            "tiltHeight": self.display.hwConfig.tiltHeight,
            "uvCurrent": self.display.hwConfig.uvCurrent,
            "wizardUvVoltageRow1": self.display.hwConfig.wizardUvVoltage[0],
            "wizardUvVoltageRow2": self.display.hwConfig.wizardUvVoltage[1],
            "wizardUvVoltageRow3": self.display.hwConfig.wizardUvVoltage[2],
            "wizardFanRpm": self.display.hwConfig.wizardFanRpm,
            "wizardTempUvInit": self.display.hwConfig.wizardTempUvInit,
            "wizardTempUvWarm": self.display.hwConfig.wizardTempUvWarm,
            "wizardTempAmbient": self.display.hwConfig.wizardTempAmbient,
            "wizardTempA64": self.display.hwConfig.wizardTempA64,
            "wizardResinVolume": self.display.hwConfig.wizardResinVolume
        }
        try:
            mqtt.single(topic, json.dumps(printerConfig), qos=2, retain=True, hostname="mqttstage.prusa")
        except Exception as err:
            self.logger.warning("mqtt message not delivered. %s", err)
        #endtry

        hwConfig = libConfig.HwConfig()
        self.display.hwConfig.update(
            # set  to default those parameters which can be changed from advanced settings or via calibration
            towerheight=self.display.hwConfig.calcMicroSteps(defines.defaultTowerHeight),
            tiltheight=defines.defaultTiltHeight,
            tiltsensitivity=hwConfig.tiltSensitivity,
            towersensitivity=hwConfig.towerSensitivity,
            limit4fast=hwConfig.limit4fast,
            calibtoweroffset=hwConfig.calibTowerOffset,
            fan3pwm=hwConfig.fan3Pwm,
            autooff=hwConfig.autoOff,
            covercheck=hwConfig.coverCheck,
            resinsensor=hwConfig.resinSensor,
            calibrated="no",
            showadmin="no",
            showwizard="yes",
            showunboxing="yes"
        )
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text=_("Cannot save factory defaults configuration"))
            return "error"
        #endif
        self.display.shutDown(True)
    #enddef


    def _BACK_(self):
        return "_BACK_"
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
        self.updateDataPeriod = 1
    #enddef


    def getNetFirmwares(self):
        try:
            query_url = defines.firmwareListURL + "/?serial=" + self.display.hw.cpuSerialNo + "&version=" + self.display.hwConfig.os.versionId
            self.downloadURL(query_url, defines.firmwareListTemp, title=_("Downloading firmware list"),
                             timeout_sec=3)
            with open(defines.firmwareListTemp) as list_file:
                return json.load(list_file)
            #endwith
        except:
            self.logger.exception("Failed to load firmware list from the net")
            return []
        #endtry
    #enddef


    def fillData(self):
        # Get list of available firmware files on USB
        fw_files = glob.glob(os.path.join(defines.mediaRootPath, "**/*.raucb"))

        # Get list of avaible firmware files on net
        try:
            for fw in self.net_list:
                if fw['branch'] != "stable":
                    continue

                if fw['version'] == self.display.hwConfig.os.versionId:
                    continue

                fw_files.append(fw['url'])
            #endfor
        except:
            self.logger.exception("Failed to process net firmware list")
        #endtry

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
            'firmwares' : fw_files,
            'operation' : operation,
            'progress' : progress,
        }
    #enddef


    def show(self):
        self.net_list = self.getNetFirmwares()
        self.items.update(self.fillData())
        super(PageFirmwareUpdate, self).show()
    #enddef


    def updateData(self):
        items = self.fillData()
        if self.old_items != items:
            self.showItems(**items)
            self.old_items = items
        #endif
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
            text = _("Do you really want to update the firmware?"))
        return "confirm"
    #enddef


    def fetchUpdate(self, fw_url):
        try:
            self.downloadURL(fw_url, defines.firmwareTempFile, _("Fetching firmware"))
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

        pageWait = PageWait(self.display, line1 = _("Updating the firmware"))
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
                #endif

                # Check for operation failure
                if progress[1] == 'Installing failed.':
                    raise Exception("Update failed")
                #endif

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


    def fillData(self):
        wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')

        aps = {}
        for ap in wifisetup.GetAPs():
            aps[ap['ssid']] = ap

        return {
            'devlist' : self.display.inet.getDevices(),
            'wifi_mode' : wifisetup.WifiMode,
            'client_ssid' : wifisetup.ClientSSID,
            'client_psk' : wifisetup.ClientPSK,
            'ap_ssid' : wifisetup.APSSID,
            'ap_psk' : wifisetup.APPSK,
            'aps' : aps.values(),
            'wifi_ssid' : wifisetup.WifiConnectedSSID,
            'wifi_signal' : wifisetup.WifiConnectedSignal,
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
            text = _("""Do you really want to set the Wi-fi to client mode?

It may disconnect the web client."""))
        return "confirm"
    #enddef


    def apsetButtonSubmit(self, data):
        self.display.page_confirm.setParams(
            continueFce = self.setap,
            continueParams = { 'ssid': data['ap-ssid'], 'psk': data['ap-psk'] },
            text = _("""Do you really want to set the Wi-fi to AP mode?

It may disconnect the web client."""))
        return "confirm"
    #enddef


    def wifioffButtonSubmit(self, data):
        self.display.page_confirm.setParams(
            continueFce = self.wifioff,
            text = _("""Do you really want to turn off the Wi-fi?

It may disconnect the web client."""))
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
            if 'wlan0' in self.display.inet.getDevices():
                # Connection "ok"
                return "_BACK_"
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
            if 'ap0' in self.display.inet.getDevices():
                # AP "ok"
                return "_BACK_"
            #endfor
        #endfor

        # Connection fail
        self.display.page_error.setParams(
                text = _("Starting AP failed!"))
        return "error"
    #enddef

#endclass


# FIXME obsolete?
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

    def __init__(self, display):
        self.pageUI = "print"
        self.pageTitle = _("Print")
        super(PagePrint, self).__init__(display)
        self.callbackPeriod = 0.1
        self.callbackSkip = 6
    #enddef


    def prepare(self):

        if self.display.expo.inProgress():
            return
        #endif

        config = self.display.config

        # FIXME move to MC counters
        coLog = "job:%s+exp=%.1f/%d+step=%d" % (
                config.projectName,
                config.expTime,
                int(config.expTimeFirst),
                config.layerMicroSteps)
        self.jobLog("\n%s" % (coLog))

        self.display.hw.setTowerProfile('layer')
        self.display.hw.towerMoveAbsoluteWait(0)    # first layer will move up

        # FIXME spatne se spocita pri zlomech (layerMicroSteps 2 a 3)
        self.totalHeight = (config.totalLayers-1) * self.display.hwConfig.calcMM(config.layerMicroSteps) + self.display.hwConfig.calcMM(config.layerMicroStepsFirst)
        self.lastLayer = 0

        self.display.screen.getImgBlack()
        self.display.hw.setUvLedCurrent(self.display.hwConfig.uvCurrent)
        if not self.display.hwConfig.blinkExposure:
            self.display.hw.uvLed(True)
        #endif

        self.printStartTime = time()
        self.logger.debug("printStartTime: " + str(self.printStartTime))

        self.display.expo.start()
    #enddef


    def callback(self):

        if self.callbackSkip > 5:
            self.callbackSkip = 0
            retc = super(PagePrint, self).callback()
            if retc:
                return retc
            #endif
        #endif

        self.callbackSkip += 1
        expo = self.display.expo
        hwConfig = self.display.hwConfig

        if not expo.inProgress():

            if expo.exception is not None:
                raise Exception("Exposure thread exception: %s" % str(expo.exception))
            #endif

            printTime = int((time() - self.printStartTime) / 60)
            self.logger.info("Job finished - real printing time is %s minutes", printTime)
            self.jobLog(" - print time: %s  resin: %.1f ml" % (printTime, expo.resinCount) )

            self.display.hw.stopFans()
            self.display.hw.motorsRelease()
            if hwConfig.autoOff and not expo.canceled:
                self.display.shutDown(True)
            #endif
            return "_EXIT_"
        #endif

        if self.lastLayer == expo.actualLayer:
            return
        #endif

        self.lastLayer = expo.actualLayer
        config = self.display.config

        time_remain_min = self.countRemainTime(expo.actualLayer, expo.slowLayers)
        time_elapsed_min = int(round((time() - self.printStartTime) / 60))
        positionMM = hwConfig.calcMM(expo.position)
        percent = int(100 * (self.lastLayer-1) / config.totalLayers)
        self.logger.info("Layer: %d/%d  Height: %.3f/%.3f mm  Elapsed[min]: %d  Remain[min]: %d  Percent: %d",
                self.lastLayer, config.totalLayers, positionMM,
                self.totalHeight, time_elapsed_min, time_remain_min, percent)

        remain = None
        low_resin = False
        if expo.resinVolume:
            remain = expo.resinVolume - int(expo.resinCount)
            if remain < defines.resinFeedWait:
                self.display.page_feedme.manual = False
                expo.doFeedMe()
                self.display.page_systemwait.fill(
                    line1 = _("Wait until layer finish..."))
                return "systemwait"
            #endif
            if remain < defines.resinLowWarn:
                self.display.hw.beepAlarm(1)
                low_resin = True
            #endif
        #endif

        items = {
                'time_remain_min' : time_remain_min,
                'time_elapsed_min' : time_elapsed_min,
                'current_layer' : self.lastLayer,
                'total_layers' : config.totalLayers,
                'layer_height_first_mm' : self.display.hwConfig.calcMM(config.layerMicroStepsFirst),
                'layer_height_mm' : hwConfig.calcMM(config.layerMicroSteps),
                'position_mm' : positionMM,
                'total_mm' : self.totalHeight,
                'project_name' : config.projectName,
                'progress' : percent,
                'resin_used_ml' : expo.resinCount,
                'resin_remaining_ml' : remain,
                'resin_low' : low_resin
                }

        self.showItems(**items)
        #endif

    #enddef


    def show(self):
        self.items.update({
            'showAdmin' : int(self.display.show_admin), # TODO: Remove once client uses show_admin
            'show_admin': self.display.show_admin,
        })
        super(PagePrint, self).show()
    #enddef


    def feedmeButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce = self.doFeedme,
            text = _("Do you really want add the resin to the tank?"))
        return "confirm"
    #enddef


    def doFeedme(self):
        self.display.page_feedme.manual = True
        self.display.expo.doFeedMeByButton()
        self.display.page_systemwait.fill(
            line1 = _("Wait until layer finish..."))
        return "systemwait"
    #enddef


    def updownButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce = self.doUpAndDown,
            text = _("""Do you really want the platform to go up and down?

It may affect the printed object!"""))
        return "confirm"
    #enddef


    def doUpAndDown(self):
        self.display.expo.doUpAndDown()
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
                checkPowerbutton = False,
                text = _("Do you really want to cancel the actual job?"))
        return "confirm"
    #enddef


    def adminButtonRelease(self):
        if self.display.show_admin:
            return "admin"
        #endif
    #enddef


    def jobLog(self, text):
        with open(defines.jobCounter, "a") as jobfile:
            jobfile.write(text)
        #endwith
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
                'serial_number': self.display.hw.cpuSerialNo,
                'system_name': self.display.hwConfig.os.name,
                'system_version': self.display.hwConfig.os.version,
                'firmware_version': defines.swVersion,
                })
        self.updateDataPeriod = 0.5
        self.skip = 11
        self.checkPowerbutton = False
    #enddef


    def show(self):
        self.oldValues = {}
        self.items['controller_version'] = self.display.hw.mcVersion
        self.items['controller_serial'] = self.display.hw.mcSerialNo
        self.items['api_key'] = self.octoprintAuth
        self.items['tilt_fast_time'] = self.display.hwConfig.tiltFastTime
        self.items['tilt_slow_time'] = self.display.hwConfig.tiltSlowTime
        self.display.hw.resinSensor(True)
        self.skip = 11
        super(PageSysInfo, self).show()
    #enddef


    def updateData(self):
        items = {}
        if self.skip > 10:
            self._setItem(items, 'fans', {'fan%d_rpm' % i: v for i, v in enumerate(self.display.hw.getFansRpm())})
            self._setItem(items, 'temps', {'temp%d_celsius' % i: v for i, v in enumerate(self.display.hw.getMcTemperatures())})
            self._setItem(items, 'cpu_temp', self.display.hw.getCpuTemperature())
            self._setItem(items, 'leds', {'led%d_voltage_volt' % i: v for i, v in enumerate(self.display.hw.getVoltages())})
            self._setItem(items, 'devlist', self.display.inet.getDevices())
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
        apDeviceName = "ap0"
        items = {}
        devices = self.display.inet.getDevices()
        if devices:
            if apDeviceName in devices:
                # AP mode
                try:
                    with open(defines.wifiSetupFile, "r") as f:
                        wifiData = json.loads(f.read())
                    #endwith
                    ip = devices[apDeviceName]
                    items['mode'] = "ap"
                    items['ap_ssid'] = wifiData['ssid']
                    items['ap_psk'] = wifiData['psk']
                    items['qr'] = "WIFI:S:%s;T:WPA;P:%s;H:false;" % (wifiData['ssid'], wifiData['psk'])
                except Exception:
                    self.logger.exception("wifi setup file exception:")
                    items['mode'] = None
                    items['text'] = _("Error reading Wi-fi setup!")
                #endtry
            else:
                # client mode
                ip = self.display.inet.getIp()
                items['mode'] = "client"
                items['client_ip'] = ip
                items['client_hostname'] = self.display.inet.getHostname()
                items['qr'] = "http://maker:%s@%s/" % (self.octoprintAuth, ip)
            #endif
        else:
            # no internet connection
            items['mode'] = None
            items['text'] = _("Not connected to network")
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
                'line1' : "2018-2019 Prusa Research s.r.o.",
                'line2' : defines.aboutURL,
#                'qr' : "https://www.prusa3d.com",
                'qr' : "MECARD:N:Prusa Research s.r.o.;URL:www.prusa3d.com;EMAIL:info@prusa3d.com;;",
                'about_url': defines.aboutURL
                })
    #enddef


    def showadminButtonRelease(self):
        try:
            query_url = defines.admincheckURL + "/?serial=" + self.display.hw.cpuSerialNo
            self.downloadURL(query_url, defines.admincheckTemp, title=_("Checking admin access"))

            with open(defines.admincheckTemp, 'r') as file:
                admin_check = json.load(file)
                if not admin_check['result']:
                    raise Exception("Admin not enabled")
                #endif
            #endwith
        except:
            self.logger.exception("Admin accesibility check exception")
            self.display.page_error.setParams(
                text=_("Admin not accessible"))
            return "error"
        #endexcept

        self.display.page_confirm.setParams(
                continueFce = self.showadminContinue,
                text = _("""Do you really want to enable the admin menu?

Wrong settings will damage your printer!"""))
        return "confirm"
    #enddef


    def showadminContinue(self):
        self.display.show_admin = True
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
                self.logger.exception("Ignoring source project for exception")
                continue
            #endtry
        #endfor
    #enddef


    def processItem(self, item, path):
        # Skip . link
        if item.startswith('.'):
            raise SourceDir.NotProject(". dir")
        #endif

        # Skip files that fail to decode as utf-8
        try:
            item.decode('utf-8')
        except Exception as e:
            raise Exception('Invalid filename')
        #endtry

        # Add directory to result
        full_path = os.path.join(path, item)
        if os.path.isdir(full_path):
            # Count number of projects in current root and number of dirs that contain some projects
            nonempty_dirs = set()
            root_projects = 0
            for root, dirs, files in os.walk(full_path):
                for file in files:
                    (_, ext) = os.path.splitext(file)
                    if ext not in defines.projectExtensions:
                        continue
                    #endif

                    rel_path = os.path.relpath(root, os.path.normpath(full_path))
                    if rel_path == ".":
                        root_projects += 1
                    else:
                        nonempty_dirs.add(rel_path.split(os.sep)[0])
                    #endif
                #endfor
            #endfor

            num_items = len(nonempty_dirs) + root_projects
            if num_items == 0:
                raise SourceDir.NotProject("No project in dir")
            #endif

            return {
                'type': 'dir',
                'name': item,
                'path': item,
                'fullpath': full_path,
                'numitems': num_items
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
                'time': os.path.getmtime(full_path),
                'size': os.path.getsize(full_path),
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
        self.sources = {}
        super(PageSrcSelect, self).__init__(display)
        self.stack = False
        self.updateDataPeriod = 1
    #enddef


    def in_root(self):
        return self.currentRoot == "."
    #enddef


    def source_list(self):
        # Get source directories
        sourceDirs = [SourceDir(defines.internalProjectPath, "internal")]
        sourceDirs += [SourceDir(path, "usb") for path in glob.glob(os.path.join(defines.mediaRootPath, "*"))]

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
        content_map = {}
        for i, item in enumerate(content):
            choice = "choice%d" % i
            item['choice'] = choice
            content_map[choice] = item
        #endfor

        return content, content_map
    #enddef


    def fillData(self):
        ip = self.display.inet.getIp()
        if ip != "none" and self.octoprintAuth:
            text = "%s%s (%s)" % (ip, defines.octoprintURI, self.octoprintAuth)
        else:
            text = _("Not connected to network")
        #endif

        content, self.sources = self.source_list()

        return {
            'text': text,
            'sources': content
        }
    #enddef


    def show(self):
        self.items = self.fillData()
        super(PageSrcSelect, self).show()
    #enddef


    def updateData(self):
        items = self.fillData()
        if self.old_items != items:
            self.showItems(**items)
            self.old_items = items
        #endif
    #enddef


    def sourceButtonSubmit(self, data):
        try:
            item = self.sources[data['choice']]
        except KeyError:
            self.logger.info("Invalid choice id passed %s", data['choice'])
            return
        #endtry

        if item['type'] == 'dir':
            self.currentRoot = os.path.join(self.currentRoot, item['path'])
            self.currentRoot = os.path.normpath(self.currentRoot)
            self.logger.info("Current project selection root: %s" % self.currentRoot)
            return "sourceselect"
        else:
            return self.loadProject(item['fullpath'])
        #endif
    #enddef


    def deleteButtonSubmit(self, data):
        try:
            item = self.sources[data['choice']]
        except KeyError:
            self.logger.info("Invalid choice id passed %s", data['choice'])
            return
        #endtry

        if item['type'] == 'dir':
#            for root, dirs, files in os.walk(item['fullpath']):
#                for file in files:
#                    (name, ext) = os.path.splitext(file)
#                    if ext in defines.projectExtensions:
#                        os.remove(os.path.join(root, file))
#            return
            raise NotImplementedError
        else:
            try:
                os.remove(item['fullpath'])
            except OSError:
                self.logger.error("Failed to remove project file")
            return
        #endif
    #enddef


    def netChange(self):
        ip = self.display.inet.getIp()
        if ip != "none" and self.octoprintAuth:
            self.showItems(text = "%s%s (%s)" % (ip, defines.octoprintURI, self.octoprintAuth))
        else:
            self.showItems(text = _("Not connected to network"))
        #endif
    #enddef


    def loadProject(self, project_filename):
        pageWait = PageWait(self.display, line1 = _("Reading project data..."))
        pageWait.show()
        config = self.display.config
        config.parseFile(project_filename)
        if config.zipError is not None:
            sleep(0.5)
            self.display.page_error.setParams(
                    text = _("""Your project has a problem: %s

Re-export it and try again.""") % config.zipError)
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

    def __init__(self, display):
        self.pageUI = "error"
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
        self.backFce = kwargs.pop("backFce", None)
        self.backParams = kwargs.pop("backParams", dict())
        self.fill()
        self.items.update(kwargs)
    #enddef


    def okButtonRelease(self):
        self.display.hw.powerLed("normal")
        if self.backFce is None:
            return "_EXIT_"
        else:
            return self.backFce(**self.backParams)
        #endif
    #enddef

    #TODO remove back button from GUI
    def backButtonRelease(self):
        return self.okButtonRelease()
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
                'button13' : "",
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
        pageWait = PageWait(self.display, line1 = _("Moving platform to the top"))
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
        pageWait = PageWait(self.display, line1 = _("Moving platform to the top"))
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
        pass
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
        self.checkCooling = True
    #enddef


    def show(self):
        self.display.hw.startFans()
        self.display.screen.getImgBlack()
        self.display.screen.inverse()
        self.display.hw.setUvLedCurrent(self.display.hwConfig.uvCurrent)
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
        savepath = self.getSavePath()
        if savepath is None:
            self.display.page_error.setParams(
                text = _("No USB storage present"))
            return "error"
        #endif

        test_file = os.path.join(savepath, "test.png")

        if not os.path.isfile(test_file):
            self.display.page_error.setParams(
                text = _("Cannot find the test image"))
            return "error"
        #endif

        try:
            self.display.screen.getImg(filename = test_file)
        except Exception:
            # TODO: This is not reached. Exceptions from screen do not propagate here
            self.logger.exception("Error displaying test image")
            self.display.page_error.setParams(
                text = _("Cannot display the test image"))
            return "error"
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
        self.display.hw.startFans()
        self.display.hw.setUvLedCurrent(self.display.hwConfig.uvCurrent)
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
        self.display.hw.stopFans()
        return super(PageDisplay, self).backButtonRelease()
    #enddef

#endclass


class PageDisplayTest(Page):

    def __init__(self, display):
        self.pageUI = "yesno"
        self.pageTitle = _("Display test")
        super(PageDisplayTest, self).__init__(display)
        self.items.update({
            'imageName' : "10_prusa_logo.jpg",
            'text' : _("""Can you see company logo on the exposure display through the orange cover?

Tip: The logo is best seen when you look from above.

DO NOT open the cover.""")})
        self.stack = False
        self.checkCover = True
        self.checkCoverWarnOnly = False
        self.checkCoverUVOn = True
        self.checkCooling = True
    #enddef


    def show(self):
        if not self.display.hwConfig.coverCheck or self.display.hw.isCoverClosed():
            self.display.hw.uvLed(True)
            super(PageDisplayTest, self).show()
        #endif
        self.display.screen.getImg(filename=os.path.join(defines.dataPath, "logo_1440x2560.png"))
        self.display.hw.startFans()
    #enddef


    def yesButtonRelease(self):
        return "_OK_"
    #endif


    def noButtonRelease(self):
        return "_NOK_"
    #enddef


    def leave(self, newPage):
        self.display.hw.uvLed(False)
        self.display.screen.getImgBlack()
        self.display.hw.stopFans()
        return newPage
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
                'button12' : _("Logging"),
                'button13' : _("System Information"),
                'button14' : "",
                'button15' : "",
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
                text = _("""This overwrites the motion controller with the selected firmware.

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
        self.display.hw.initDefaults()
        return "_BACK_"
    #enddef


    def button8ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.mc2net,
                continueParams = { 'bootloader' : True },
                text = _("""This will disable the GUI and connect the MC bootloader to TCP port.

Are you sure?"""))
        return "confirm"
    #enddef


    def button9ButtonRelease(self):
        self.display.page_confirm.setParams(
                continueFce = self.mc2net,
                continueParams = { 'bootloader' : False },
                text = _("""This will disable the GUI and connect the motion controller to TCP port.

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
                text = _("""Is there the correct amount of resin in the tank?

Is the tank secured with both screws?"""))
        return "confirm"
    #enddef


    def button10Continue(self):
        # TODO vyzadovat zavreny kryt po celou dobu!
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Moving platform to the top"))
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

        pageWait.showItems(line2 = _("Measuring..."), line3 = _("Do NOT TOUCH the printer"))
        volume = self.display.hw.getResinVolume()
        self.display.hw.powerLed("normal")
        if not volume:
            self.display.page_error.setParams(
                    text = _("""Resin measuring failed!

Is there the correct amount of resin in the tank?

Is the tank secured with both screws?"""))
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
        return "logging"
    #enddef


    def button13ButtonRelease(self):
        return "sysinfo"
    #enddef


    def button14ButtonRelease(self):
        pass
    #enddef


    def button15ButtonRelease(self):
        pass
    #enddef

#endclass


class PageNetUpdate(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = _("Net Update")
        super(PageNetUpdate, self).__init__(display)

        # Create item for downlaoding examples
        self.items.update({
            "button15": _("Download examples")
        })

        self.firmwares = []
    #enddef


    def show(self):
        try:
            query_url = defines.firmwareListURL + "/?serial=" + self.display.hw.cpuSerialNo + "&version=" + self.display.hwConfig.os.versionId
            self.downloadURL(query_url, defines.firmwareListTemp, title=_("Downloading firmware list"),
                             timeout_sec=5)

            with open(defines.firmwareListTemp) as list_file:
                self.firmwares = list(enumerate(json.load(list_file)))
            #endwith
        except:
            self.logger.exception("Failed to load firmware list from the net")
        #endtry

        # Create items for updating firmwares
        self.items.update({
            "button%s" % (i + 1): ("%s - %s") % (firmware['version'], firmware['branch']) for (i, firmware) in self.firmwares
        })

        # Create action handlers
        for (i, firmware) in self.firmwares:
            self.makeUpdateButton(i + 1, firmware['version'], firmware['url'])
        #endfor

        super(PageNetUpdate, self).show()
    #enddef


    def button15ButtonRelease(self):
        try:
            if not os.path.isdir(defines.internalProjectPath):
                os.makedirs(defines.internalProjectPath)
            #endif

            self.downloadURL(defines.examplesURL, defines.examplesArchivePath, title=_("Fetching examples"))

            pageWait = PageWait(self.display, line1=_("Decompressing examples"))
            pageWait.show()
            pageWait.showItems(line1=_("Extracting examples"))
            with tarfile.open(defines.examplesArchivePath) as tar:
                tar.extractall(path=defines.internalProjectPath)
            #endwith
            pageWait.showItems(line1=_("Cleaning up"))

            return "_BACK_"
        #endtry

        except Exception as e:
            self.logger.error("Exaples fetch failed: " + str(e))
            self.display.page_error.setParams(
                text=_("Examples fetch failed"))
            return "error"
        #endexcept

        finally:
            os.remove(defines.examplesArchivePath)
        #endfinally
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


class PageLogging(Page):

    def __init__(self, display):
        self.pageUI = "admin"
        self.pageTitle = _("Logging")
        super(PageLogging, self).__init__(display)
        self.items.update({
            "button1": _("Save logs to USB")
        })
    #enddef


    def button1ButtonRelease(self):
        return self.saveLogsToUSB()
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
        savepath = self.getSavePath()
        if savepath is None:
            self.display.page_error.setParams(
                text=_("No USB storage present"))
            return "error"
        #endif

        config_file = os.path.join(savepath, defines.hwConfigFileName)

        if not self.display.hwConfig.writeFile(config_file):
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
    #enddef


    def button2ButtonRelease(self):
        ''' import '''
        savepath = self.getSavePath()
        if savepath is None:
            self.display.page_error.setParams(
                text=_("No USB storage present"))
            return "error"
        #endif

        config_file = os.path.join(savepath, defines.hwConfigFileName)

        if not os.path.isfile(config_file):
            self.display.page_error.setParams(
                text=_("Cannot find configuration to import"))
            return "error"
        #endif

        try:
            with open(config_file, "r") as f:
                self.display.hwConfig.parseText(f.read())
            #endwith
        except Exception:
            self.logger.exception("import exception:")
            self.display.page_error.setParams(
                text=_("Cannot import configuration"))
            return "error"
        #endtry

        # TODO: Does import also means also save? There is special button for it.
        if not self.display.hwConfig.writeFile(defines.hwConfigFile):
            self.display.page_error.setParams(
                text=_("Cannot save imported configuration"))
            return "error"
        #endif

        self.show()
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        self.display.hwConfig.update(**self.changed)
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
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
                'label1g5' : _("Auto power off"),
                'label1g6' : _("Mute (no beeps)"),

                'label2g1' : _("Screw (mm/rot)"),
                'label2g2' : _("Tilt msteps"),
                'label2g3' : _("Calib. tower offset [mm]"),
                'label2g4' : _("Measuring moves count"),
                'label2g5' : _("Stirring moves count"),
                'label2g6' : _("Delay after stirring [s]"),
                'label2g8' : _("MC board version"),
                })
    #enddef


    def show(self):
        self.temp['screwmm'] = self.display.hwConfig.screwMm
        self.temp['tiltheight'] = self.display.hwConfig.tiltHeight
        self.temp['calibtoweroffset'] = self.display.hwConfig.calibTowerOffset
        self.temp['measuringmoves'] = self.display.hwConfig.measuringMoves
        self.temp['stirringmoves'] = self.display.hwConfig.stirringMoves
        self.temp['stirringdelay'] = self.display.hwConfig.stirringDelay
        self.temp['mcboardversion'] = self.display.hwConfig.MCBoardVersion

        self.items['value2g1'] = str(self.temp['screwmm'])
        self.items['value2g2'] = str(self.temp['tiltheight'])
        self.items['value2g3'] = self._strOffset(self.temp['calibtoweroffset'])
        self.items['value2g4'] = str(self.temp['measuringmoves'])
        self.items['value2g5'] = str(self.temp['stirringmoves'])
        self.items['value2g6'] = self._strTenth(self.temp['stirringdelay'])
        self.items['value2g8'] = str(self.temp['mcboardversion'])

        self.temp['fancheck'] = self.display.hwConfig.fanCheck
        self.temp['covercheck'] = self.display.hwConfig.coverCheck
        self.temp['mcversioncheck'] = self.display.hwConfig.MCversionCheck
        self.temp['resinsensor'] = self.display.hwConfig.resinSensor
        self.temp['autooff'] = self.display.hwConfig.autoOff
        self.temp['mute'] = self.display.hwConfig.mute

        self.items['state1g1'] = int(self.temp['fancheck'])
        self.items['state1g2'] = int(self.temp['covercheck'])
        self.items['state1g3'] = int(self.temp['mcversioncheck'])
        self.items['state1g4'] = int(self.temp['resinsensor'])
        self.items['state1g5'] = int(self.temp['autooff'])
        self.items['state1g6'] = int(self.temp['mute'])

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


    def state1g5ButtonRelease(self):
        self._onOff(4, 'autooff')
    #enddef


    def state1g6ButtonRelease(self):
        self._onOff(5, 'mute')
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


    def minus2g4Button(self):
        self._value(3, 'measuringmoves', 1, 10, -1)
    #enddef


    def plus2g4Button(self):
        self._value(3, 'measuringmoves', 1, 10, 1)
    #enddef


    def minus2g5Button(self):
        self._value(4, 'stirringmoves', 1, 10, -1)
    #enddef


    def plus2g5Button(self):
        self._value(4, 'stirringmoves', 1, 10, 1)
    #enddef


    def minus2g6Button(self):
        self._value(5, 'stirringdelay', 0, 300, -5, self._strTenth)
    #enddef


    def plus2g6Button(self):
        self._value(5, 'stirringdelay', 0, 300, 5, self._strTenth)
    #enddef


    def minus2g8Button(self):
        self._value(7, 'mcboardversion', 5, 6, -1)
    #enddef


    def plus2g8Button(self):
        self._value(7, 'mcboardversion', 5, 6, 1)
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
        self.temp['trigger'] = self.display.hwConfig.trigger
        self.temp['limit4fast'] = self.display.hwConfig.limit4fast
        self.temp['layertowerhop'] = self.display.hwConfig.layerTowerHop
        self.temp['delaybeforeexposure'] = self.display.hwConfig.delayBeforeExposure
        self.temp['delayafterexposure'] = self.display.hwConfig.delayAfterExposure
        self.temp['upanddownwait'] = self.display.hwConfig.upAndDownWait
        self.temp['upanddowneverylayer'] = self.display.hwConfig.upAndDownEveryLayer

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
        pass
    #enddef


    def plus2g1Button(self):
        pass
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


class PageCalibration1(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 1/10")
        super(PageCalibration1, self).__init__(display)
        self.items.update({
            'imageName' : "06_tighten_knob.jpg",
            'text' : _(u"If the platform is not yet inserted, insert it according to picture at 0° angle and secure it with the black knob.")})
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
    #enddef


    def contButtonRelease(self):
        return "calibration2"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        self.display.hw.motorsRelease()
        return "_EXIT_"
    #enddef

#endclass


class PageCalibration2(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 2/10")
        super(PageCalibration2, self).__init__(display)
        self.items.update({
            'imageName' : "01_loosen_screws.jpg",
            'text' : _("Loosen small screws on the cantilever. Be careful not to unscrew them completely.")})
    #enddef


    def contButtonRelease(self):
        return "calibration3"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageCalibration3(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 3/10")
        super(PageCalibration3, self).__init__(display)
        self.items.update({
            'imageName' : "02_place_bed.jpg",
            'text' : _("Unscrew the tank, rotate it by 90 degrees and place it flat across the tilt bed. Remove the tank screws completely!")})
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display,
            line1 = _("Setting start position."),
            line2 = _("Please wait..."))
        pageWait.show()

        self.display.hw.powerLed("warn")
        self.display.hw.tiltMoveAbsolute(self.display.hw._tiltCalibStart)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.powerLed("normal")
        return "calibration4"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageCalibration4(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 4/10")
        super(PageCalibration4, self).__init__(display)
        self.items.update({
            'imageName' : "03_proper_aligment.jpg",
            'text' : _("In the next step, move the tilt up/down until the tilt frame is in direct contact with the resin tank. The tilt frame and tank have to be aligned in a perfect line.")})
    #enddef


    def contButtonRelease(self):
        return "calibration5"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageCalibration5(MovePage):

    def __init__(self, display):
        self.pageUI = "tiltmovecalibration"
        self.pageTitle = _("Calibration step 5/10")
        super(PageCalibration5, self).__init__(display)
        self.autorepeat = { "upslow" : (3, 1), "downslow" : (3, 1) }
    #enddef


    def show(self):
        self.display.hw.setTiltProfile('moveSlow')
        self.items["value"] = self.display.hw.getTiltPosition()
        self.moving = False
        super(PageCalibration5, self).show()
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


    def okButtonRelease(self):
        position = self.display.hw.getTiltPositionMicroSteps()
        if position is None:
            self.logger.error("Invalid tilt position to save!")
            self.display.hw.beepAlarm(3)
        else:
            self.display.hwConfig.tiltHeight = position
        #endif
        return "calibration6"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageCalibration6(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 6/10")
        super(PageCalibration6, self).__init__(display)
        self.items.update({
            'imageName' : "08_clean.jpg",
            'text' : _("""Make sure the platform, tank and tilt are PERFECTLY clean.

The image is for illustation only.""")})
    #enddef


    def contButtonRelease(self):
        return "calibration7"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageCalibration7(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 7/10")
        super(PageCalibration7, self).__init__(display)
        self.items.update({
            'imageName' : "04_tighten_screws.jpg",
            'text' : _("Return the tank to the original position and secure it with tank screws. Make sure you tighten both screws evenly and with the same amount of force.")})
    #enddef


    def contButtonRelease(self):
        return "calibration8"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef

#endclass


class PageCalibration8(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 8/10")
        super(PageCalibration8, self).__init__(display)
        self.items.update({
            'imageName' : "06_tighten_knob.jpg",
            'text' : _("""Check if the platform is properly secured with the black knob.

Do not rotate the platform. It should be positioned according to the picture.""")})
    #enddef


    def contButtonRelease(self):
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
            self.display.hw.towerSyncWait()
            self.display.page_confirm.setParams(
                continueFce = self.positionFailed,
                text = _("""Tower not at the expected position.

Is the platform and tank secured in correct position?

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
            self.display.hw.towerSyncWait()
            self.display.page_confirm.setParams(
                continueFce = self.positionFailed,
                text = _("""Tower not at the expected position.

Is the platform and tank secured in correct position?

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
        return "calibration9"
    #endif


    def positionFailed(self):
        return "_BACK_"
    #enddef


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef

#endclass


class PageCalibration9(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 9/10")
        super(PageCalibration9, self).__init__(display)
        self.items.update({
            'imageName' : "05_align_platform.jpg",
            'text' : _("""Adjust the platform so it's aligned with the exposition display.

Front edges of the platform and exposition display need to be parallel.""")})
    #enddef


    def contButtonRelease(self):
        return "calibration10"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageCalibration10(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration step 10/10")
        super(PageCalibration10, self).__init__(display)
        self.items.update({
            'imageName' : "07_tighten_screws.jpg",
            'text' : _("Tighten small screws on the cantilever little by little. For best results, tighten them as evenly as possible.")})
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Measuring tilt times..."), line2 = _("Please wait..."))
        pageWait.show()
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait()
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        tiltSlowTime = self.getTiltTime(pageWait, True)
        tiltFastTime = self.getTiltTime(pageWait, False)
        self.display.hw.setTowerProfile('moveFast')
        self.display.hw.setTiltProfile('moveFast')
        self.display.hw.tiltUpWait()
        self.display.hw.motorsHold()
        self.display.hwConfig.update(
            towerheight = self.display.hwConfig.towerHeight,
            tiltheight = self.display.hwConfig.tiltHeight,
            tiltfasttime = tiltFastTime,
            tiltslowtime = tiltSlowTime,
            calibrated = "yes")
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        self.display.hw.powerLed("normal")
        return "calibration11"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def getTiltTime(self, pageWait, slowMove):
        tiltTime = 0
        total = self.display.hwConfig.measuringMoves
        for i in xrange(total):
            pageWait.showItems(line3 = (_("Slow move %(count)d/%(total)d") if slowMove else _("Fast move %(count)d/%(total)d")) % { 'count' : i+1, 'total' : total })
            tiltStartTime = time()
            self.display.hw.tiltLayerUpWait()
            self.display.hw.tiltLayerDownWait(slowMove)
            tiltTime += time() - tiltStartTime
        #endfor
        return round(tiltTime / total, 1)
    #enddef

#endclass


class PageCalibration11(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Calibration done")
        super(PageCalibration11, self).__init__(display)
        self.items.update({
            'text' : _("All done, happy printing!")})
    #enddef


    def contButtonRelease(self):
        return "_EXIT_"
    #endif


    def backButtonRelease(self):
        return "_EXIT_"
    #enddef

#endclass


class PageCalibrationConfirm(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Cancel calibration?")
        super(PageCalibrationConfirm, self).__init__(display)
        self.items.update({
            'text' : _("""Do you really want to cancel calibration?

Machine will not work without going through it.""")})
    #enddef


    def contButtonRelease(self):
        return "_EXIT_"
    #endif


    def backButtonRelease(self):
        return "_NOK_"
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
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
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
                "button5" : _("Defaults"),
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
        savepath = self.getSavePath()
        if savepath is None:
            self.display.page_error.setParams(
                text=_("No USB storage present"))
            return "error"
        #endif

        profile_file = os.path.join(savepath, self.profilesFilename)

        try:
            with open(profile_file, "w") as f:
                f.write(json.dumps(self.profiles, sort_keys=True, indent=4, separators=(',', ': ')))
            #endwith
        except Exception:
            self.logger.exception("export exception:")
            self.display.page_error.setParams(
                text=_("Cannot export profile"))
            return "error"
        #endtry
    #enddef


    def button2ButtonRelease(self):
        ''' import '''
        savepath = self.getSavePath()
        if savepath is None:
            self.display.page_error.setParams(
                text=_("No USB storage present"))
            return "error"
        #endif

        profile_file = os.path.join(savepath, self.profilesFilename)

        if not os.path.isfile(profile_file):
            self.display.page_error.setParams(
                text=_("Cannot find profile to import"))
            return "error"
        #endif

        try:
            with open(profile_file, "r") as f:
                self.profiles = json.loads(f.read())
            #endwith
            self._setProfile()
            return
        except Exception:
            self.logger.exception("import exception:")
            self.display.page_error.setParams(
                text=_("Cannot import profile"))
            return "error"
        #endtry
    #enddef


    def button5ButtonRelease(self):
        ''' defaults '''
        try:
            with open(os.path.join(defines.dataPath, self.profilesFilename), "r") as f:
                self.profiles = json.loads(f.read())
            #endwith
            self._setProfile()
        except Exception:
            self.logger.exception("import exception:")
            self.display.page_error.setParams(
                text=_("Cannot load default profile"))
            return "error"
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

                'button1' : _("Save defaults"),
                'button3' : _("Defaults"),
                'button4' : _("Save"),
                'back' : _("Back"),
                })
        self.updateDataPeriod = 0.5
        self.changed = {}
        self.temp = {}
        self.valuesToSave = list(('fan1pwm', 'fan2pwm', 'fan3pwm', 'uvcurrent', 'pwrledpwm'))
        self.checkCooling = True
    #enddef


    def show(self):
        self.oldValues = {}
        super(PageFansLeds, self).show()
    #enddef


    def updateData(self):
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


    def button1ButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce=self.save_defaults,
            text=_("Save current values as factory defaults?")
        )
        return "confirm"
    #enddef


    def save_defaults(self):
        self._update_config()
        try:
            self.logger.info("Remounting factory partition rw")
            subprocess.check_call(["/usr/bin/mount", "-o", "remount,rw", defines.factoryMountPoint])

            defaults = {
                'fan1pwm': self.display.hwConfig.fan1Pwm,
                'fan2pwm': self.display.hwConfig.fan2Pwm,
                'fan3pwm': self.display.hwConfig.fan3Pwm,
                'uvcurrent': self.display.hwConfig.uvCurrent,
            }

            with open(defines.hwConfigFactoryDefaultsFile, "w") as file:
                toml.dump(defaults, file)
            #endwith

            self.display.hwConfig._defaults = defaults
        except:
            self.logger.exception("Failed to save factory defaults")
            self.display.page_error.setParams(
                text=_("!!! Failed to save factory defaults !!!"))
            return "error"
        finally:
            try:
                self.logger.info("Remounting factory partition ro")
                subprocess.check_call(["/usr/bin/mount", "-o", "remount,ro", defines.factoryMountPoint])
            except:
                self.logger.exception("Failed to remount factory partion ro")
        #endtry
        return "_BACK_"
    #enddef


    def button3ButtonRelease(self):
        self.display.page_confirm.setParams(
            continueFce=self.reset_to_defaults,
            text=_("Reset to factory defaults?")
        )
        return "confirm"
    #enddef


    def reset_to_defaults(self):
        self.display.hwConfig.update(
            uvcurrent=None,
            fan1pwm=None,
            fan2pwm=None,
            fan3pwm=None,
        )
        self._reset_hw_values()
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return "_BACK_"
    #enddef


    def _update_config(self):
        # filter only wanted items
        filtered = {k: v for k, v in filter(lambda t: t[0] in self.valuesToSave, self.changed.iteritems())}
        self.display.hwConfig.update(**filtered)
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        self._update_config()
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return super(PageFansLeds, self).backButtonRelease()
    #endif


    def _reset_hw_values(self):
        self.display.hw.setFansPwm(
            (self.display.hwConfig.fan1Pwm,
             self.display.hwConfig.fan2Pwm,
             self.display.hwConfig.fan3Pwm))
        self.display.hw.setUvLedCurrent(self.display.hwConfig.uvCurrent)
        self.display.hw.setPowerLedPwm(self.display.hwConfig.pwrLedPwm)
    #enddef


    def backButtonRelease(self):
        self._reset_hw_values()
        return super(PageFansLeds, self).backButtonRelease()
    #enddef


    def state1g1ButtonRelease(self):
        self._onOff(0, 'fs1')
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
        self.display.hw.setFanCheckMask((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(1, 'fs2')
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
        self.display.hw.setFanCheckMask((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(2, 'fs3')
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
        self.display.hw.setFanCheckMask((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g5ButtonRelease(self):
        self._onOff(4, 'uls')
        self.display.hw.uvLed(self.temp['uls'])
        if self.temp['uls']:
            self.display.hw.startFans()
        else:
            self.display.hw.stopFans()
        #endif
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

    def __init__(self, display):
        self.pageUI = "feedme"
        self.pageTitle = _("Feed me")
        super(PageFeedMe, self).__init__(display)
        self.manual = False
        self.checkCoverOveride = True
    #enddef


    def show(self):
        super(PageFeedMe, self).show()
        self.display.hw.powerLed("error")
    #enddef


    def backButtonRelease(self):
        self.display.hw.powerLed("normal")
        if not self.manual:
            self.display.expo.setResinVolume(None)
        #endif
        self.display.expo.doBack()
        return super(PageFeedMe, self).backButtonRelease()
    #enddef


    def refilledButtonRelease(self):
        self.display.hw.powerLed("normal")
        self.display.expo.setResinVolume(defines.resinFilled)
        self.display.expo.doContinue()
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
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
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
            'relative_path' : self.path,
            'base_path' : self.base_path,
            'absolute_path' : os.path.join(self.base_path, self.path),
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


class PageSetLoginCredentials(Page):

    def __init__(self, display):
        self.pageUI = "setlogincredentials"
        self.pageTitle = _("Login Credentials")
        super(PageSetLoginCredentials, self).__init__(display)
    #enddef


    def fillData(self):
        return {
            'api_key' : self.octoprintAuth,
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetLoginCredentials, self).show()
    #enddef


    def saveButtonSubmit(self, data):
        apikey = data['api_key']

        try:
            subprocess.check_call(["/bin/api-keygen.sh", apikey])
        except subprocess.CalledProcessError as e:
            self.display.page_error.setParams(
                text = _("Octoprint API key change failed"))
            return "error"
        #endexcept

        return "_BACK_"
    #enddef

#endclass


class PageUnboxing1(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Unboxing step 1/4")
        super(PageUnboxing1, self).__init__(display)
        self.items.update({
            'imageName' : "13_open_cover.jpg",
            'text' : _("""Please remove the safety sticker on the right and open the orange cover.

You can skip to wizard by hitting back button.""")})
    #enddef

    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display)
        pageWait.show()
        if self.display.hwConfig.coverCheck and self.display.hw.isCoverClosed():
            pageWait.showItems(
                    line1 = _("The cover is closed!"),
                    line2 = _("Please remove the safety sticker and open the orange cover."))
            self.display.hw.beepAlarm(3)
            while self.display.hw.isCoverClosed():
                sleep(0.5)
            #endwhile
        #endif
        pageWait.showItems(
            line1 = _("The printer is moving to allow for easier manipulation"),
            line2 = _("Please wait...")
        )
        self.display.hw.setTowerPosition(0)
        self.display.hw.setTowerProfile("homingFast")
        self.display.hw.towerMoveAbsolute(self.display.hwConfig.calcMicroSteps(30))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.powerLed("normal")
        return "unboxing2"
    #endif


    def backButtonRelease(self):
        return "unboxingconfirm"
    #enddef


    def _OK_(self):
        self.display.hwConfig.update(showunboxing = "no")
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return "wizard1"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageUnboxing2(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Unboxing step 2/4")
        super(PageUnboxing2, self).__init__(display)
        self.items.update({
            'imageName' : "14_remove_foam.jpg",
            'text' : _("Remove the black foam from both sides of the platform.")})
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = _("The printer is moving to allow for easier manipulation"),
            line2 = _("Please wait..."))
        pageWait.show()
        self.display.hw.towerSyncWait()
        self.display.hw.powerLed("normal")
        return "unboxing3"
    #enddef


    def backButtonRelease(self):
        return "unboxingconfirm"
    #enddef


    def _OK_(self):
        return "_OK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageUnboxing3(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Unboxing step 3/4")
        super(PageUnboxing3, self).__init__(display)
        self.items.update({
            'imageName' : "15_remove_bottom_foam.jpg",
            'text' : _("Unscrew and remove the resin tank and remove the black foam underneath it.")})
    #enddef


    def contButtonRelease(self):
        return "unboxing4"
    #enddef


    def backButtonRelease(self):
        return "unboxingconfirm"
    #enddef


    def _OK_(self):
        return "_OK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageUnboxing4(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Unboxing step 4/4")
        super(PageUnboxing4, self).__init__(display)
        self.items.update({
            'text' : _("Carefully peel off the orange protective foil from the exposition display.")})
    #enddef


    def contButtonRelease(self):
        self.display.hwConfig.update(showunboxing = "no")
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return "unboxing5"
    #enddef


    def backButtonRelease(self):
        return "unboxingconfirm"
    #enddef


    def _OK_(self):
        return "_OK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageUnboxing5(Page):
    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Unboxing done")
        super(PageUnboxing5, self).__init__(display)
        self.items.update({
            'text' : _("""The printer is fully unboxed and ready for the selftest.

Continue?""")})
    #enddef


    def contButtonRelease(self):
        return "wizard1"
    #enddef


    def backButtonRelease(self):
        return "_EXIT_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageUnboxingConfirm(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Skip unboxing?")
        super(PageUnboxingConfirm, self).__init__(display)
        self.items.update({
            'text' : _("""Do you really want to skip the unboxing wizard?

Press 'Continue' only in case you've assembled the printer as a kit, or you went through this wizard previously and the printer is unpacked.

Press 'Back' to return to the wizard.""")})
    #enddef


    def contButtonRelease(self):
        return "_OK_"
    #enddef


    def backButtonRelease(self):
        return "_NOK_"
    #enddef

#endclass


class PageWizard1(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Setup wizard step 1/5")
        super(PageWizard1, self).__init__(display)
        self.items.update({
            'text' : _("""Welcome to the setup wizard.

This procedure is mandatory and it will help you to set up the printer

Continue?""")})
    #enddef


    def contButtonRelease(self):
        # check serial numbers
        if (not re.match("CZPX\d{4}X009X[C|K]\d{5}", self.display.hw.cpuSerialNo) or
        not re.match("CZPX\d{4}X012X[C|K]\d{5}", self.display.hw.mcSerialNo)):
# FIXME we don't want cut off betatesters with MC without serial number
            self.display.page_error.setParams(
                backFce = self.justContinue, # use as confirm
                text = _("""Serial numbers in wrong format!

A64: %(a64)s
MC: %(mc)s

Please contact tech support!""" % {'a64' : self.display.hw.cpuSerialNo, 'mc' : self.display.hw.mcSerialNo}))
            return "error"

        #endif
        return self.justContinue() # only for confirm, join with contButtonContinue() when changed to error
    #enddef


    def justContinue(self):
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

Please check if the tilt motor and optical endstop are connected properly."""))
                return "error"
            elif homeStatus == 0:
                self.display.hw.tiltHomeCalibrateWait()
                self.display.hw.setTiltPosition(0)
                break
            #endif
        #endfor
        if homeStatus == -3:
            self.display.page_error.setParams(
                text = _("""Tilt home check failed!

Please contact tech support!

Tilt profiles need to be changed."""))
            return "error"
        #endif

        #tilt length measure
        pageWait.showItems(line1 = _("Tilt axis check"))
        self.display.hw.setTiltProfile("homingFast")
        self.display.hw.tiltMoveAbsolute(self.display.hw._tiltEnd)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.tiltMoveAbsolute(512)   # go down fast before endstop
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.setTiltProfile("homingSlow")    #finish measurement with slow profile (more accurate)
        self.display.hw.tiltMoveAbsolute(self.display.hw._tiltMin)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        #TODO make MC homing more accurate
        if self.display.hw.getTiltPosition() < -defines.tiltHomingTolerance or self.display.hw.getTiltPosition() > defines.tiltHomingTolerance:
            self.display.page_error.setParams(
                text = _("""Tilt axis check failed!

Current position: %d

Please check if the tilting mechanism can move smoothly in its entire range.""") % self.display.hw.getTiltPosition())
            return "error"
        #endif
        self.display.hw.setTiltProfile("homingFast")
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

Please check if the tower motor is connected properly."""))
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

Please contact tech support!

Tower profiles need to be changed."""))
            return "error"
        #endif
        self.display.hw.powerLed("normal")
        return "wizard2"
    #enddef


    def backButtonRelease(self):
        return "wizardconfirm"
    #enddef


    def _OK_(self):
        self.display.hw.uvLed(False)
        self.display.hw.motorsRelease()
        self.display.hw.stopFans()
        self.display.hwConfig.update(showwizard = "no")
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text = _("Cannot save wizard configuration"))
            return "error"
        #endif
        return "_EXIT_"
    #endef


    def _EXIT_(self):
        self.display.hw.uvLed(False)
        self.display.hw.motorsRelease()
        self.display.hw.stopFans()
        return "_EXIT_"
    #enddef

#endclass


class PageWizard2(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Setup wizard step 2/5")
        super(PageWizard2, self).__init__(display)
        self.items.update({
            'imageName' : "04_tighten_screws.jpg",
            'text' : _("""Secure the resin tank with resin tank screws.

Make sure the tank is empty and clean.""")})
    #enddef


    def contButtonRelease(self):
        return "wizard3"
    #enddef


    def backButtonRelease(self):
        return "wizardconfirm"
    #enddef


    def _OK_(self):
        return "_OK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageWizard3(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Setup wizard step 3/5")
        super(PageWizard3, self).__init__(display)
        self.items.update({
            'imageName' : "09_remove_platform.jpg",
            'text' : _("""Loosen the black knob and remove the platform.""")})
    #enddef


    def contButtonRelease(self):
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
        if self.display.hw.getTowerPositionMicroSteps() == 0:
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
        #endif
        position = self.display.hw.getTowerPositionMicroSteps()
        #MC moves tower by 1024 steps forward in last step of !twho
        if position < self.display.hw._towerEnd or position > self.display.hw._towerEnd + 1024 + 127: #add tolerance half fullstep
            self.display.page_error.setParams(
                text = _("""Tower axis check failed!

Current position: %d

Please check if the ballscrew can move smoothly in its entire range.""") % position)
            return "error"
        #endif

        # fan check
        pageWait.showItems(line1 = _("Fans check (fans are stopped)"))
        self.display.hw.stopFans()
        sleep(defines.fanStartStopTime)  # wait for fans to stop
        rpm = self.display.hw.getFansRpm()
        if any(rpm):
            self.display.page_error.setParams(
                text = _("""RPM detected when fans are expected to be off

Check if all fans are properly connected.

RPM data: %s""") % rpm)
            return "error"
        #endif
        pageWait.showItems(line1 = _("Fans check (fans are running)"))
        # TODO rafactoring needed -> fans object(s)
                        #fan1        fan2        fan3
        fanLimits = [[50,250], [1100, 1700], [150, 500]]
        hwConfig = libConfig.HwConfig()
        self.display.hw.setFansPwm((hwConfig.fan1Pwm, hwConfig.fan2Pwm, hwConfig.fan3Pwm))   #use default PWM. TODO measure fans in range of values
        self.display.hw.startFans()
        sleep(defines.fanStartStopTime)  # let the fans spin up
        rpm = [[], [], []]
        for i in xrange(defines.fanMeasCycles):
            tmp = self.display.hw.getFansRpm()
            rpm[0].append(tmp[0])   #UV
            rpm[1].append(tmp[1])   #blower
            rpm[2].append(tmp[2])   #rear
            pageWait.showItems(line1 = _("Fans check (fans are running). Remaining %d s") % (defines.fanMeasCycles - i))
            sleep(1)
        #endfor

        for i in xrange(3): #iterate over fans
            rpm[i].remove(max(rpm[i]))
            rpm[i].remove(min(rpm[i]))
            avgRpm = sum(rpm[i]) / len(rpm[i])
            if not fanLimits[i][0] <= avgRpm <= fanLimits[i][1]:
                self.display.page_error.setParams(
                    text = _("""RPM of %(fan)s not in range!

Please check if the fan is connected correctly.

RPM data: %(rpm)s""") % { 'fan' : self.display.hw.getFanName(i), 'rpm' : rpm[i] })
                return "error"
            #endif
            self.display.hwConfig.wizardFanRpm[i] = avgRpm
        #endfor

        # temperature check
        pageWait.showItems(line1 = _("A64 temperature check"))
        A64temperature = self.display.hw.getCpuTemperature()
        if A64temperature > self.display.hw._maxA64Temp:
            self.display.page_error.setParams(
                text = _(u"""A64 temperature is too high. Measured: %.1f °C!

Shutting down in 10 seconds...""") % A64temperature)
            self.display.page_error.show()
            sleep(10)
            self.display.shutDown(True)
            return "error"
        #endif

        pageWait.showItems(line1 = _("Thermistors temperature check"))
        temperatures = self.display.hw.getMcTemperatures()
        for i in xrange(2):
            if temperatures[i] < 0:
                self.display.page_error.setParams(
                    text = _("""Can't read %s

Please check if temperature sensors are connected correctly.""") % self.display.hw.getSensorName(i))
                return "error"
            #endif
            if i == 0:
                maxTemp = self.display.hw._maxUVTemp
            else:
                maxTemp = self.display.hw._maxAmbientTemp
            #endif
            if not self.display.hw._minAmbientTemp < temperatures[i] < maxTemp:
                self.display.page_error.setParams(
                    text = _(u"""%(sensor)s not in range!

Measured temperature: %(temp).1f °C.

Keep the printer out of direct sunlight at room temperature (18 - 32 °C).""")
                    % { 'sensor' : self.display.hw.getSensorName(i), 'temp' : temperatures[i] })
                return "error"
            #endif
        #endfor
        self.display.hwConfig.wizardTempA64 = A64temperature
        self.display.hwConfig.wizardTempUvInit = temperatures[0]
        self.display.hwConfig.wizardTempAmbient = temperatures[1]
        self.display.hw.powerLed("normal")
        return "wizard4"
    #enddef


    def backButtonRelease(self):
        return "wizardconfirm"
    #enddef


    def _OK_(self):
        return "_OK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageWizard4(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Setup wizard step 4/5")
        super(PageWizard4, self).__init__(display)
        self.items.update({
            'imageName' : "12_close_cover.jpg",
            'text' : _("""Please close the orange lid.

Make sure the tank is empty and clean.""")})
    #enddef


    def contButtonRelease(self):
        self.ensureCoverIsClosed()

        # UV LED voltage comparation
        pageWait = PageWait(self.display,
            line1 = _("UV LED check"),
            line2 = _("Please wait..."))
        pageWait.show()
        self.display.hw.setUvLedCurrent(0)
        self.display.hw.uvLed(True)
        uvCurrents = [0, 300, 600]
        diff = 0.4    # [mV] voltages in all rows cannot differ more than this limit
        for i in xrange(3):
            self.display.hw.setUvLedCurrent(uvCurrents[i])
            if self.display.hwConfig.MCBoardVersion < 6:    #for 05
                sleep(10)    #wait to refresh all voltages
            else:                                           #for 06+
                sleep(5)    #wait to refresh all voltages
            volts = self.display.hw.getVoltages()
            del volts[-1]   #delete power supply voltage
            if max(volts) - min(volts) > diff:
                self.display.page_error.setParams(
                    text = _("""UV LED voltages differ too much!

Please check if UV LED panel is connected properly.

Data: %(current)d mA, %(value)s V""") % { 'current' : uvCurrents[i], 'value' : volts})
                return "error"
            #endif
            self.display.hwConfig.wizardUvVoltage[0][i] = int(volts[0] * 1000)
            self.display.hwConfig.wizardUvVoltage[1][i] = int(volts[1] * 1000)
            self.display.hwConfig.wizardUvVoltage[2][i] = int(volts[2] * 1000)
        #endfor

        # UV LED temperature check
        pageWait.showItems(line1 = _("UV LED warmup check"))
        self.display.hw.setUvLedCurrent(700)
        for countdown in xrange(120, 0, -1):
            pageWait.showItems(line2 = _("Please wait %d s") % countdown)
            sleep(1)
            temp = self.display.hw.getUvLedTemperature()
            if temp > self.display.hw._maxUVTemp:
                self.display.page_error.setParams(
                    text = _("""UV LED too hot!

Please check if the UV LED panel is attached to the heatsink.

Temperature data: %s""") % temp)
                return "error"
            #endif
        #endfor
        self.display.hwConfig.wizardTempUvWarm = temp
        self.display.hw.setUvLedCurrent(self.display.hwConfig.uvCurrent)
        self.display.hw.powerLed("normal")

        return "displaytest"
    #enddef


    def backButtonRelease(self):
        return "wizardconfirm"
    #enddef


    def _NOK_(self):
        self.display.page_error.setParams(
            text = _("""Your display is broken somehow.

Please contact tech support!"""))
        return "error"
    #enddef


    def _OK_(self):
        return "wizard5"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageWizard5(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Setup wizard step 5/5")
        super(PageWizard5, self).__init__(display)
        self.items.update({
            'imageName' : "11_insert_platform_60deg.jpg",
            'text' : _("Leave the resin tank secured with screws and insert platform at a 60-degree angle, exactly like in the picture. The platform must hit the edges of the tank on its way down.")})
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = _("Resin sensor check"),
            line2 = _("Please wait..."),
            line3 = _("DO NOT touch the printer"))
        pageWait.show()
        self.display.hw.towerSyncWait()
        self.display.hw.setTowerPosition(self.display.hwConfig.calcMicroSteps(defines.defaultTowerHeight))
        volume = self.display.hw.getResinVolume()
        if not 110 <= volume <= 190:    #to work properly even with loosen rocker brearing
            self.display.page_error.setParams(
                text = _("""Resin sensor not working!

Please check if sensor is connected properly.

Measured %d ml.""") % volume)
            return "error"
        #endif
        self.display.hwConfig.wizardResinVolume = volume
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait()
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        self.display.hw.motorsRelease()
        self.display.hw.stopFans()
        self.display.hwConfig.update(
            wizarduvvoltagerow1 = ' '.join(str(n) for n in self.display.hwConfig.wizardUvVoltage[0]),
            wizarduvvoltagerow2 = ' '.join(str(n) for n in self.display.hwConfig.wizardUvVoltage[1]),
            wizarduvvoltagerow3 = ' '.join(str(n) for n in self.display.hwConfig.wizardUvVoltage[2]),
            wizardfanrpm = ' '.join(str(n) for n in self.display.hwConfig.wizardFanRpm),
            wizardtempuvinit = self.display.hwConfig.wizardTempUvInit,
            wizardtempuvwarm = self.display.hwConfig.wizardTempUvWarm,
            wizardtempambient = self.display.hwConfig.wizardTempAmbient,
            wizardtempa64 = self.display.hwConfig.wizardTempA64,
            wizardresinvolume = self.display.hwConfig.wizardResinVolume,
            showwizard = "no"
        )
        if not self.display.hwConfig.writeFile():
            self.display.page_error.setParams(
                text = _("Cannot save wizard configuration"))
            return "error"
        #endif

        #TODO save hardware.cfg to second slot

        return "wizard6"
    #enddef


    def backButtonRelease(self):
        return "wizardconfirm"
    #enddef


    def _OK_(self):
        return "_OK_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageWizard6(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Setup wizard done")
        super(PageWizard6, self).__init__(display)
        self.items.update({
            'text' : _("""Selftest OK.

Continue to calibration?""")})
    #enddef


    def contButtonRelease(self):
        return "calibration1"
    #enddef


    def backButtonRelease(self):
        return "_EXIT_"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


class PageWizardConfirm(Page):

    def __init__(self, display):
        self.pageUI = "confirm"
        self.pageTitle = _("Skip wizard?")
        super(PageWizardConfirm, self).__init__(display)
        self.items.update({
            'text' : _("""Do you really want to skip wizard?

Machine may not work correctly without going through this check.

Press 'Continue' to exit the wizard, or 'Back' to return to the wizard.""")})
    #enddef


    def contButtonRelease(self):
        return "_OK_"
    #endif


    def backButtonRelease(self):
        return "_NOK_"
    #enddef

#endclass
