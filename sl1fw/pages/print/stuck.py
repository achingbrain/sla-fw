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
class PageStuck(PagePrintBase):
    Name = "printstuck"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Printer stuck")

    def show(self):
        self.showItems(
            text=_(
                "The printer got stuck and needs user assistance.\n\n"
                "Release the tank mechanism and press Continue.\n\n"
                "If you don't want to continue, press the Back button on top of the screen and the current job will be canceled."
            )
        )
        self.display.hw.beepAlarm(1)
        super().show()

    def contButtonRelease(self):
        return self.display.expo.doContinue()

    def backButtonRelease(self):
        return self.display.expo.doBack()


@page
class PagePrintStuckRecovery(PagePrintBase):
    Name = "printstuckrecovery"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"
        self.pageTitle = N_("Stuck recovery")

    def show(self):
        self.showItems(line1=_("Setting start positions"))
        super().show()
