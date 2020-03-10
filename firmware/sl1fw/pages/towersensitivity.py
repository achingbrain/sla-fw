# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=no-else-return

from sl1fw.errors.exceptions import ConfigException
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageTowerSensitivity(Page):
    Name = "towersensitivity"

    def __init__(self, display):
        super(PageTowerSensitivity, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Tower sensitivity")
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Tower axis sensitivity needs to be adjusted for realiable homing. This value will be saved in advanced settings."),
            'no_back' : True})
        super(PageTowerSensitivity, self).show()
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Tower axis sensitivity adjust"))
        pageWait.show()
        towerSensitivity = 0    # use default sesnsitivity first
        self.display.hw.updateMotorSensitivity(self.display.hwConfig.tiltSensitivity, towerSensitivity)
        tries = 3
        while tries > 0:
            self.display.hw.towerSyncWait()
            homeStatus = self.display.hw.towerHomingStatus
            if homeStatus == -2:
                self.display.pages['error'].setParams(
                    text = _("Tower endstop not reached!\n\n"
                        "Please check if the tower motor is connected properly."))
                return "error"
            elif homeStatus == -3:  #if homing failed try different tower homing profiles (only positive values of motor sensitivity)
                towerSensitivity += 1   #try next motor sensitivity
                tries = 3   #start over with new sensitivity
                if towerSensitivity >= len(self.display.hw.towerAdjust['homingFast']) - 2:
                    self.display.pages['error'].setParams(
                        text = _("Tower home check failed!\n\n"
                            "Please contact tech support!\n\n"
                            "Tower profiles need to be changed."))
                    return "error"
                else:
                    self.display.hw.updateMotorSensitivity(self.display.hwConfig.tiltSensitivity, towerSensitivity)
                #endif
                continue
            #endif
            tries -= 1
        #endwhile

        if tries == 0:
            self.display.hwConfig.towerSensitivity = towerSensitivity
            self.display.hw.setTowerPosition(self.display.hw.tower_end)
            if self.display.wizardData:
                self.display.wizardData.towerSensitivity = self.display.hwConfig.towerSensitivity
            #endif
            self.display.hwConfig.towerSensitivity = self.display.hwConfig.towerSensitivity

            try:
                self.display.hwConfig.write()
            except ConfigException:
                self.logger.exception("Cannot save wizard configuration")
                self.display.pages['error'].setParams(
                    text=_("Cannot save wizard configuration"))
                return "error"
            #endif
        #endif

        return "_OK_"
    #enddef

#endclass
