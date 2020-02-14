# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import json

import distro
import paho.mqtt.publish as mqtt

from sl1fw import defines
from sl1fw.libConfig import TomlConfig
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.calibration import PageCalibrationStart
from sl1fw.pages.uvcalibration import PageUvDataShowFactory, PageUvDataShow, PageUvCalibration


@page
class PageDisplay(Page):
    Name = "display"

    def __init__(self, display):
        super(PageDisplay, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Display"
        self.checkCooling = True
    #enddef


    def show(self):
        state = self.display.hw.getUvLedState()[0]
        self.items.update({
                'button1' : "Chess 8",
                'button2' : "Chess 16",
                'button3' : "Grid 8",
                'button4' : "Grid 16",
                'button5' : "Maze",

                'button6' : "USB:/test.png",
                'button7' : "Prusa logo",
                'button8' : "Black",
                'button9' : "Inverse",
                'button10' : "UV off" if state else "UV on",

                'button11' : "Infinite test",
                "button12" : "Send factory config",
                'button13' : "Show factory UV c.d.",
                'button14' : "Show UV calib. data",
                'button15' : "UV (re)calibration",
                })
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
            self.display.pages['error'].setParams(
                text = "No USB storage present")
            return "error"
        #endif

        test_file = os.path.join(savepath, "test.png")

        if not os.path.isfile(test_file):
            self.display.pages['error'].setParams(
                text = "Cannot find the test image")
            return "error"
        #endif

        try:
            self.display.screen.getImg(filename = test_file)
        except Exception:
            # TODO: This is not reached. Exceptions from screen do not propagate here
            self.logger.exception("Error displaying test image")
            self.display.pages['error'].setParams(
                text = "Cannot display the test image")
            return "error"
        #endtry

    #enddef


    def button7ButtonRelease(self):
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "logo_1440x2560.png"))
    #enddef


    def button8ButtonRelease(self):
        self.display.screen.getImgBlack()
    #enddef


    def button9ButtonRelease(self):
        self.display.screen.inverse()
    #enddef


    def button10ButtonRelease(self):
        state = not self.display.hw.getUvLedState()[0]
        self.showItems(button10 = "UV off" if state else "UV on")
        if state:
            self.display.hw.startFans()
            self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
        else:
            self.display.hw.stopFans()
        #endif

        self.display.hw.uvLed(state)
    #enddef


    def button11ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return "infinitetest"
    #enddef


    def button12ButtonRelease(self):
# FIXME for testing only
#        if self.display.hw.isKit:
#            self.display.pages['error'].setParams(
#                    text = "Factory config will NOT be sent for kit!")
#            return "error"
        #endif

        # Get wizard data
        wizardDict = TomlConfig(defines.wizardDataFile).load()
        if not wizardDict and not (self.display.hw.isKit and self.display.printer0.factory_mode):
            self.display.pages['error'].setParams(
                    backFce = self.gotoWizard,
                    text = _("The wizard did not finish successfully!"))
            return "error"
        #endif

        if not self.display.hwConfig.calibrated and not (self.display.hw.isKit and self.display.printer0.factory_mode):
            self.display.pages['error'].setParams(
                    backFce = self.gotoCalib,
                    text = _("The calibration did not finish successfully!"))
            return "error"
        #endif

        # Get UV calibration data
        calibDict = TomlConfig(defines.uvCalibDataPathFactory).load()
        if not calibDict:
            self.display.pages['error'].setParams(
                    backFce = self.gotoUVcalib,
                    text = _("The automatic UV LED calibration did not finish successfully!"))
            return "error"
        #endif

        # Compose data to single dict, ensure basic data are present
        mqtt_data = {
            "osVersion": distro.version(),
            "a64SerialNo": self.display.hw.cpuSerialNo,
            "mcSerialNo": self.display.hw.mcSerialNo,
            "mcFwVersion": self.display.hw.mcFwVersion,
            "mcBoardRev": self.display.hw.mcBoardRevision,
        }
        mqtt_data.update(wizardDict)
        mqtt_data.update(calibDict)

        # Send data to MQTT
        topic = "prusa/sl1/factoryConfig"
        self.logger.debug("mqtt data: %s", mqtt_data)
        try:
            mqtt.single(topic, json.dumps(mqtt_data), qos=2, retain=True, hostname="mqttstage.prusa")
        except Exception as err:
            self.logger.error("mqtt message not delivered. %s", err)
            self.display.pages['error'].setParams(text = "Cannot send factory config!")
            return "error"
        #endtry

        self.display.pages['confirm'].setParams(
                continueFce = self.success,
                text = "Factory config was successfully sent.")
        return "confirm"
    #enddef

    @staticmethod
    def gotoWizard():
        return "wizardinit"
    #enddef

    @staticmethod
    def gotoCalib():
        return PageCalibrationStart.Name
    #enddef

    @staticmethod
    def gotoUVcalib():
        return PageUvCalibration.Name
    #enddef

    @staticmethod
    def success():
        return "_BACK_"
    #enddef


    def button13ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return PageUvDataShowFactory.Name
    #enddef


    def button14ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return PageUvDataShow.Name
    #enddef


    def button15ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return PageUvCalibration.Name
    #enddef


    def backButtonRelease(self):
        self.display.hw.saveUvStatistics()
        self.allOff()
        return super(PageDisplay, self).backButtonRelease()
    #enddef

#endclass
