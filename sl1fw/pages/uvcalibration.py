# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=inconsistent-return-statements
# pylint: disable=no-else-return
# pylint: disable=too-many-instance-attributes

from __future__ import annotations

import functools
import os
from dataclasses import asdict
from threading import Thread
from time import sleep
from abc import abstractmethod
from typing import TYPE_CHECKING, Optional
from datetime import datetime
import toml

import distro
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw import defines, test_runtime
from sl1fw.libConfig import TomlConfig, TomlConfigStats
from sl1fw.errors.exceptions import ConfigException, get_exception_code
from sl1fw.states.display import DisplayState
from sl1fw.libUvLedMeterMulti import UvLedMeterMulti, UvMeterState
from sl1fw.functions.files import save_wizard_history
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait
from sl1fw.pages.displaytest import PageDisplayTest

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageUvDataShow(Page):
    Name = "uvdatashow"

    def __init__(self, display):
        super(PageUvDataShow, self).__init__(display)
        self.pageUI = "picture"
        self.pageTitle = N_("UV calibration data")
    #enddef


    def prepare(self):
        data = TomlConfig(defines.uvCalibDataPath).load()
        if not data:
            data = TomlConfig(defines.uvCalibDataPathFactory).load()
        #endif
        return self.showData(data)
    #enddef


    def showData(self, data):
        if not data:
            self.display.pages['error'].setParams(code=Sl1Codes.NO_UV_CALIBRATION_DATA.raw_code)
            return "error"
        #enddef
        self.logger.info("Generating picture from: %s", str(data))
        imagePath = os.path.join(defines.ramdiskPath, "uvcalib.png")
        if data['uvSensorType'] == 0:
            UvLedMeterMulti().save_pic(800, 400, "PWM: %d" % data['uvFoundPwm'], imagePath, data)
            self.setItems(image_path = "file://%s" % imagePath)
        else:
            self.display.pages['error'].setParams(code=Sl1Codes.DATA_FROM_UNKNOWN_UV_SENSOR.raw_code)
            return "error"
        #endif
    #enddef

    def networkButtonRelease(self):
        self.logger.debug("Network control disabled in uvcalibration")
    #enddef

#endclass


@page
class PageUvDataShowFactory(PageUvDataShow):
    Name = "uvdatashowfactory"

    def prepare(self):
        data = TomlConfig(defines.uvCalibDataPathFactory).load()
        return self.showData(data)
    #enddef

#endclass


class PageUvCalibrationBase(Page):

    # one object to rule them all
    uvmeter = UvLedMeterMulti()
    skipAsking = False
    writeDataToFactory = False
    resetLedCounter = False
    resetDisplayCounter = False
    factoryUvPwm = None

    def __init__(self, display):
        super(PageUvCalibrationBase, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("UV LED calibration")
        self.checkCooling = True
        try:
            self.factoryUvPwm = TomlConfig(defines.uvCalibDataPathFactory).load()["uvFoundPwm"]
            self.logger.info("factoryUvPwm %s", self.factoryUvPwm)
        except KeyError:
            self.logger.error("not found factoryUvPwm")
    #enddef

    def off(self):
        self.uvmeter.close()
        self.allOff()
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
    #enddef


    @staticmethod
    def _EXIT_():
        return "_EXIT_"
    #enddef

    @staticmethod
    def _BACK_():
        return "_BACK_"
    #enddef


    def backButtonRelease(self):
        return "uvcalibrationcancel"
    #enddef


    def networkButtonRelease(self):
        self.logger.debug("Network control disabled in uvcalibration")
    #enddef

#endclass

@page
class PageUvCalibrationStart(PageUvCalibrationBase):
    Name = "uvcalibrationstart"

    def __init__(self, display):
        super(PageUvCalibrationStart, self).__init__(display)
        self.pageUI = "confirm"
    #enddef


    def show(self):
        PageUvCalibrationBase.skipAsking = True
        self.items.update({
            'text' : _("UV intensity not set!\n\n"
                "Calibrate now?")})
        super(PageUvCalibrationStart, self).show()
    #enddef


    @staticmethod
    def contButtonRelease():
        return "uvcalibration"
    #enddef

#endclass

@page
class PageUvCalibration(PageUvCalibrationBase):
    Name = "uvcalibration"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageWait = None


    def show(self):
        PageUvCalibrationBase.writeDataToFactory = False
        PageUvCalibrationBase.resetDisplayCounter = False
        PageUvCalibrationBase.resetLedCounter = False
        minpwm, maxpwm = self.display.hw.getMeasPwms()
        text = _("Welcome to the UV LED calibration.\n\n"
                "1. If the resin tank is in the printer, remove it along with the screws.\n"
                "2. Close the orange lid, don't open it! UV radiation is harmful!")
        if self.display.runtime_config.factory_mode:
            text += _("\n\nIntensity: center %(cint)d, edge %(eint)d\n"
                "Warm-up: %(time)d s, PWM: <%(minp)d, %(maxp)d>") \
            % { 'cint' : self.display.hwConfig.uvCalibIntensity,
                'eint' : self.display.hwConfig.uvCalibMinIntEdge,
                'time' : self.display.hwConfig.uvWarmUpTime,
                'minp' : minpwm,
                'maxp' : maxpwm,
                }
        #endif
        self.items.update({
            'text' : text,
            'imageName' : "selftest-remove_tank.jpg"})
        super(PageUvCalibration, self).show()
    #enddef


    @staticmethod
    def contButtonRelease():
        if PageUvCalibrationBase.skipAsking is True:
            PageUvCalibrationBase.skipAsking = False
            return PageUvCalibrationResolve.Name
        return PageUvCalibrationDisplay.Name


@page
class PageUvCalibrationDisplay(PageUvCalibrationBase):
    Name = "uvcalibrationdisplay"

    def __init__(self, display):
        super(PageUvCalibrationDisplay, self).__init__(display)
        self.pageUI = "yesno"


    def show(self):
        self.items.update({
            'pageTitle' : N_("New display?"),
            'text' : _("Did you replaced the\n"
                "EXPOSITION DISPLAY\n"
                "for new one?")})
        super(PageUvCalibrationDisplay, self).show()


    @staticmethod
    def yesButtonRelease():
        PageUvCalibrationBase.writeDataToFactory = True
        PageUvCalibrationBase.resetDisplayCounter = True
        return PageUvCalibrationLedSet.Name


    @staticmethod
    def noButtonRelease():
        return PageUvCalibrationLedSet.Name


@page
class PageUvCalibrationLedSet(PageUvCalibrationBase):
    Name = "uvcalibrationledset"

    def __init__(self, display):
        super(PageUvCalibrationLedSet, self).__init__(display)
        self.pageUI = "yesno"


    def show(self):
        self.items.update({
            'pageTitle' : N_("New UV led set?"),
            'text' : _("Did you replaced the\n"
                "UV LED SET\n"
                "for new one?")})
        super(PageUvCalibrationLedSet, self).show()


    @staticmethod
    def yesButtonRelease():
        PageUvCalibrationBase.writeDataToFactory = True
        PageUvCalibrationBase.resetLedCounter = True
        return PageUvCalibrationResolve.Name


    @staticmethod
    def noButtonRelease():
        return PageUvCalibrationResolve.Name


@page
class PageUvCalibrationResolve(PageUvCalibrationBase):
    Name = "uvcalibrationresolve"

    def prepare(self):
        if PageUvCalibrationBase.writeDataToFactory is not True: # if neither the display nor the led set was replaced, do not show the warning page
            return PageUvCalibrationPrepare.Name


    def show(self):
        self.items.update({
            'text' : _("WARNING! Since you have replaced the exposition display or the UV LED set,\n"
                "this procedure will rewrite the factory calibration data.")})
        super(PageUvCalibrationResolve, self).show()

    @staticmethod
    def contButtonRelease():
        return PageUvCalibrationPrepare.Name


@page
class PageUvCalibrationPrepare(PageUvCalibrationBase):
    Name = "uvcalibrationprepare"

    def __init__(self, display):
        super(PageUvCalibrationPrepare, self).__init__(display)
        self.pageWait = None


    def prepare(self):
        self.pageWait = PageWait(self.display, line1=_("Setting start positions"), line2=_("Please wait..."))
        self.pageWait.pageTitle = N_("UV LED calibration")
        self.pageWait.show()
        self.display.state = DisplayState.CALIBRATION
        # TODO: Remove this once we do not need to do uvcalibration in factory on a kit
        if not (self.display.hw.isKit and self.display.runtime_config.factory_mode):
            # Skip setting of initial positions as the kit not fully assembled at the factory (there is no tower)
            self.display.hw.towerSync()
            self.display.hw.tiltSync()
            while self.display.hw.isTowerMoving() or self.display.hw.isTiltMoving():
                sleep(0.25)
            #endwhile
            if not self.display.hw.isTowerSynced():
                self.display.state = DisplayState.IDLE
                self.display.pages['error'].setParams(code=Sl1Codes.TOWER_HOME_FAILED.raw_code)
                return "error"
            #endif
            if not self.display.hw.isTiltSynced():
                self.display.state = DisplayState.IDLE
                self.display.pages['error'].setParams(code=Sl1Codes.TILT_HOME_FAILED.raw_code)
                return "error"
            #endif
            self.display.hw.tiltLayerUpWait()

            if not self.display.doMenu(PageDisplayTest.Name):
                self.off()
                return self._EXIT_()
            #endif


    def show(self):
        self.items.update({
            'imageName' : "uvcalibration_insert_meter.jpg",
            'text' : _("1. Place the UV calibrator on the print display and connect it to the front USB.\n"
                "2. Close the orange lid, don't open it! UV radiation is harmful!")})
        super(PageUvCalibrationPrepare, self).show()


    def contButtonRelease(self):
        if not self.checkUVMeter():
            self.off()
            self.display.state = DisplayState.IDLE
            return "error"
        #endif
        self.warmUp()
        if not self.checkPlacement():
            self.off()
            self.display.state = DisplayState.IDLE
            return "error"
        #endif
        self.display.pages[PageUVCalibrateCenter.Name].boostResults = False
        return PageUVCalibrateCenter.Name
    #enddef


    def checkUVMeter(self):
        self.ensureCoverIsClosed()
        self.pageWait.showItems(line1 = _("Waiting for UV calibrator"))
        self.pageWait.show()
        for i in range(0, defines.uvLedMeterMaxWait_s, -1):
            self.pageWait.showItems(line2 = ngettext("Remaining %d second",
                "Remaining %d seconds", i) % i)
            if self.uvmeter.present:
                break
            #endif
            sleep(1)
        #endfor
        self.pageWait.showItems(line2 = "")

        if not self.uvmeter.present:
            self.display.pages['error'].setParams(code=Sl1Codes.UV_LED_METER_NOT_DETECTED.raw_code)
            return False
        #endif
        self.pageWait.showItems(line1 = _("Connecting to the UV calibrator"), line2 = _("Please wait..."))
        if not self.uvmeter.connect():
            self.display.pages['error'].setParams(code=Sl1Codes.UV_LED_METER_NOT_RESPONDING.raw_code)
            return False
        #endif

        return True
    #enddef


    def warmUp(self):
        self.ensureCoverIsClosed()
        self.pageWait.showItems(line1 = _("Warming up"))

        self.display.hw.startFans()
        self.display.hw.uvLedPwm = self.display.hw.getMaxPwm()
        self.display.screen.blank_screen()
        self.display.hw.uvLed(True)

        for countdown in range(self.display.hwConfig.uvWarmUpTime, 0, -1):
            self.pageWait.showItems(line2 = ngettext("Remaining %d second",
                "Remaining %d seconds", countdown) % countdown)
            sleep(1)
            if test_runtime.testing:
                self.logger.debug("Skipping UV warm-up due to testing")
                break
            #endif
        #endfor

        self.display.hw.uvLedPwm = self.display.hw.getMinPwm()
    #enddef


    def checkPlacement(self):
        self.ensureCoverIsClosed()
        self.showItems(line1 = _("Checking UV calibrator placement on the screen"), line2 = _("Please wait..."))
        retc = self.uvmeter.check_place(self.display.screen.inverse)
        if not retc:
            return True
        #endif

        if retc == UvMeterState.ERROR_COMMUNICATION:
            self.display.pages['error'].setParams(code=Sl1Codes.UV_LED_METER_COMMUNICATION_ERROR.raw_code)
        elif retc == UvMeterState.ERROR_TRANSLUCENT:
            self.display.pages['error'].setParams(code=Sl1Codes.DISPLAY_TRANSLUCENT.raw_code)
        elif retc == UvMeterState.ERROR_INTENSITY:
            self.display.pages['error'].setParams(code=Sl1Codes.UNEXPECTED_UV_INTENSITY.raw_code)
        else:
            self.display.pages["error"].setParams(
                code=Sl1Codes.UNKNOWN_UV_MEASUREMENT_ERROR.raw_code,
                params={"code": retc}
            )
        return False
#endclass


class PageUvCalibrationThreadBase(PageUvCalibrationBase):

    ERROR_DONE = 0
    ERROR_READ_FAILED = 1
    ERROR_TOO_BRIGHT = 2
    ERROR_TOO_DIMM = 3
    ERROR_TOO_HIGH_DEVIATION = 4
    INTENSITY_DEVIATION_THRESHOLD = 25


    def __init__(self, display):
        super(PageUvCalibrationThreadBase, self).__init__(display)
        self.pageUI = "wait"
        self.pageTitle = N_("UV LED calibration")
        self.continuePage = None
        self.pwm = None
        self.intensity = None
        self.minValue = None
        self.deviation = 2 * self.INTENSITY_DEVIATION_THRESHOLD
        self.result = None
        self.thread: Optional[Thread] = None
        self.boostResults = False
        self.boostMultiplier = 1.2
        self.secondPassThreshold = 240


    def show(self):
        self.intensity = None
        self.minValue = None
        self.deviation = 2 * self.INTENSITY_DEVIATION_THRESHOLD
        self.display.uvCalibData = None

        if PageUvCalibrationBase.resetLedCounter or PageUvCalibrationBase.resetDisplayCounter or PageUvCalibrationBase.factoryUvPwm is None:   # if user replaced HW component allow UV PWM up to 240 without boost
            PageUvCalibrationBase.factoryUvPwm = 200
            PageUvCalibrationBase.writeDataToFactory = True  # only scenario when this will change the value False->True is with new KIT
            self.logger.info("using temporary default factoryUvPwm %s", PageUvCalibrationBase.factoryUvPwm)

        # TODO Concurrent.futures would allow us to pass errors as exceptions
        self.result = None
        self.thread = Thread(target = self.calibrate_thread)
        self.thread.start()

        if self.Name == PageUVCalibrateCenter.Name:
            self.showItems(line1 = _("Calibrating UV LED power in the center of the print display"))
            for countdown in range(defines.uvCalibDuration, 0, -1):
                if self.result == self.ERROR_DONE:
                    break
                self.showItems(line2 = ngettext("Remaining %d second",
                    "Remaining %d seconds", countdown) % countdown)
                sleep(1)
            #endfor
        else:
            self.showItems(line1 = _("Calibrating UV LED power on the edges of the print display"), line2 = _("Please wait..."))
        #endif
    #enddef


    def calibrate_thread(self):
        self.result, self.display.uvCalibData = self.calibrate()
    #enddef


    @abstractmethod
    def calibrate(self):
        ...
    #enddef


    def callback(self):
        retc = super(PageUvCalibrationThreadBase, self).callback()
        if retc:
            return retc
        #endif

        if self.thread.is_alive():
            return
        #endif

        if ((self.pwm > self.secondPassThreshold or
                self.pwm > (PageUvCalibrationBase.factoryUvPwm / 100) * (100 + self.display.hwConfig.uvCalibBoostTolerance) or
                self.result == self.ERROR_TOO_DIMM) and
                not self.boostResults and
                not self.uvmeter.sixty_points):
            # Possibly the UV sensor does not match UV LED wavelength, lets try with corrected readings
            self.boostResults = True
            self.logger.info(
                "Requested intensity cannot be reached by max. allowed PWM, run second iteration with boostResults on (PWM=%d)",
                self.pwm)
            self.logger.info("Boosted results applied due to bigger tolerance. Factory: %d, max: %f, tolerance: %d",
                PageUvCalibrationBase.factoryUvPwm,
                (PageUvCalibrationBase.factoryUvPwm / 100)  * (100 + self.display.hwConfig.uvCalibBoostTolerance),
                self.display.hwConfig.uvCalibBoostTolerance)
            self.display.hw.beepAlarm(2)
            return PageUVCalibrateCenter.Name

        self.display.screen.blank_screen()

        if self.result == self.ERROR_DONE:
            self.display.pages[self.continuePage].boostResults = self.boostResults
            return self.continuePage
        #endif

        if self.result == self.ERROR_READ_FAILED:
            self.display.pages['error'].setParams(code=Sl1Codes.UV_LED_METER_COMMUNICATION_ERROR.raw_code)
        elif self.result == self.ERROR_TOO_BRIGHT:
            self.display.pages['error'].setParams(code=Sl1Codes.UV_TOO_BRIGHT.raw_code)
        elif self.result == self.ERROR_TOO_DIMM:
            self.display.pages['error'].setParams(code=Sl1Codes.UV_TOO_DIMM.raw_code)
        elif self.result == self.ERROR_TOO_HIGH_DEVIATION:
            self.display.pages['error'].setParams(
                code=Sl1Codes.UV_INTENSITY_DEVIATION_TOO_HIGH.raw_code,
                params={
                    "found": self.deviation,
                    "allowed": self.INTENSITY_DEVIATION_THRESHOLD,
                }
            )
        else:
            self.display.pages['error'].setParams(code=Sl1Codes.UNKNOWN_UV_MEASUREMENT_ERROR.raw_code)

        self.off()
        return "error"
    #enddef

#endclass


@page
class PageUVCalibrateCenter(PageUvCalibrationThreadBase):
    Name = "uvcalibratecenter"

    PARAM_P = 0.75
    PARAM_I = 0.0025
    TUNNING_ITERATIONS = 100
    SUCCESS_ITERATIONS = 5


    def __init__(self, display):
        super(PageUVCalibrateCenter, self).__init__(display)
        self.continuePage = PageUVCalibrateEdge.Name
    #enddef


    def calibrate(self):
        # Start UV led with minimal pwm
        self.pwm = self.display.hw.getMinPwm()

        error = 0
        integrated_error = 0
        success_count = 0

        # Calibrate LED Power
        for iteration in range(0, self.TUNNING_ITERATIONS):
            self.display.hw.uvLedPwm = self.pwm
            # Read new intensity value
            data = self.uvmeter.read_data()
            if data is None:
                return self.ERROR_READ_FAILED, None
            else:
                self.intensity = data.uvMean if not self.boostResults else data.uvMean * self.boostMultiplier
                self.deviation = data.uvStdDev
                data.uvFoundPwm = -1    # for debug log
                self.logger.info("New UV sensor data %s", str(data))
            #endif

            # Calculate new error
            error = self.display.hwConfig.uvCalibIntensity - self.intensity
            integrated_error += error

            self.logger.info("UV pwm tuning: pwm: %d, intensity: %f, error: %f, integrated: %f, iteration: %d, success count: %d",
                              self.pwm, self.intensity, error, integrated_error, iteration, success_count)

            # Break cycle when error is tolerable
            if abs(error) < self.uvmeter.INTENSITY_ERROR_THRESHOLD:
                if success_count >= self.SUCCESS_ITERATIONS:
                    break
                #endif
                success_count += 1
            else:
                success_count = 0
            #endif

            # Adjust PWM according to error, integrated error and operational limits
            self.pwm = self.pwm + self.PARAM_P * error + self.PARAM_I * integrated_error
            self.pwm = max(self.display.hw.getMinPwm(), min(self.display.hw.getMaxPwm(), self.pwm))
        #endfor

        # Report ranges and deviation errors
        if error > self.uvmeter.INTENSITY_ERROR_THRESHOLD:
            self.logger.error("UV intensity error: %f", error)
            return self.ERROR_TOO_DIMM, None
        elif error < -self.uvmeter.INTENSITY_ERROR_THRESHOLD:
            self.logger.error("UV intensity error: %f", error)
            return self.ERROR_TOO_BRIGHT, None
        elif self.deviation > self.INTENSITY_DEVIATION_THRESHOLD:
            self.logger.error("UV deviation: %f", self.deviation)
            return self.ERROR_TOO_HIGH_DEVIATION, None
        #endif

        data.uvFoundPwm = self.display.hw.uvLedPwm
        return self.ERROR_DONE, data
    #enddef

#endclass


@page
class PageUVCalibrateEdge(PageUvCalibrationThreadBase):
    Name = "uvcalibrateedge"

    def __init__(self, display):
        super(PageUVCalibrateEdge, self).__init__(display)
        self.continuePage = PageUvCalibrationConfirm.Name
    #enddef


    def calibrate(self):
        self.display.screen.blank_screen()
        self.display.screen.inverse()
        maxpwm = self.display.hw.getMaxPwm()
        # check PWM value from previous step
        self.pwm = self.display.hw.uvLedPwm
        while self.pwm <= maxpwm:
            self.display.hw.uvLedPwm = self.pwm
            # Read new intensity value
            data = self.uvmeter.read_data()
            if data is None:
                return self.ERROR_READ_FAILED, None
            else:
                self.minValue = data.uvMinValue if not self.boostResults else data.uvMinValue * self.boostMultiplier
                self.deviation = data.uvStdDev
                data.uvFoundPwm = -1    # for debug log
                self.logger.info("New UV sensor data %s", str(data))
            #endif
            self.logger.info("UV pwm tuning: pwm: %d, minValue: %f", self.pwm, self.minValue)

            # Break cycle when minimal intensity (on the edge) is ok
            if self.minValue >= self.display.hwConfig.uvCalibMinIntEdge:
                break
            #endif
            self.pwm += 1
        #endfor

        # Report ranges
        if self.pwm > maxpwm:
            self.logger.error("UV PWM %d > allowed PWM %d", self.pwm, maxpwm)
            return self.ERROR_TOO_DIMM, None
        elif self.deviation > self.INTENSITY_DEVIATION_THRESHOLD:
            self.logger.error("UV deviation: %f", self.deviation)
            return self.ERROR_TOO_HIGH_DEVIATION, None
        #endif

        data.uvFoundPwm = self.display.hw.uvLedPwm
        return self.ERROR_DONE, data
    #enddef

#endclass


@page
class PageUvCalibrationConfirm(PageUvCalibrationBase):
    Name = "uvcalibrationconfirm"

    def __init__(self, display):
        super(PageUvCalibrationConfirm, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Apply calibration?")
        self.checkCooling = True
        self.checkPowerbutton = False
        self.previousUvPwm = 0
    #enddef


    def prepare(self):
        self.off()
    #enddef


    def show(self):
        if self.display.uvCalibData.uvStdDev > 0.0:
            dev = _("Std dev: %.1f\n") % self.display.uvCalibData.uvStdDev
        else:
            dev = ""
        #endif
        text = _("The printer has been successfully calibrated! You can now open the lid and remove the UV calibrator.\n\n"
                "Would you like to apply the calibration results?")
        if self.display.runtime_config.factory_mode:
            text += _("\nThe result of calibration\n"
                "PWM: %(pwm)d, Intensity: %(int).1f\n"
                "Min value: %(min)d, %(dev)s") \
            % { 'pwm' : self.display.uvCalibData.uvFoundPwm,
                'int' : self.display.uvCalibData.uvMean,
                'min' : self.display.uvCalibData.uvMinValue,
                'dev' : dev,
                }
        self.items.update({
            'text' : text,
            'no_back' : True })
        super(PageUvCalibrationConfirm, self).show()
        self.display.hw.beepRepeat(1)
    #enddef


    def yesButtonRelease(self):
        self.display.state = DisplayState.IDLE

        # save hwConfig
        self.previousUvPwm = self.display.hwConfig.uvPwm
        self.display.hwConfig.uvPwm = self.display.uvCalibData.uvFoundPwm
        self.display.hw.uvLedPwm = self.display.uvCalibData.uvFoundPwm
        del self.display.hwConfig.uvCurrent   # remove old value too
        try:
            self.display.hwConfig.write()
        except ConfigException as exception:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(code=get_exception_code(exception).raw_code)
            return "error"
        #endtry

        # save UV calibration data
        uvCalibConfig = TomlConfig(defines.uvCalibDataPath)
        try:
            uvCalibConfig.data = asdict(self.display.uvCalibData)
            uvCalibConfig.data["uvOsVersion"] = distro.version()
            uvCalibConfig.data["uvMcBoardRev"] = self.display.hw.mcBoardRevision
            uvCalibConfig.data["uvLedCounter"] = self.display.hw.getUvStatistics()
        except AttributeError:
            self.logger.exception("uvCalibData is not completely filled")
            self.display.pages['error'].setParams(code=Sl1Codes.MISSING_UV_CALIBRATION_DATA.raw_code)
            return "error"
        #endtry
        uvCalibConfig.save_raw()
        save_wizard_history(defines.uvCalibDataPath)

        # save to factory partition if needed
        if self.display.runtime_config.factory_mode or PageUvCalibrationBase.writeDataToFactory:
            uvCalibConfigFactory = TomlConfig(defines.uvCalibDataPathFactory)
            uvCalibConfigFactory.data = uvCalibConfig.data
            if self.writeToFactory(functools.partial(self.writeAllDefaults, uvCalibConfigFactory)):
                save_wizard_history(defines.uvCalibDataPathFactory)
            else:
                self.display.pages['error'].setParams(code=Sl1Codes.FAILED_TO_SAVE_FACTORY_DEFAULTS.raw_code)
                return "error"
            #endif
        #endif

        # save counters log
        if PageUvCalibrationBase.resetLedCounter or PageUvCalibrationBase.resetDisplayCounter:
            stats = TomlConfigStats(defines.statsData, self.display.hw)
            stats.load()
            self.logger.info("stats: %s", stats)
            uv_stats = self.display.hw.getUvStatistics()
            countersData = {
                datetime.utcnow().isoformat(): {
                    "started_projects": stats["started_projects"],
                    "finished_projects": stats["finished_projects"],
                    "total_layers": stats["layers"],
                    "total_seconds": stats["total_seconds"],
                    "total_resin": stats["total_resin"],
                    "uvLed_seconds": uv_stats[0],
                    "display_seconds": uv_stats[1],
                    "factoryMode": self.display.runtime_config.factory_mode,
                    "resetDisplayCounter": PageUvCalibrationBase.resetDisplayCounter,
                    "resetUvLedCounter": PageUvCalibrationBase.resetLedCounter,
                    "previousUvPwm": self.previousUvPwm,
                    "newUvPwm": self.display.hwConfig.uvPwm
                }
            }
            self.logger.info("counter data: %s", countersData)
            if self.writeToFactory(functools.partial(self.appendToFile, defines.counterLog, countersData)):
                save_wizard_history(defines.counterLog)
            else:
                self.display.pages['error'].setParams(code=Sl1Codes.FAILED_TO_SAVE_FACTORY_DEFAULTS.raw_code)
                return "error"
            #endif
        #endif

        # reset UV led counter in MC
        if PageUvCalibrationBase.resetLedCounter:
            self.display.hw.clearUvStatistics()
        #endif

        # reset Display counter in MC
        if PageUvCalibrationBase.resetDisplayCounter:
            self.display.hw.clearDisplayStatistics()
        #endif

        return "_EXIT_"
    #enddef


    def writeAllDefaults(self, uvCalibConfigFactory):
        self.saveDefaultsFile()
        uvCalibConfigFactory.save_raw()
    #enddef


    @staticmethod
    def appendToFile(file, data):
        with open(file, "a") as f:
            toml.dump(data, f)
    #enddef


    def noButtonRelease(self):
        self.display.state = DisplayState.IDLE
        return "_EXIT_"
    #enddef

#endclass

@page
class PageUvCalibrationCancel(PageUvCalibrationBase):
    Name = "uvcalibrationcancel"

    def __init__(self, display):
        super(PageUvCalibrationCancel, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Cancel calibration?")
        self.checkPowerbutton = False
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Do you really want to cancel the calibration?\n\n"
                "The machine will not work without going through it.")})
        super(PageUvCalibrationCancel, self).show()
    #enddef


    def yesButtonRelease(self):
        self.display.state = DisplayState.IDLE
        self.off()
        return "_EXIT_"
    #endif


    @staticmethod
    def noButtonRelease():
        return "_NOK_"
    #enddef

#endclass
