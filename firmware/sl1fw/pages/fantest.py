# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page, PageWait
from sl1fw import libConfig
from gettext import ngettext
from time import sleep


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
            'text' : _("Make sure all fan air vens are clean and not covered up.")})
        super(PageFanTest, self).show()
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Fans check"), line2 = _("(fans are running)"))
        pageWait.show()
                # TODO rafactoring needed -> fans object(s)
                        #fan1        fan2        fan3
        fanDiff = 200
        hwConfig = libConfig.HwConfig()
        fanLimits = [[hwConfig.fan1Rpm - fanDiff, hwConfig.fan1Rpm + fanDiff], [hwConfig.fan2Rpm - fanDiff, hwConfig.fan2Rpm + fanDiff], [hwConfig.fan3Rpm - fanDiff, hwConfig.fan3Rpm + fanDiff]]
        # TODO measure fans in range of values
        self.display.hw.setFansRpm({ 0 : hwConfig.fan1Rpm, 1 : hwConfig.fan2Rpm, 2 : hwConfig.fan3Rpm })
        self.display.hw.startFans()

        rpm = [[], [], []]
        cnt = defines.fanMeasCycles + defines.fanStartStopTime * 2
        for i in range(cnt):
            if i >= defines.fanStartStopTime * 2: #let the fans spin up and control the rpms
                tmp = self.display.hw.getFansRpm()
                rpm[0].append(tmp[0])   #UV
                rpm[1].append(tmp[1])   #blower
                rpm[2].append(tmp[2])   #rear
            #endif
            cnt -= 1
            pageWait.showItems(line3 = ngettext("Remaining %d second" % cnt,
                    "Remaining %d seconds" % cnt, cnt))
            sleep(1)

            fansState = self.display.hw.getFansError().values()
            if any(fansState):
                failedFans = []
                for num, state in enumerate(fansState):
                    if state:
                        failedFans.append(self.display.hw.getFanName(num))
                    #endif
                #endfor
                self.display.pages['error'].setParams(
                        text = _("Failed: %s\n\n"
                            "Check if fans are connected properly and can rotate without resistance." % ", ".join(failedFans)))
                return "error"
            #endif
        #endfor

        avgRpms = list()
        for i in range(3): #iterate over fans
            rpm[i].remove(max(rpm[i]))
            rpm[i].remove(min(rpm[i]))
            avgRpm = sum(rpm[i]) // len(rpm[i])
            if not fanLimits[i][0] <= avgRpm <= fanLimits[i][1]:
                self.display.pages['error'].setParams(
                    text = _("RPM of %(fan)s not in range!\n\n"
                        "Please check if the fan is connected correctly.\n\n"
                        "RPM data: %(rpm)s avg: %(avg)d")
                    % { 'fan' : self.display.hw.getFanName(i), 'rpm' : rpm[i], 'avg' : avgRpm })
                return "error"
            #endif
            avgRpms.append(avgRpm)
        #endfor

        self.display.wizardData.update(wizardFanRpm = avgRpms)
        return "_BACK_"
    #enddef

    def leave(self):
        self.display.fanErrorOverride = False
        self.display.hw.stopFans()
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass