# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw.pages import page
from sl1fw.pages.print.base import PagePrintBase

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


class PageGoing(PagePrintBase):
    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"

    def callback(self):
        pos_mm = self.display.expo.hw.tower_position_nm / 1000000
        self.showItems(line2="%.3f mm" % pos_mm)
        return super().callback()


@page
class PageGoingUp(PageGoing):
    Name = "goingup"

    def __init__(self, display):
        super().__init__(display)
        self.pageTitle = N_("Going up")

    def show(self):
        self.setItems(line1=_("Moving tower to the top position"))

        if self.display.expo.exception:
            self.setItems(line2=_("There is a problem with platform position"), line3=_("Moving platform up"))
        super().show()


@page
class PageGoingDown(PageGoing):
    Name = "goingdown"

    def __init__(self, display):
        super().__init__(display)
        self.pageTitle = N_("Going down")

    def show(self):
        self.setItems(line1=_("Moving tower down"), line2="")
        super().show()
