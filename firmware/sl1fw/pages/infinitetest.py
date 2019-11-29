# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from time import sleep

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageInfiniteTest(Page):
    Name = "infinitetest"

    def __init__(self, display):
        super(PageInfiniteTest, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Infinite test")
        self.checkCooling = True
    #enddef


    def show(self):
        self.items.update({
            'text' : _("It is strongly recommended to NOT run this test. This is an infinite routine "
            "which tests durability of expostition display and mechanical parts."),
        })
        super(PageInfiniteTest, self).show()
    #enddef


    def contButtonRelease(self):
        towerCounter = 0
        tiltCounter = 0
        towerStatus = 0
        tiltMayMove = True
        towerTargetPosition = 0
        #up = 0
        #above Display = 1
        #down = 3

        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = _("Infinite test"),
            line2 = _("Tower cycles: %d") % towerCounter,
            line3 = _("Tilt cycles: %d") % tiltCounter)
        pageWait.show()
        self.display.screen.getImg(filename = os.path.join(defines.dataPath, "sachovnice16_1440x2560.png"))
        self.display.hw.startFans()
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
        self.display.hw.uvLed(True)
        self.display.hw.towerSync()
        while True:
            if not self.display.hw.isTowerMoving():
                if towerStatus == 0:    #tower moved to top
                    towerCounter += 1
                    pageWait.showItems(line2 = _("Tower cycles: %d") % towerCounter)
                    self.logger.debug("towerCounter: %d, tiltCounter: %d", towerCounter, tiltCounter)
                    if (towerCounter % 100) == 0:   # save uv statistics every 100 tower cycles
                        self.display.hw.saveUvStatistics()
                    #endif
                    self.display.hw.setTowerPosition(0)
                    self.display.hw.setTowerProfile('homingFast')
                    towerTargetPosition = self.display.hw._towerAboveSurface
                    self.display.hw.towerMoveAbsolute(towerTargetPosition)
                    towerStatus = 1
                elif towerStatus == 1:  #tower above the display
                    tiltMayMove = False
                    if self.display.hw.isTiltOnPosition():
                        towerStatus = 2
                        self.display.hw.setTiltProfile('layerMoveSlow')
                        self.display.hw.setTowerProfile('homingSlow')
                        towerTargetPosition = self.display.hw._towerMin
                        self.display.hw.towerMoveAbsolute(towerTargetPosition)
                    #endif
                elif towerStatus == 2:
                    tiltMayMove = True
                    towerTargetPosition = self.display.hw._towerEnd
                    self.display.hw.towerMoveAbsolute(towerTargetPosition)
                    towerStatus = 0
                #endif
            #endif

            if not self.display.hw.isTiltMoving():
                if self.display.hw.getTiltPositionMicroSteps() < 128:   #hack to force tilt to move. Needs MC FW fix. Tilt cannot move up when tower moving
                    self.display.hw.towerStop()
                    self.display.hw.setTiltProfile('homingFast')
                    self.display.hw.tiltUp()
                    self.display.hw.setTowerProfile('homingFast')
                    self.display.hw.towerMoveAbsolute(towerTargetPosition)
                    sleep(1)
                else:
                    if tiltMayMove:
                        tiltCounter += 1
                        pageWait.showItems(line3 = _("Tilt cycles: %d") % tiltCounter)
                        self.display.hw.setTiltProfile('homingFast')
                        self.display.hw.tiltSyncWait()
                    #endif
                #endif
            #endif
            sleep(0.25)
        #endwhile
    #enddef

#endclass
