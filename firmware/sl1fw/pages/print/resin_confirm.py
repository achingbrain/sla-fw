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


@page
class PageResinConfirm(PagePrintBase):
    Name = "resinconfirm"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Performing pre-print checks")

    def show(self):
        self.setItems(
            text=_(
                "Your resin volume is approx %(measured)d %%\n\n"
                "For your project, %(requested)d %% is needed. A refill may be required during printing."
            )
            % {
                "measured": self.display.hw.calcPercVolume(self.display.expo.resinVolume),
                "requested": self.display.hw.calcPercVolume(self.display.expo.project.usedMaterial),
            }
        )
        super().show()

    def contButtonRelease(self):
        self.display.expo.confirm_resin_warning()
