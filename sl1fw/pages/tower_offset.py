# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.errors.exceptions import ConfigException, get_exception_code
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageTowerOffset(Page):
    Name = "toweroffset"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "towermovecalibration"
        self.stack = False
        self.autorepeat = { "upslow" : (3, 1), "downslow" : (3, 1) }
        self.tmpTowerOffset = None
    #enddef


    def show(self):
        self.tmpTowerOffset = self.display.hwConfig.calibTowerOffset
        self.items["value"] = self._strOffset(self.tmpTowerOffset)
        super(PageTowerOffset, self).show()
    #enddef


    def __value(self, change):
        if -400 <= self.tmpTowerOffset + change <= 400:
            self.tmpTowerOffset += change
            self.showItems(**{ 'value' : self._strOffset(self.tmpTowerOffset) })
        else:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def upslowButton(self):
        self.__value(1)
    #enddef


    def upslowButtonRelease(self):
        pass
    #enddef


    def downslowButton(self):
        self.__value(-1)
    #enddef


    def downslowButtonRelease(self):
        pass
    #enddef


    def okButtonRelease(self):
        self.display.hwConfig.calibTowerOffset = self.tmpTowerOffset
        try:
            self.display.hwConfig.write()
        except ConfigException as exception:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(code=get_exception_code(exception).raw_code)
            return "error"
        #endtry
        return "_BACK_"
    #enddef

#endclass
