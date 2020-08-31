# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements

from sl1fw.errors.errors import UVLEDHeatsinkFailed, FanRPMOutOfTestRange
from sl1fw.functions.checks import check_uv_leds, check_uv_fans
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageUvFansTest(Page):
    Name = "uvfanstest"

    def __init__(self, display):
        super(PageUvFansTest, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("UV & Fans test")
        self.stack = False
        self.checkCooling = True

    def show(self):
        self.items.update({"text": _("Make sure all fan air vents are clean and not blocked."), "no_back": True})
        super(PageUvFansTest, self).show()

    def contButtonRelease(self):
        self.ensureCoverIsClosed()

        # UV LED voltage comparation
        pageWait = PageWait(self.display, line1=_("UV LED check"), line2=_("Please wait..."))
        pageWait.show()

        row1, row2, row3 = check_uv_leds(self.display.hw)

        if self.display.wizardData:
            self.display.wizardData.wizardUvVoltageRow1 = row1
            self.display.wizardData.wizardUvVoltageRow2 = row2
            self.display.wizardData.wizardUvVoltageRow3 = row3

        pageWait.showItems(line2=_("Fans check"))
        try:
            avg_rpms, uv_temp = check_uv_fans(self.display.hw, self.display.hwConfig, self.logger)
        except UVLEDHeatsinkFailed as e:
            self.display.pages["error"].setParams(
                text=_(
                    "UV LED too hot!\n\n"
                    "Please check if the UV LED panel is attached to the heatsink.\n\n"
                    "Temperature data: %s"
                )
                % e.uv_temp_deg_c
            )
            return "error"
        except FanRPMOutOfTestRange as e:
            self.display.pages["error"].setParams(
                text=_(
                    "RPM of %(fan)s not in range!\n\n"
                    "Please check if the fan is connected correctly.\n\n"
                    "RPM data: %(rpm)s\n"
                    "Average: %(avg)s\n"
                    "Fan error: %(fanError)s"
                )
                % {
                    "fan": e.name,
                    "rpm": e.rpm if e.rpm else "NA",
                    "avg": e.avg if e.avg else "NA",
                    "fanError": e.fanError,
                }
            )
            return "error"

        if self.display.wizardData:
            self.display.wizardData.wizardFanRpm = avg_rpms
            self.display.wizardData.wizardTempUvWarm = uv_temp
        return "_OK_"

    def leave(self):
        self.display.fanErrorOverride = False
        self.display.hw.uvLed(False)
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
        if not self.display.wizardData:
            self.display.hw.stopFans()  # stop fans only if not in wizard
