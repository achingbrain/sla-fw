# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageTestWizards(Page):
    Name = "testwizards"

    def __init__(self, display):
        super(PageTestWizards, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Wizards"

    def show(self):
        self.items.update({
                'button1' : "Unpacking (C)",
                'button2' : "Unpacking (K)",
                'button3' : "Selftest",
                'button4' : "Calibration",
                })
        super(PageTestWizards, self).show()

    def button1ButtonRelease(self):
        self.display.doMenu("unboxing1")
        return "_SELF_"

    def button2ButtonRelease(self):
        # force page title
        self.display.pages['unboxing4'].pageTitle = N_("Unboxing step 1/1")
        self.display.doMenu("unboxing4")
        return "_SELF_"

    def button3ButtonRelease(self):
        self.display.doMenu("wizardinit")
        return "_SELF_"

    def button4ButtonRelease(self):
        self.display.doMenu("calibrationstart")
        return "_SELF_"
