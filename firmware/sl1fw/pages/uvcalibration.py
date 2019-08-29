# part of SL1 firmware
# -*- coding: utf-8 -*-
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
from time import sleep
from time import monotonic

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page, PageWait


@page
class PageUvCalibration(Page):
    Name = "uvcalibration"

    def __init__(self, display):
        super(PageUvCalibration, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("UV LED calibration")
        self.checkCooling = True
    #enddef


    def show(self):
        self.getMeasPwms()
        self.items.update({
            'text' : _("This will calibrate the UV LED (intensity %(int)d,"
            " temperature %(temp)d °C, range <%(minp)d, %(maxp)d>).\n\n"
            "Calibrated UV LED meter connected to the USB port will be required after warm up.")
            % { 'int' : self.display.hwConfig.uvCalibIntensity,
                'temp' : self.display.hwConfig.uvCalibTemp,
                'minp' : self.measMinPwm,
                'maxp' : self.measMaxPwm,
                }})
        super(PageUvCalibration, self).show()
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display,
            line1 = _("UV calibration"),
            line2 = _("Warming up to %d °C") % self.display.hwConfig.uvCalibTemp)
        pageWait.show()

        self.display.hw.startFans()
        self.display.hw.uvLedPwm = self.measMaxPwm
        self.display.screen.getImgBlack()
        self.display.screen.inverse()
        self.display.hw.uvLed(True)

        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.tiltLayerUpWait()

        temp = -1
        while temp < self.display.hwConfig.uvCalibTemp:
            temp = self.display.hw.getUvLedTemperature()
            pageWait.showItems(line3 = _("Actual temperature: %.1f °C") % temp)
            sleep(1)
        #endwhile

        self.display.pages['confirm'].setParams(
                continueFce = self.contButtonContinue,
                text = _("Connect the UV LED meter and wait few seconds."))
        return "confirm"
    #enddef


    def contButtonContinue(self):
        return "uvmeter"
    #enddef


    def off(self):
        self.allOff()
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
    #enddef


    def _EXIT_(self):
        self.off()
        return "_EXIT_"
    #enddef


    def _BACK_(self):
        self.off()
        return "_BACK_"
    #enddef

#endclass


@page
class PageUvMeterShow(Page):
    Name = "uvmetershow"

    def __init__(self, display):
        super(PageUvMeterShow, self).__init__(display)
        self.pageUI = "picture"
        self.pageTitle = N_("UV LED calibration")
        self.checkCooling = True
        from sl1fw.libUvLedMeter import UvLedMeter
        self.uvmeter = UvLedMeter()
    #enddef


    def generatePicture(self, data):
        imagePath = os.path.join(defines.ramdiskPath, "uvcalib.png")
        self.uvmeter.savePic(800, 400, "PWM: %d" % data['uvFoundPwm'], imagePath, data)
        self.setItems(image_path = "file://%s" % imagePath)
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef

#endclass


@page
class PageUvCalibrationTest(PageUvMeterShow):
    Name = "uvcalibrationtest"

    def prepare(self):
        if self.display.wizardData.uvFoundPwm < 1:
            return "uvcalibration"
        #enddef
        self.generatePicture(self.display.wizardData.getDict())
    #enddef


    def backButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.toCalibration,
                pageTitle = N_("Recalibrate?"),
                text = _("The UV LED is already calibrated.\n\n"
                    "Would you like to recalibrate?"))
        return "yesno"
    #enddef


    def toCalibration(self):
        return "uvcalibration"
    #enddef


    def _NOK_(self):
        return "_BACK_"
    #enddef

#endclass


@page
class PageUvMeter(PageUvMeterShow):
    Name = "uvmeter"

    def prepare(self):
        pageWait = PageWait(self.display,
            line1 = _("UV calibration"),
            line2 = _("Connecting to the UV LED meter"))
        pageWait.show()

        if not self.uvmeter.connect():
            self.display.pages['error'].setParams(text = _("The UV LED meter is not "
                "detected.\n\nCheck the connection and try again."))
            self.allOff()
            return "error"
        #endif

        pageWait.showItems(line2 = _("Reading data"))
        if not self.uvmeter.read():
            self.display.pages['error'].setParams(text = _("Cannot read data from the UV LED meter."
                "\n\nCheck the connection and try again."))
            self.allOff()
            self.uvmeter.close()
            return "error"
        #endif

        realPwm = self.display.hw.uvLedPwm
        data = self.uvmeter.getData()
        self.logger.info("UV calibration - PWM:%d data:%s", realPwm, str(data))

        if data['uvMean'] < self.display.hwConfig.uvCalibIntensity:
            self.display.pages['error'].setParams(text = _("Requested intensity "
                "cannot be reached by max. allowed PWM (weak UV LED?).\n\n"
                "Change the values and try again."))
            self.allOff()
            self.uvmeter.close()
            return "error"
        #endif

        imagePath = os.path.join(defines.ramdiskPath, "uvcalib-%d.png" % realPwm)
        self.uvmeter.savePic(800, 400, "PWM: %d" % realPwm, imagePath, data)
        self.setItems(image_path = "file://%s" % imagePath)

        self.getMeasPwms()
        self.topPwm = self.measMaxPwm
        self.bottomPwm = self.measMinPwm
        self.testPwm = self.bottomPwm
        self.display.hw.uvLedPwm = self.testPwm
        self.lastCallback = monotonic()
        self.iterCnt = 15
        self.finalTest = False
    #enddef


    def callback(self):
        retc = super(PageUvMeter, self).callback()
        if retc:
            return retc
        #endif

        if monotonic() - self.lastCallback < 3.0:
            return
        #endif

        realPwm = self.display.hw.uvLedPwm
        if not self.uvmeter.read():
            self.display.pages['error'].setParams(text = _("Cannot read data from the UV LED meter."
                "\n\nCheck the connection and try again."))
            self.allOff()
            self.uvmeter.close()
            return "error"
        #endif
        data = self.uvmeter.getData()
        self.logger.info("UV calibration - finalTest:%s PWM:%d data:%s",
                "yes" if self.finalTest else "no", realPwm, str(data))

        if self.finalTest:
            self.allOff()
            self.uvmeter.close()
            if data['uvMean'] > 1.0 or data['uvMaxValue'] > 2:
                self.display.wizardData.parseFile(defines.wizardDataFile)
                self.display.pages['error'].setParams(text = _("The exposure display "
                    "do not block the UV light enough. Replace it please."))
                return "error"
            #endif
            return "uvcalibrationconfirm"
        #endif

        if int(self.testPwm) == int(self.bottomPwm) and data['uvMean'] > self.display.hwConfig.uvCalibIntensity:
            self.display.pages['error'].setParams(text = _("Requested intensity "
                "cannot be reached by min. allowed PWM (jammed UV meter?).\n\n"
                "Change the values and try again."))
            self.allOff()
            self.uvmeter.close()
            return "error"
        #endif

        imagePath = os.path.join(defines.ramdiskPath, "uvcalib-%d.png" % realPwm)
        self.uvmeter.savePic(800, 400, "PWM: %d" % realPwm, imagePath, data)
        self.showItems(image_path = "file://%s" % imagePath)

        if int(round(data['uvMean'])) == self.display.hwConfig.uvCalibIntensity:
            if data['uvStdDev'] > 20.0:
                self.display.pages['error'].setParams(text = _("The correct settings "
                    "was found but standard deviation (%.1f) is greater than "
                    "allowed value (20.0).\n\nVerify the UV LED meter position "
                    "and calibration, then try again.") % data['uvStdDev'])
                self.allOff()
                self.uvmeter.close()
                return "error"
            #endif

            self.display.wizardData.update(**data)
            self.display.wizardData.update(uvFoundPwm = realPwm)
            self.display.screen.getImgBlack()
            self.finalTest = True
            self.lastCallback = monotonic()
            return
        #endif

        self.iterCnt -= 1
        if not self.iterCnt:
            self.display.pages['error'].setParams(text = _("Cannot find the correct "
                "settings for the specified intensity.\n\nVerify the UV LED "
                "meter position and calibration or change the values, then try "
                "again."))
            self.allOff()
            self.uvmeter.close()
            return "error"
        #endif

        if data['uvMean'] < self.display.hwConfig.uvCalibIntensity:
            self.bottomPwm = self.testPwm
        else:
            self.topPwm = self.testPwm
        #endif

        self.testPwm = (self.topPwm - self.bottomPwm) // 2 + self.bottomPwm
        self.display.hw.uvLedPwm = self.testPwm
        self.lastCallback = monotonic()
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


    def show(self):
        self.items.update({
            'text' : _("The result of calibration\nPWM: %(pwm)d\n"
                "Intensity: %(int).1f\n"
                "Standard deviation: %(dev).1f\n\n"
                "Would you like to apply the calibration?")
            % { 'pwm' : self.display.wizardData.uvFoundPwm,
                'int' : self.display.wizardData.uvMean,
                'dev' : self.display.wizardData.uvStdDev,
                }})
        super(PageUvCalibrationConfirm, self).show()
    #enddef


    def yesButtonRelease(self):
        self.display.hwConfig.update(uvPwm = self.display.wizardData.uvFoundPwm)
        if not self.display.hwConfig.writeFile():
            self.display.pages['error'].setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        if not self.writeToFactory(self.writeAllDefaults):
            self.display.pages['error'].setParams(
                text = _("!!! Failed to save factory defaults !!!"))
            return "error"
        #endif
        return "_BACK_"
    #enddef


    def writeAllDefaults(self):
        self.saveDefaultsFile()
        self.display.wizardData.writeFile()
    #enddef


    def noButtonRelease(self):
        self.display.wizardData.parseFile(defines.wizardDataFile)
        return "_BACK_"
    #enddef

#endclass
