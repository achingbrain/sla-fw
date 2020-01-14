# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from time import sleep

from sl1fw import defines
from sl1fw import libConfig
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageFanTest(Page):
    Name = "fantest"

    def __init__(self, display):
        super(PageFanTest, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Fan test")
        self.stack = False
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Make sure all fan air vents are clean and not blocked."),
            'no_back' : True})
        super(PageFanTest, self).show()
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Fans check"), line2 = _("(fans are running)"))
        pageWait.show()
        # TODO rafactoring needed -> fans object(s)
        # TODO measure fans in range of values
        fanDiff = 200
        hwConfig = libConfig.HwConfig()
        fanLimits = [[hwConfig.fan1Rpm - fanDiff, hwConfig.fan1Rpm + fanDiff], [hwConfig.fan2Rpm - fanDiff, hwConfig.fan2Rpm + fanDiff], [hwConfig.fan3Rpm - fanDiff, hwConfig.fan3Rpm + fanDiff]]
        self.display.hw.setFansRpm({ 0 : hwConfig.fan1Rpm, 1 : hwConfig.fan2Rpm, 2 : hwConfig.fan3Rpm })
        self.display.hw.startFans()

        rpm = [[], [], []]
        cnt = defines.fanMeasCycles + defines.fanStartStopTime
        for i in range(cnt):
            tmp = self.display.hw.getFansRpm()
            rpm[0].append(tmp[0])   #UV
            rpm[1].append(tmp[1])   #blower
            rpm[2].append(tmp[2])   #rear
            cnt -= 1
            pageWait.showItems(line3 = ngettext("Remaining %d second",
                    "Remaining %d seconds",(cnt + 1)) % (cnt + 1))
            sleep(1)
        #endfor

        avgRpms = list()
        fansError = self.display.hw.getFansError()
        for i in range(3): #iterate over fans
            del rpm[i][:defines.fanStartStopTime] #remove first measurements. Let fans spin up
            avgRpm = sum(rpm[i]) // len(rpm[i])
            if not fanLimits[i][0] <= avgRpm <= fanLimits[i][1] or fansError.get(i):
                self.logger.warning("Fans raw RPM: %s", rpm)
                self.logger.warning("FansError: %s", fansError)
                self.display.pages['error'].setParams(
                    text = _("RPM of %(fan)s not in range!\n\n"
                        "Please check if the fan is connected correctly.\n\n"
                        "RPM data: %(rpm)s avg: %(avg)d")
                    % { 'fan' : self.display.hw.getFanName(i), 'rpm' : rpm[i], 'avg' : avgRpm })
                return "error"
            #endif
            avgRpms.append(avgRpm)
        #endfor

        if self.display.wizardData:
            self.display.wizardData.wizardFanRpm = avgRpms
        #endif

        return "_OK_"
    #enddef

    def leave(self):
        self.display.runtime_config.fan_error_override = False
        self.display.hw.stopFans()
    #enddef

#endclass
