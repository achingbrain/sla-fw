# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import glob
import logging
import os
import subprocess
from time import sleep
from typing import TYPE_CHECKING

import distro

from sl1fw import actions
from sl1fw import defines
from sl1fw.actions import get_save_path
from sl1fw.libConfig import ConfigException

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


class Page:

    def __init__(self, display: Display):
        self.pageUI = "splash"
        self.pageTitle = ""
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.autorepeat = {}
        self.stack = True
        self.clearStack = False
        self.items = dict()

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
        self.checkOverTempSkip = 20   # 10 sec
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


    def prepare(self):
        pass
    #enddef


    def leave(self):
        """
        Override this to modify page this page is left for.
        """
        pass
    #enddef


    def show(self):
        # renew save path every time when page is shown, it may change
        self.items.update({
            'save_path' : self.getSavePath(),
            'image_version' : "%s%s" % (distro.version(), _(" (factory mode)") if self.display.printer0.factory_mode else ""),
            'page_title' : _(self.pageTitle),
            })

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


    def wifiButtonRelease(self):
        return "netinfo"
    #enddef


    def networkButtonRelease(self):
        return "network"
    #enddef


    def infoButtonRelease(self):
        return "about"
    #enddef


    def turnoffButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.turnoffContinue,
                text = _("Do you really want to turn off the printer?"))
        return "yesno"
    #enddef


    def turnoffContinue(self):
        self.display.shutDown(True)
    #enddef


    def netChange(self):
        pass
    #enddef


    # Dynamic USB path, first usb device or None
    def getSavePath(self) -> str:
        path = get_save_path()
        if path is None:
            self.logger.debug("getSavePath returning None, no media seems present")
        #endif
        return str(path)
    #enddef


    def ensureCoverIsClosed(self):
        if not self.display.hwConfig.coverCheck or self.display.hw.isCoverClosed():
            return
        #endif
        self.display.hw.powerLed("warn")
        pageWait = self.display.makeWait(self.display,
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
        pageWait = self.display.makeWait(self.display, line1=_("Saving logs"))
        pageWait.show()
        try:
            actions.save_logs_to_usb(self.display.hw.cpuSerialNo)
        except FileNotFoundError:
            self.logger.exception("File not found saving logs to usb")
            self.display.pages['error'].setParams(text=_("No USB storage present"))
            return "error"
        except Exception as exception:
            self.logger.exception("Failed to save logs to usb")
            self.display.pages['error'].setParams(text=_(str(exception)))
            return "error"

        return "_BACK_"
    #enddef


    def writeToFactory(self, saveFce):
        try:
            self.logger.info("Remounting factory partition rw")
            subprocess.check_call(["/usr/bin/mount", "-o", "remount,rw", defines.factoryMountPoint])
            saveFce()
        except:
            self.logger.exception("Failed to save to factory partition")
            return False
        finally:
            try:
                self.logger.info("Remounting factory partition ro")
                subprocess.check_call(["/usr/bin/mount", "-o", "remount,ro", defines.factoryMountPoint])
            except:
                self.logger.exception("Failed to remount factory partion ro")
            #endtry
        #endtry
        return True
    #enddef


    def saveDefaultsFile(self):
        try:
            self.display.hwConfig.write_factory()
        except ConfigException:
            self.logger.exception("Defaults were not saved!")
        #endtry
    #enddef


    def _onOff(self, temp, changed, index, val):
        # TODO: Can changed be something else than self.changed ???
        # TODO: Can temp be something else than self.changed ???
        temp[val] = not temp[val]
        changed[val] = temp[val]
        self.showItems(**{ 'state1g%d' % (index + 1) : int(temp[val]) })
    #enddef


    def _value(self, temp, changed, index, val, valmin, valmax, change, strFce = str, minLimit = None):
        if valmin <= temp[val] + change <= valmax:
            temp[val] += change
            changed[val] = temp[val]
            if minLimit is not None and temp[val] < minLimit:
                show = "OFF"
            else:
                show = strFce(temp[val])
            #enddef
            self.showItems(**{ 'value2g%d' % (index + 1) : show })
        else:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def _setItem(self, items, oldValues, index, value):
        if oldValues.get(index, None) != value:
            if isinstance(value, bool):
                items[index] = int(value)
            elif isinstance(value, dict):
                items[index] = value
            else:
                items[index] = str(value)
            #endif
            oldValues[index] = value
        #endif
    #enddef


    def _syncTower(self):
        if not self.display.hw.towerSyncWait(retries = 2):
            self.display.pages['error'].setParams(
                    text = _("Tower homing failed!\n\n"
                        "Check the printer's hardware."))
            return "error"
        #endif
        return "_SELF_"
    #enddef


    def _syncTilt(self):
        if not self.display.hw.tiltSyncWait(retries = 2):
            self.display.pages['error'].setParams(
                    text = _("Tilt homing failed!\n\n"
                        "Check the printer's hardware."))
            return "error"
        #endif
        return "_SELF_"
    #enddef


    def _strOffset(self, value):
        return "%+.3f" % self.display.hwConfig.calcMM(value)
    #enddef


    def _strTenth(self, value):
        return "%.1f" % (value / 10.0)
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

        if self.display.expo:
            expoInProgress = self.display.expo.inProgress()
        else:
            expoInProgress = False
        #endif

        if not self.checkCoverOveride and (self.checkCover or expoInProgress):
            state = True
            self.checkCoverCallback()
        #endif

        if self.checkCooling or (expoInProgress and self.display.checkCoolingExpo):
            state = True
            retc = self.checkCoolingCallback(expoInProgress)
            if retc:
                return retc
            #endif
        #endif

        # always check the over temp
        self.checkOverTempCallback()

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

        if self.powerButtonCount > 0:
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
            pageWait = self.display.makeWait(self.display, line1 = _("Close the orange cover."))
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

            self.display.pages['error'].setParams(
                    backFce = backFce,
                    text = _("Reading of UV LED temperature has failed!\n\n"
                        "This value is essential for the UV LED lifespan and printer safety.\n\n"
                        "Please contact tech support!\n\n"
                        "%s") % addText)
            return "error"
        #endif

        if temp > defines.maxUVTemp:
            if expoInProgress:
                self.display.expo.doPause()
            else:
                self.display.hw.uvLed(False)
            #enddef
            self.display.hw.powerLed("error")
            pageWait = self.display.makeWait(self.display, line1 = _("UV LED OVERHEAT!"), line2 = _("Cooling down"))
            pageWait.show()
            self.display.hw.beepAlarm(3)
            while(temp > defines.maxUVTemp - 10): # hystereze
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

        fansState = self.display.hw.getFansError().values()
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
                addText = _("Expect overheating, but the print may continue.\n\n"
                        "If you don't want to continue, please press the Back button on top of the screen and the actual job will be canceled.")
            else:
                backFce = self.backButtonRelease
                addText = ""
            #endif

            self.display.pages['confirm'].setParams(
                    backFce = backFce,
                    continueFce = self.backButtonRelease,
                    beep = True,
                    text = _("Failed: %(what)s\n\n"
                        "Please contact tech support!\n\n"
                        "%(addText)s") % { 'what' : ", ".join(failedFans), 'addText' : addText })
            return "confirm"
        #endif
    #enddef


    def checkOverTempCallback(self):
        if self.checkOverTempSkip < 20:
            self.checkOverTempSkip += 1
            return
        #endif
        self.checkOverTempSkip = 0

        A64temperature = self.display.hw.getCpuTemperature()
        if A64temperature > defines.maxA64Temp - 10: # 60 C
            self.logger.warning("Printer is overheating! Measured %.1f °C on A64.", A64temperature)
            self.display.hw.startFans()
            #self.checkCooling = True #shouldn't this start the fan check also?
        #endif
        '''
        do not shut down the printer for now
        if A64temperature > defines.maxA64Temp: # 70 C
            self.logger.warning("Printer is shuting down due to overheat! Measured %.1f °C on A64.", A64temperature)
            self.display.pages['error'].setParams(
                text = _("Printers temperature is too high. Measured: %.1f °C!\n\n"
                    "Shutting down in 10 seconds") % A64temperature)
            self.display.pages['error'].show()
            for i in range(10):
                self.display.hw.beepAlarm(3)
                sleep(1)
            #endfor
            self.display.shutDown(True)
            return "error"
        #endif
        '''
    #enddef


    def exitPrint(self):
        self.display.expo.doExitPrint()
        self.display.expo.canceled = True
        self.display.setWaitPage(line1 = _("Job will be canceled after layer finish"))
        return "_SELF_"
    #enddef


    def loadProject(self, project_filename: str):
        pageWait = self.display.makeWait(self.display, line1 = _("Reading project data"))
        pageWait.show()
        zip_error = self.display.expo.parseProject(project_filename)
        if zip_error is not None:
            sleep(0.5)
            self.display.pages['error'].setParams(
                text=_("Your project has a problem: %s\n\n"
                       "Re-export it and try again.") % zip_error)
            return False
        #endif
        return True
    #endef


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


    def allOff(self):
        self.display.screen.getImgBlack()
        self.display.hw.uvLed(False)
        self.display.hw.stopFans()
        self.display.hw.motorsRelease()
    #enddef


    def getMeasPwms(self):
        if self.display.hw.is500khz:
            return defines.uvLedMeasMinPwm500k, defines.uvLedMeasMaxPwm500k
        else:
            return defines.uvLedMeasMinPwm, defines.uvLedMeasMaxPwm
        #endif
    #enddef

    def getMinPwm(self):
        min, max = self.getMeasPwms()
        return min
    #enddef

    def getMaxPwm(self):
        min, max = self.getMeasPwms()
        return max
    #enddef

#endclass
