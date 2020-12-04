# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=no-else-return

from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageError(Page):
    Name = "error"

    def __init__(self, display):
        super(PageError, self).__init__(display)
        self.pageUI = "error"
        self.pageTitle = N_("Error")
        self.stack = False
        self.backFce = None
        self.backParams = {}
    #enddef


    def show(self):
        super(PageError, self).show()
        self.display.hw.powerLed("error")
        self.display.hw.beepAlarm(3)
    #enddef


    def setParams(self, **kwargs):
        self.backFce = kwargs.pop("backFce", None)
        self.backParams = kwargs.pop("backParams", dict())
        self.items = kwargs
    #enddef


    def okButtonRelease(self):
        self.display.hw.powerLed("normal")
        if self.backFce is None:
            return "_EXIT_"
        else:
            return self.backFce(**self.backParams)
        #endif
    #enddef

    @staticmethod
    def gotoSettingsButtonRelease():# TODO remove this hack when we get rid of the websockets
        return "_SETTINGS_"

#endclass
