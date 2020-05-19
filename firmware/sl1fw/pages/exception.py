# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.functions.system import shut_down
from sl1fw.errors.exceptions import MotionControllerException
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageException(Page):
    Name = "exception"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "exception"
        self.pageTitle = N_("System Error")
        self.callbackPeriod = 1

    def show(self) -> None:
        super().show()
        try:
            self.display.hw.powerLed("error")
        except MotionControllerException:
            self.logger.exception("Failed to set power LED mode")

    def callback(self) -> None:
        if self.display.expo and self.display.expo.in_progress:
            return

        self.display.hw.uvLed(False)
        self.display.hw.stopFans()
        self.display.hw.motorsRelease()

        if self.display.hw.getPowerswitchState():
            shut_down(self.display.hw)

    def setParams(self, **kwargs):
        self.items = kwargs

    def backButtonRelease(self):
        return self.Name
