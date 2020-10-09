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
class PageConfirm(Page):
    Name = "confirm"

    def __init__(self, display):
        super(PageConfirm, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Confirm")
        self.stack = False
        self.continueFce = None
        self.continueParams = {}
        self.backFce = None
        self.backParams = {}
        self.beep = False
    #enddef


    def setParams(self, **kwargs):
        self.continueFce = kwargs.pop("continueFce", None)
        self.continueParams = kwargs.pop("continueParams", dict())
        self.backFce = kwargs.pop("backFce", None)
        self.backParams = kwargs.pop("backParams", dict())
        self.beep = kwargs.pop("beep", False)
        self.pageTitle = kwargs.pop("pageTitle", N_("Confirm"))
        self.items = kwargs
    #enddef


    def show(self):
        super(PageConfirm, self).show()
        if self.beep:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def contButtonRelease(self):
        if self.continueFce is None:
            return "_EXIT_"
        else:
            return self.continueFce(**self.continueParams)
        #endif
    #enddef


    def backButtonRelease(self):
        if self.backFce is None:
            return super(PageConfirm, self).backButtonRelease()
        else:
            return self.backFce(**self.backParams)
        #endif
    #enddef

#endclass