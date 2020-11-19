# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.uvcalibration import PageUvCalibrationBase
from sl1fw.pages.wait import PageWait
from sl1fw.pages.infinitetest import PageInfiniteTest


@page
class PageTests(Page):
    Name = "tests"

    def __init__(self, display):
        super(PageTests, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Tests"

    def show(self):
        self.items.update(
            {
                "button1": "Resin sensor test",
                "button2": "UV & Fan test",
                "button3": "Tower sensitivity",
                "button4": "Infinite UV meter test",
                "button6": "Infinite test",
                "button13": "Error - nocode",
                "button14": "Error - code",
                "button15": "Raise exception",
            }
        )
        super(PageTests, self).show()

    def button1ButtonRelease(self):
        self.display.pages["yesno"].setParams(
            yesFce=self.button1Continue,
            text="Is there the correct amount of resin in the tank?\n\n" "Is the tank secured with both screws?",
        )
        return "yesno"

    def button1Continue(self):
        # TODO vyzadovat zavreny kryt po celou dobu!
        self.display.hw.powerLed("warn")
        page_wait = PageWait(self.display, line1="Moving platform to the top")
        page_wait.show()
        retc = self._syncTower()
        if retc == "error":
            return retc

        page_wait.showItems(line1="Tilt home", line2="")
        page_wait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc

        self.display.hw.setTiltProfile("layerMoveSlow")
        self.display.hw.tiltUpWait()

        page_wait.showItems(line1="Measuring", line2="Do NOT TOUCH the printer")
        volume = self.display.hw.get_precise_resin_volume_ml()
        self.display.hw.powerLed("normal")
        if not volume:
            self.display.pages["error"].setParams(
                text="Resin measuring failed!\n\n"
                "Is there the correct amount of resin in the tank?\n\n"
                "Is the tank secured with both screws?"
            )
            return "error"

        self.display.pages["confirm"].setParams(
            continueFce=self.backButtonRelease, text="Measured resin volume: %d ml" % volume,
        )
        return "confirm"

    @staticmethod
    def button2ButtonRelease():
        return "uvfanstest"

    def button6ButtonRelease(self):
        self.display.hw.saveUvStatistics()
        return PageInfiniteTest.Name

    def button13ButtonRelease(self):
        self.display.pages["error"].setParams(
            text=_(
                "Tower home check failed!\n\n"
                "Please contact tech support!\n\n"
                "Tower profiles need to be changed."
            )
        )
        return "error"

    def button14ButtonRelease(self):
        self.display.pages["error"].setParams(
            code=Sl1Codes.UNKNOWN.raw_code,
            text=_(
                "Tower home check failed!\n\n"
                "Please contact tech support!\n\n"
                "Tower profiles need to be changed."
            )
        )
        return "error"

    @staticmethod
    def button15ButtonRelease():
        raise Exception("Test problem")

    def button4ButtonRelease(self):
        wait = PageWait(self.display, line1="Running infinite UV meter test")
        wait.show()

        while True:
            wait.showItems(line2="Connecting uvmeter")
            self.logger.info("Connecting UV meter")
            if not PageUvCalibrationBase.uvmeter.connect():
                self.logger.error("Failed to connect UV meter")
                self.display.pages["error"].setParams(text="Failed to connect")
                return "error"

            for _ in range(5):
                self.logger.info("Reading UV meter data")
                wait.showItems(line2="Reading data")
                if not PageUvCalibrationBase.uvmeter.read():
                    self.logger.error("Failed to read UV meter data")
                    self.display.pages["error"].setParams(text="Failed to read")
                    return "error"

                uv_mean = PageUvCalibrationBase.uvmeter.get_data().uvMean
                self.logger.info("Red data: UVMean: %s", uv_mean)
                wait.showItems(line3=f"Last uvMean = {uv_mean}")

            wait.showItems(line2="Closing uvmeter")
            PageUvCalibrationBase.uvmeter.close()
