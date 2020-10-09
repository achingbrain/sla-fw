# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=no-else-return
# pylint: disable=too-many-instance-attributes

from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageYesNo(Page):
    Name = "yesno"

    def __init__(self, display):
        super(PageYesNo, self).__init__(display)
        self.pageUI = "yesno"
        self.stack = False
        self.checkPowerbutton = False
        self.yesFce = None
        self.yesParams = {}
        self.noFce = None
        self.noParams = {}
        self.beep = False
    #enddef


    def setParams(self, **kwargs):
        self.yesFce = kwargs.pop("yesFce", None)
        self.yesParams = kwargs.pop("yesParams", dict())
        self.noFce = kwargs.pop("noFce", None)
        self.noParams = kwargs.pop("noParams", dict())
        self.beep = kwargs.pop("beep", False)
        self.pageTitle = kwargs.pop("pageTitle", N_("Are you sure?"))
        self.items = kwargs
    #enddef


    def show(self):
        super().show()
        if self.beep:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def yesButtonRelease(self):
        if self.yesFce is None:
            return "_OK_"
        else:
            return self.yesFce(**self.yesParams)
        #endif
    #enddef


    def noButtonRelease(self):
        if self.noFce is None:
            return "_NOK_"
        else:
            return self.noFce(**self.noParams)
        #endif
    #enddef

#endclass