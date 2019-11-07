# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageSysInfo(Page):
    Name = "sysinfo"

    def __init__(self, display):
        super(PageSysInfo, self).__init__(display)
        self.pageUI = "sysinfo"
        self.checkPowerbutton = False

    def show(self):
        self.display.hw.resinSensor(True)
        super().show()

    def backButtonRelease(self):
        self.display.hw.resinSensor(False)
        return super().backButtonRelease()
