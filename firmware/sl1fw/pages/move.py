# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod

from sl1fw.pages import page
from sl1fw.pages.base import Page


class MovePage(Page, ABC):

    @abstractmethod
    def _up(self, slowMoving: bool):
        ...
    #enddef


    @abstractmethod
    def _down(self, slowMoving: bool):
        ...
    #enddef


    @abstractmethod
    def _stop(self):
        ...
    #enddef


    def upfastButton(self):
        self._up(False)
    #enddef


    def upfastButtonRelease(self):
        self._stop()
    #enddef


    def upslowButton(self):
        self._up(True)
    #enddef


    def upslowButtonRelease(self):
        self._stop()
    #enddef


    def downfastButton(self):
        self._down(False)
    #enddef


    def downfastButtonRelease(self):
        self._stop()
    #enddef


    def downslowButton(self):
        self._down(True)
    #enddef


    def downslowButtonRelease(self):
        self._stop()
    #enddef

#endclass


@page
class PageTowerMove(MovePage):
    Name = "towermove"

    def __init__(self, display):
        super(PageTowerMove, self).__init__(display)
        self.pageUI = "towermove"
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
        self.setProfiles = True
    #enddef


    def show(self):
        self.items["value"] = self.display.hw.getTowerPosition()
        self.moving = False
        super(PageTowerMove, self).show()
    #enddef


    def _up(self, slowMoving: bool):
        print("_up")
        if not self.display.hw.tower_move(1 if slowMoving else 2, set_profiles=self.setProfiles):
            self.display.hw.beepAlarm(1)
        self.showItems(value=self.display.hw.getTowerPosition())
    #enddef


    def _down(self, slowMoving: bool):
        print("_down")
        if not self.display.hw.tower_move(-1 if slowMoving else -2, set_profiles=self.setProfiles):
            self.display.hw.beepAlarm(1)
        self.showItems(value=self.display.hw.getTowerPosition())
    #enddef


    def _stop(self):
        print("_stop")
        self.display.hw.tower_move(0, set_profiles=self.setProfiles)
    #enddef


    def changeProfiles(self, setProfiles):
        self.setProfiles = setProfiles
    #enddef

#endclass


@page
class PageTiltMove(MovePage):
    Name = "tiltmove"

    def __init__(self, display):
        super(PageTiltMove, self).__init__(display)
        self.pageUI = "tiltmove"
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
        self.setProfiles = True
    #enddef


    def show(self):
        self.items["value"] = self.display.hw.getTiltPosition()
        super().show()
    #enddef


    def _up(self, slowMoving: bool):
        if not self.display.hw.tilt_move(1 if slowMoving else 2, set_profiles=self.setProfiles):
            self.display.hw.beepAlarm(1)
        self.showItems(value=self.display.hw.getTiltPosition())
    #enddef


    def _down(self, slowMoving: bool):
        if not self.display.hw.tilt_move(-1 if slowMoving else -2, set_profiles=self.setProfiles):
            self.display.hw.beepAlarm(1)
        self.showItems(value=self.display.hw.getTiltPosition())
    #enddef


    def _stop(self):
        self.display.hw.tilt_move(0, set_profiles=self.setProfiles)
    #enddef


    def changeProfiles(self, setProfiles):
        self.setProfiles = setProfiles
    #enddef

#endclass
