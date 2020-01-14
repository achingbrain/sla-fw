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


class PageTilting(PagePrintBase):
    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"

    def callback(self):
        self.showItems(line2="%.3f" % self.display.expo.hw.tilt_position)
        return super().callback()


@page
class PageTiltingUp(PageTilting):
    Name = "tiltingup"

    def __init__(self, display):
        super().__init__(display)
        self.pageTitle = N_("Going up")

    def show(self):
        self.setItems(line1=_("Moving tilt up"))
        super().show()


@page
class PageTiltingDown(PageTilting):
    Name = "tiltingdown"

    def __init__(self, display):
        super().__init__(display)
        self.pageTitle = N_("Tilting down")

    def show(self):
        self.setItems(line1=_("Moving tilt down"), line2="")
        super().show()
