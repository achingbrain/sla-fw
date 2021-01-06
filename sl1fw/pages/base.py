# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=inconsistent-return-statements
# pylint: disable=no-else-return
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-public-methods


from __future__ import annotations

import logging
from time import sleep
from typing import TYPE_CHECKING, Optional

import distro
from deprecation import deprecated
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw import defines, test_runtime
from sl1fw.states.exposure import ExposureState
from sl1fw.states.examples import ExamplesState
from sl1fw.state_actions.examples import Examples
from sl1fw.functions import files
from sl1fw.functions.system import shut_down, FactoryMountedRW, get_octoprint_auth, hw_all_off
from sl1fw.errors.exceptions import ConfigException
from sl1fw.libConfig import TomlConfig

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


class Page:
    Name = None

    def __init__(self, display: Display):
        self.pageUI = "splash"
        self.pageTitle = "unknown"
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
        return get_octoprint_auth(self.logger)
    #enddef

    @property
    def httpDigest(self):
        return TomlConfig(defines.remoteConfig).load().get('htdigest', True)
    #enddef

    def prepare(self):
        pass
    #enddef


    def leave(self):
        """
        Override this to modify page this page is left for.
        """
    #enddef


    def show(self):
        # renew save path every time when page is shown, it may change
        self.items.update({
            'save_path' : self.getSavePath(),
            'image_version' : "%s%s" % (distro.version(), _(" (factory mode)") if self.display.runtime_config.factory_mode else ""),
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


    def backButtonRelease(self): # pylint: disable=no-self-use
        return "_BACK_"
    #enddef


    @deprecated("There should be no wifi button, only network icon")
    def wifiButtonRelease(self):
        return self.networkButtonRelease()
    #enddef


    def networkButtonRelease(self): # pylint: disable=no-self-use
        return "network"
    #enddef


    @staticmethod
    def infoButtonRelease():
        return "about"
    #enddef


    def turnoffButtonRelease(self, hw_button = False): # pylint: disable=unused-argument
        self.display.pages['yesno'].setParams(
                yesFce = self.turnoffContinue,
                text = _("Do you really want to turn off the printer?"))
        return "yesno"
    #enddef


    def turnoffContinue(self):
        shut_down(self.display.hw)
    #enddef


    def netChange(self):
        pass
    #enddef


    def getSavePath(self) -> Optional[str]:
        """
        Dynamic USB path, first usb device or None

        :return: USB path as str or None
        """
        path = files.get_save_path()
        if path is None:
            self.logger.debug("getSavePath returning None, no media seems present")
            return None
        #endif
        return str(path)
    #enddef


    def ensureCoverIsClosed(self):
        if not self.display.hwConfig.coverCheck or self.display.hw.isCoverClosed():
            return
        #endif
        # TODO: Remove this once we do not need to do uvcalibration in factory on a kit
        if self.display.hw.isKit and self.display.runtime_config.factory_mode:
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


    def writeToFactory(self, saveFce):
        try:
            with FactoryMountedRW():
                ret = saveFce()
                if ret is None:
                    return True
                return ret
        except Exception:
            self.logger.exception("Failed to save to factory partition")
            return False
        #endtry
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


    @staticmethod
    def _setItem(items, oldValues, index, value):
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
            self.display.pages['error'].setParams(code=Sl1Codes.TOWER_HOME_FAILED.raw_code)
            return "error"
        #endif
        return "_SELF_"
    #enddef


    def _syncTilt(self):
        if not self.display.hw.tiltSyncWait(retries = 2):
            self.display.pages['error'].setParams(code=Sl1Codes.TILT_HOME_FAILED.raw_code)
            return "error"
        #endif
        return "_SELF_"
    #enddef


    def _strOffset(self, value):
        return "%+.3f" % self.display.hwConfig.calcMM(value)
    #enddef


    @staticmethod
    def _strTenth(value):
        return "%.1f" % (value / 10.0)
    #enddef


    def callback(self):
        self._page_switch_callback()

        state = False
        if self.checkPowerbutton:
            state = True
            retc = self.powerButtonCallback()
            if retc:
                return retc
            #endif
        #endif

        if self.display.expo:
            expoInProgress = self.display.expo.in_progress
        else:
            expoInProgress = False
        #endif

        if not self.checkCoverOveride and (self.checkCover or expoInProgress):
            state = True
            self.checkCoverCallback()
        #endif

        if self.checkCooling or (expoInProgress and self.display.runtime_config.check_cooling_expo):
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


    def _page_switch_callback(self):
        if not self.display.action_manager.exposure:
            return
        #endif

        state = self.display.action_manager.exposure.state
        page = self.display.actualPage.Name

        if state == ExposureState.CONFIRM and page not in ["printpreviewswipe", "exposure"]:
            self.logger.debug("Exposure in confirm state. Switching %s -> printpreview", page)
            self.display.forcePage("printpreviewswipe")
        #endif

        if state == ExposureState.CHECKS and page != "checks":
            self.logger.debug("Exposure in confirm state. Switching %s -> checks", page)
            self.display.forcePage("checks")
        #endif

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
            return self.turnoffButtonRelease(hw_button=True)
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
                self.display.runtime_config.check_cooling_expo = False
                backFce = self.exitPrint
            else:
                self.display.hw.uvLed(False)
                backFce = self.backButtonRelease
            #endif

            self.logger.error("UV temperature reading failed")
            self.display.pages['error'].setParams(
                code=Sl1Codes.UV_TEMP_SENSOR_FAILED.raw_code,
                backFce = backFce
            )
            return "error"
        #endif

        if temp > defines.maxUVTemp:
            if expoInProgress:
                self.display.expo.doPause()
            else:
                self.display.hw.uvLed(False)
            #enddef
            self.display.hw.powerLed("error")
            self.logger.error("UV LED overheating: %s", temp)
            pageWait = self.display.makeWait(self.display, line1 = _("UV LED OVERHEAT!"), line2 = _("Cooling down"))
            pageWait.show()
            self.display.hw.beepAlarm(3)
            while temp > defines.maxUVTemp - 10: # hystereze
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
        if not self.display.hwConfig.fanCheck or self.display.runtime_config.fan_error_override \
                or test_runtime.test_fan_error_override:
            return
        #endif

        fansState = self.display.hw.getFansError().values()
        if any(fansState):
            failedFans = []
            for num, state in enumerate(fansState):
                if state:
                    failedFans.append(self.display.hw.fans[num].name)
                #endif
            #endfor
            self.logger.error("Detected fan failure: %s", failedFans)

            self.display.runtime_config.fan_error_override = True

            if expoInProgress:
                backFce = self.exitPrint
                addText = _("Expect overheating, but the print may continue.\n\n"
                        "If you don't want to continue, please press the Back button on top of the screen and the current job will be canceled.")
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
        if A64temperature > defines.maxA64Temp: # 80 C
            self.logger.warning("Printer is overheating! Measured %.1f °C on A64.", A64temperature)
            if not any(fan.enabled for fan in self.display.hw.fans.values()):
                self.display.hw.startFans()
            #self.checkCooling = True #shouldn't this start the fan check also?
        #endif
    #enddef


    def exitPrint(self, retValue = "_BACK_"):
        self.display.expo.cancel()
        return retValue
    #enddef


    def allOff(self):
        hw_all_off(self.display.hw, self.display.screen)
    #enddef


    def downloadExamlpes(self):
        examples = Examples(self.display.inet)
        examples.start()
        examples.join()
        if examples.state != ExamplesState.COMPLETED:
            return False
        return True
    #enddef

#endclass
