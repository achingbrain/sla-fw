# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later


# TODO: Fix following pylint problems
# pylint: disable=too-many-statements

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
        self.pageTitle = "Infinite test"
        self.checkCooling = True

    def show(self):
        self.items.update(
            {
                "text": "It is strongly recommended to NOT run this test. This is an infinite routine "
                "which tests durability of exposition display and mechanical parts."
            }
        )
        super(PageInfiniteTest, self).show()

    def contButtonRelease(self):
        tower_counter = 0
        tilt_counter = 0
        tower_status = 0
        tilt_may_move = True
        tower_target_position = 0
        # up = 0
        # above Display = 1
        # down = 3

        self.display.hw.powerLed("warn")
        page_wait = PageWait(
            self.display,
            line1="Infinite test",
            line2="Tower cycles: %d" % tower_counter,
            line3="Tilt cycles: %d" % tilt_counter,
        )
        page_wait.show()
        self.display.screen.getImg(filename=os.path.join(defines.dataPath, "sachovnice16_1440x2560.png"))
        self.display.hw.startFans()
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
        self.display.hw.uvLed(True)
        self.display.hw.towerSync()
        while True:
            if not self.display.hw.isTowerMoving():
                if tower_status == 0:  # tower moved to top
                    tower_counter += 1
                    page_wait.showItems(line2="Tower cycles: %d" % tower_counter)
                    self.logger.info("towerCounter: %d, tiltCounter: %d", tower_counter, tilt_counter)
                    if (tower_counter % 100) == 0:  # save uv statistics every 100 tower cycles
                        self.display.hw.saveUvStatistics()

                    self.display.hw.setTowerPosition(0)
                    self.display.hw.setTowerProfile("homingFast")
                    tower_target_position = self.display.hw.tower_above_surface
                    self.display.hw.towerMoveAbsolute(tower_target_position)
                    tower_status = 1
                elif tower_status == 1:  # tower above the display
                    tilt_may_move = False
                    if self.display.hw.isTiltOnPosition():
                        tower_status = 2
                        self.display.hw.setTiltProfile("layerMoveSlow")
                        self.display.hw.setTowerProfile("homingSlow")
                        tower_target_position = self.display.hw.tower_min
                        self.display.hw.towerMoveAbsolute(tower_target_position)

                elif tower_status == 2:
                    tilt_may_move = True
                    tower_target_position = self.display.hw.tower_end
                    self.display.hw.towerMoveAbsolute(tower_target_position)
                    tower_status = 0

            if not self.display.hw.isTiltMoving():
                # hack to force tilt to move. Needs MC FW fix. Tilt cannot move up when tower moving
                if self.display.hw.getTiltPositionMicroSteps() < 128:
                    self.display.hw.towerStop()
                    self.display.hw.setTiltProfile("homingFast")
                    self.display.hw.tiltUp()
                    self.display.hw.setTowerProfile("homingFast")
                    self.display.hw.towerMoveAbsolute(tower_target_position)
                    sleep(1)
                else:
                    if tilt_may_move:
                        tilt_counter += 1
                        page_wait.showItems(line3="Tilt cycles: %d" % tilt_counter)
                        self.display.hw.setTiltProfile("homingFast")
                        self.display.hw.tiltSyncWait()

            sleep(0.25)
