# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements

from time import sleep

from sl1fw import defines
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
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Make sure all fan air vents are clean and not blocked."),
            'no_back' : True})
        super(PageUvFansTest, self).show()
    #enddef


    def contButtonRelease(self):
        self.ensureCoverIsClosed()

        # UV LED voltage comparation
        pageWait = PageWait(self.display, line1 = _("UV LED check"), line2 = _("Please wait..."))
        pageWait.show()

        self.display.hw.uvLedPwm = 0
        self.display.hw.uvLed(True)
        if self.display.hw.is500khz:
            uvPwms = [40, 122, 243, 250]    # board rev 0.6c+
        else:
            uvPwms = [31, 94, 188, 219]     # board rev. < 0.6c
        #endif
        diff = 0.55    # [mV] voltages in all rows cannot differ more than this limit
        row1 = list()
        row2 = list()
        row3 = list()
        for i in range(3):
            self.display.hw.uvLedPwm = uvPwms[i]
            sleep(5)    # wait to refresh all voltages (board rev. 0.6+)
            volts = self.display.hw.getVoltages()
            del volts[-1]   # delete power supply voltage
            if max(volts) - min(volts) > diff:
                self.display.hw.uvLed(False)
                self.display.pages['error'].setParams(
                    text = _("UV LED voltages differ too much!\n\n"
                        "Please check if the UV LED panel is connected properly.\n\n"
                        "Data: %(pwm)d, %(value)s V") % { 'pwm' : uvPwms[i], 'value' : volts})
                return "error"
            #endif
            row1.append(int(volts[0] * 1000))
            row2.append(int(volts[1] * 1000))
            row3.append(int(volts[2] * 1000))
        #endfor
        if self.display.wizardData:
            self.display.wizardData.wizardUvVoltageRow1 = row1
            self.display.wizardData.wizardUvVoltageRow2 = row2
            self.display.wizardData.wizardUvVoltageRow3 = row3
        #endif

        pageWait.showItems(line2 = _("Fans check"))
        fanDiff = 200
        self.display.hw.startFans()
        rpm = [[], [], []]
        fansWaitTime = defines.fanWizardStabilizeTime + defines.fanStartStopTime

        #set UV LED to max PWM
        self.display.hw.uvLedPwm = uvPwms[3]

        for countdown in range(self.display.hwConfig.uvWarmUpTime, 0, -1):
            pageWait.showItems(line3 = ngettext("Remaining %d second",
                    "Remaining %d seconds", countdown) % countdown)

            uvTemp = self.display.hw.getUvLedTemperature()
            if uvTemp > defines.maxUVTemp:
                break
            #endif
            if any(self.display.hw.getFansError().values()):
                break
            #endif

            if fansWaitTime < self.display.hwConfig.uvWarmUpTime - countdown:
                actualRpm = self.display.hw.getFansRpm()
                for i in self.display.hw.fans:
                    rpm[i].append(actualRpm[i])
                #endfor
            #endif
            sleep(1)
        #endfor
        self.display.hw.uvLed(False)

        #evaluate fans data
        avgRpms = list()
        fanError = self.display.hw.getFansError()
        for i, fan in self.display.hw.fans.items(): #iterate over fans
            if len(rpm[i]) == 0:
                rpm[i].append(fan.targetRpm)
            #endif
            avgRpm = sum(rpm[i]) / len(rpm[i])
            if not fan.targetRpm - fanDiff <= avgRpm <= fan.targetRpm + fanDiff or fanError[i]:
                self.logger.error("Fans raw RPM: %s", rpm)
                self.logger.error("Fans error: %s", fanError)
                self.logger.error("Fans samples: %s", len(rpm[i]))
                self.display.pages['error'].setParams(
                    text = _("RPM of %(fan)s not in range!\n\n"
                        "Please check if the fan is connected correctly.\n\n"
                        "RPM data: %(rpm)s\n"
                        "Average: %(avg)s\n"
                        "Fan error: %(fanError)s")
                        % { 'fan' : fan.name,
                            'rpm' : str(min(rpm[i]))+"-"+str(max(rpm[i])) if len(rpm[i]) > 1 else "NA",
                            'avg' : round(avgRpm) if len(rpm[i]) > 1 else "NA",
                            'fanError' : fanError })
                return "error"
            #endif
            avgRpms.append(avgRpm)
        #endfor

        #evaluate UV LED data
        if uvTemp > defines.maxUVTemp:
            self.display.pages['error'].setParams(
                text = _("UV LED too hot!\n\n"
                    "Please check if the UV LED panel is attached to the heatsink.\n\n"
                    "Temperature data: %s") % uvTemp)
            return "error"
        #endif

        if self.display.wizardData:
            self.display.wizardData.wizardFanRpm = avgRpms
            self.display.wizardData.wizardTempUvWarm = uvTemp
        #endif
        return "_OK_"
    #enddef

    def leave(self):
        self.display.fanErrorOverride = False
        self.display.hw.uvLed(False)
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
        if not self.display.wizardData:
            self.display.hw.stopFans()  #stop fans only if not in wizard
        #endif
    #enddef

#endclass
