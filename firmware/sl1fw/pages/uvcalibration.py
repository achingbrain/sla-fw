# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from dataclasses import asdict
from threading import Thread
from time import sleep
from abc import abstractmethod

from sl1fw import defines
from sl1fw.libConfig import ConfigException, TomlConfig
from sl1fw.display_state import DisplayState
from sl1fw.libUvLedMeterMulti import UvLedMeterMulti, UvMeterState
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


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
            self.display.pages['error'].setParams(
                text = _("No calibration data to show!"))
            return "error"
        #enddef
        self.logger.debug("Generating picture from: %s", str(data))
        imagePath = os.path.join(defines.ramdiskPath, "uvcalib.png")
        if data['uvSensorType'] == 0:
            UvLedMeterMulti().savePic(800, 400, "PWM: %d" % data['uvFoundPwm'], imagePath, data)
            self.setItems(image_path = "file://%s" % imagePath)
        else:
            self.display.pages['error'].setParams(
                text = _("Data is from unknown UV LED sensor!"))
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

    def __init__(self, display):
        super(PageUvCalibrationBase, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("UV LED calibration")
        self.checkCooling = True
    #enddef

    def off(self):
        self.uvmeter.close()
        self.allOff()
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef


    def checkPlacemet(self):
        pageWait = PageWait(self.display, line1 = _("UV calibration"), line2 = _("Checking UV meter placement on the screen"))
        pageWait.show()

        retc = self.uvmeter.checkPlace(self.display.screen.inverse)
        if retc:
            errors = {
                    UvMeterState.ERROR_COMMUNICATION : _("Communication with the UV LED meter has failed.\n\n"
                        "Check the connection and try again."),
                    UvMeterState.ERROR_TRANSLUCENT : _("The UV LED meter detected some light on a dark display. "
                        "This means there is a light 'leak' under the UV meter, or "
                        "your display does not block the UV light enough.\n\n"
                        "Please check the UV meter placement on the screen or "
                        "replace the exposure display."),
                    UvMeterState.ERROR_INTENSITY : _("The UV LED meter failed to read expected UV light intensity.\n\n"
                        "Please check the UV meter placement on the screen."),
                    }
            self.display.pages['error'].setParams(text = errors.get(retc, _("Unknown UV LED meter error code: %d" % retc)))
            self.off()
            return False
        #endif

        return True
    #enddef

    def networkButtonRelease(self):
        self.logger.debug("Network control disabled in uvcalibration")
    #enddef

#endclass


@page
class PageUvCalibration(PageUvCalibrationBase):
    Name = "uvcalibration"

    def prepare(self):
        self.display.state = DisplayState.CALIBRATION
        self.pageWait = PageWait(self.display, line1=_("UV calibration"), line2=_("Setting start positions..."))

        # TODO: Remove this once we do not need to do uvcalibration in factory on a kit
        if self.display.hw.isKit and self.display.printer0.factory_mode:
            # Skip setting of initial positions as the kit not fully assembled at the factory (there is no tower)
            return
        #endif

        self.pageWait.show()

        self.display.hw.towerSync()
        self.display.hw.tiltSync()

        while self.display.hw.isTowerMoving() or self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile

        if not self.display.hw.isTowerSynced():
            self.display.state = DisplayState.IDLE
            self.display.pages['error'].setParams(
                    text = _("Tower homing failed!\n\nCheck the printer's hardware."))
            return "error"
        #endif

        if not self.display.hw.isTiltSynced():
            self.display.state = DisplayState.IDLE
            self.display.pages['error'].setParams(
                    text = _("Tilt homing failed!\n\nCheck the printer's hardware."))
            return "error"
        #endif

        self.display.hw.tiltLayerUpWait()
    #enddef


    def show(self):
        minpwm, maxpwm = self.getMeasPwms()
        text = _("Replace the tank with the UV meter.\n\n"
                "Do NOT remove the UV meter during measurement. "
                "Doing so may expose your eyes to harmful UV radiation.\n\n"
                "Connect the UV meter to the USB port.")
        if self.display.runtime_config.factory_mode:
            text += _("\n\nCenter intensity: %(cint)d\n"
                "Minimal edge intensity: %(eint)d\n"
                "Warm-up time: %(time)d seconds\n"
                "PWM range: <%(minp)d, %(maxp)d>") \
            % { 'cint' : self.display.hwConfig.uvCalibIntensity,
                'eint' : self.display.hwConfig.uvCalibMinIntEdge,
                'time' : self.display.hwConfig.uvWarmUpTime,
                'minp' : minpwm,
                'maxp' : maxpwm,
                }
        #endif
        self.items.update({ 'text' : text })
        super(PageUvCalibration, self).show()
        self.display.hw.beepRepeat(1)
    #enddef


    def contButtonRelease(self):
        if not self.checkUVMeter():
            self.allOff()
            self.display.state = DisplayState.IDLE
            return "error"
        #endif
        self.warmUp()
        return PageUVCalibrateCenter.Name
    #enddef


    def backButtonRelease(self):
        self.display.state = DisplayState.IDLE
        return self._BACK_()
    #enddef


    def checkUVMeter(self):
        self.pageWait.showItems(line2 = _("Waiting for UV meter"))
        self.pageWait.show()
        for i in range(0, defines.uvLedMeterMaxWait_s):
            self.pageWait.showItems(line3 = "%d/%d s" % (i, defines.uvLedMeterMaxWait_s))
            if self.uvmeter.present:
                break
            #endif
            sleep(1)
        #endfor
        self.pageWait.showItems(line3 = "")

        if not self.uvmeter.present:
            self.display.pages['error'].setParams(text =
                    _("The UV LED meter is not detected.\n\nCheck the connection and try again."))
            return False
        #endif
        self.pageWait.showItems(line2 = _("Connecting to the UV meter"))
        if not self.uvmeter.connect():
            self.display.pages['error'].setParams(text =
                    _("Cannot connect to the UV LED meter.\n\nCheck the connection and try again."))
            return False
        #endif

        return True
    #enddef


    def warmUp(self):
        self.pageWait.showItems(line2 = _("Warming up"))

        self.display.hw.startFans()
        self.display.hw.uvLedPwm = self.getMaxPwm()
        self.display.screen.getImgBlack()
        self.display.hw.uvLed(True)

        for countdown in range(self.display.hwConfig.uvWarmUpTime, 0, -1):
            self.pageWait.showItems(line3 = ngettext("Remaining %d second",
                "Remaining %d seconds", countdown) % countdown)
            sleep(1)
        #endfor

        self.display.hw.uvLedPwm = self.getMinPwm()
    #enddef


    def _BACK_(self):
        self.off()
        return "_BACK_"
    #enddef

#endclass


class PageUvCalibrationThreadBase(PageUvCalibrationBase):

    ERROR_DONE = 0
    ERROR_READ_FAILED = 1
    ERROR_TOO_BRIGHT = 2
    ERROR_TOO_DIMM = 3
    ERROR_TOO_HIGH_DEVIATION = 4
    INTENSITY_DEVIATION_THRESHOLD = 20


    def __init__(self, display):
        super(PageUvCalibrationThreadBase, self).__init__(display)
        self.pageUI = "wait"
        self.pageTitle = N_("Please wait")
        self.continuePage = None
        self.pwm = None
        self.intensity = None
        self.minValue = None
        self.deviation = 2 * self.INTENSITY_DEVIATION_THRESHOLD
        self.updated = False
    #enddef


    def prepare(self):
        if not self.checkPlacemet():
            return "error"
        #endif

        self.intensity = None
        self.minValue = None
        self.deviation = 2 * self.INTENSITY_DEVIATION_THRESHOLD
        self.updated = False
        self.display.uvcalibData = None

        self.setItems(line1 = _("UV calibration"), line2 = _("Calibrating UV LED power"))

        # TODO Concurent.futures would allow us to pass errors as exceptions
        self.result = None
        self.thread = Thread(target = self.calibrate_thread)
        self.thread.start()
    #enddef


    def calibrate_thread(self):
        self.result, self.display.uvcalibData = self.calibrate()
    #enddef


    @abstractmethod
    def calibrate(self):
        ...
    #enddef


    def callback(self):
        if self.updated:
            line = _("PWM: %d") % self.pwm
            if self.intensity is not None:
                line += _(", intensity: %.1f") % self.intensity
            #endif
            if self.minValue is not None:
                line += _(", min. int.: %d") % self.minValue
            #endif
            if self.deviation > 0.0:
                line += _(", deviation: %.1f") % self.deviation
            #endif
            self.showItems(line3 = line)
            self.updated = False
        #endif

        retc = super(PageUvCalibrationThreadBase, self).callback()
        if retc:
            return retc
        #endif

        if self.thread.is_alive():
            return
        #endif

        self.display.screen.getImgBlack()

        if self.result == self.ERROR_DONE:
            return self.continuePage
        #endif

        errors = {
                self.ERROR_READ_FAILED : \
                    _("Cannot read data from the UV LED meter.\n\nCheck the connection and try again."),
                self.ERROR_TOO_BRIGHT : \
                    _("Requested intensity cannot be reached by min. allowed PWM"),
                self.ERROR_TOO_DIMM : \
                    _("Requested intensity cannot be reached by max. allowed PWM"),
                self.ERROR_TOO_HIGH_DEVIATION : \
                    _("The correct settings was found but standard deviation "
                            "(%(found).1f) is greater than allowed value (%(allow).1f)."
                            "\n\nVerify the UV LED meter position and calibration,"
                            " then try again.") %
                    { 'allow' : self.INTENSITY_DEVIATION_THRESHOLD, 'found' : self.deviation },
                }

        self.display.pages['error'].setParams(text = errors.get(self.result,
            _("Unknown UV calibration error: %s") % str(self.result)))
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
        self.pwm = self.getMinPwm()

        error = 0
        integrated_error = 0
        success_count = 0

        # Calibrate LED Power
        for iteration in range(0, self.TUNNING_ITERATIONS):
            self.display.hw.uvLedPwm = self.pwm
            # Read new intensity value
            data = self.uvmeter.readData()
            if data is None:
                return self.ERROR_READ_FAILED, None
            else:
                self.intensity = data.uvMean
                self.deviation = data.uvStdDev
                self.updated = True
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
            self.pwm = max(self.getMinPwm(), min(self.getMaxPwm(), self.pwm))
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
        maxpwm = self.getMaxPwm()
        # check PWM value from previous step
        self.pwm = self.display.hw.uvLedPwm
        while self.pwm <= maxpwm:
            self.display.hw.uvLedPwm = self.pwm
            # Read new intensity value
            data = self.uvmeter.readData()
            if data is None:
                return self.ERROR_READ_FAILED, None
            else:
                self.minValue = data.uvMinValue
                self.deviation = data.uvStdDev
                self.updated = True
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
class PageUvCalibrationConfirm(Page):
    Name = "uvcalibrationconfirm"

    def __init__(self, display):
        super(PageUvCalibrationConfirm, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Apply calibration?")
        self.checkCooling = True
        self.checkPowerbutton = False
    #enddef


    def prepare(self):
        self.allOff()
    #enddef


    def show(self):
        if self.display.uvcalibData.uvStdDev > 0.0:
            dev = _("Standard deviation: %.1f\n") % self.display.uvcalibData.uvStdDev
        else:
            dev = ""
        #endif
        self.items.update({
            'text' : _("The result of calibration\n"
                "PWM: %(pwm)d\n"
                "Intensity: %(int).1f\n"
                "Minimal value: %(min)d\n"
                "%(dev)s\n"
                "Would you like to apply the calibration?")
            % { 'pwm' : self.display.uvcalibData.uvFoundPwm,
                'int' : self.display.uvcalibData.uvMean,
                'min' : self.display.uvcalibData.uvMinValue,
                'dev' : dev,
                }})
        super(PageUvCalibrationConfirm, self).show()
        self.display.hw.beepRepeat(1)
    #enddef


    def yesButtonRelease(self):
        self.display.state = DisplayState.IDLE
        self.display.hwConfig.uvPwm = self.display.uvcalibData.uvFoundPwm
        del self.display.hwConfig.uvCurrent   # remove old value too
        try:
            self.display.hwConfig.write()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text=_("Cannot save configuration"))
            return "error"
        #endtry
        self.uvcalibConfig = TomlConfig(defines.uvCalibDataPath)
        try:
            self.uvcalibConfig.data = asdict(self.display.uvcalibData)
        except AttributeError:
            self.logger.exception("uvcalibData is not completely filled")
            self.display.pages['error'].setParams(
                text = _("!!! Failed to serialize calibration data !!!"))
            return "error"
        #endtry
        self.uvcalibConfig.save_raw()
        if self.display.factory_mode:
            self.uvcalibConfigFactory = TomlConfig(defines.uvCalibDataPathFactory)
            self.uvcalibConfigFactory.data = self.uvcalibConfig.data
            if not self.writeToFactory(self.writeAllDefaults):
                self.display.pages['error'].setParams(
                    text = _("!!! Failed to save factory defaults !!!"))
                return "error"
            #endif
        #endif
        return "_BACK_"
    #enddef


    def writeAllDefaults(self):
        self.saveDefaultsFile()
        self.uvcalibConfigFactory.save_raw()
    #enddef


    def noButtonRelease(self):
        self.display.state = DisplayState.IDLE
        return "_BACK_"
    #enddef

#endclass
