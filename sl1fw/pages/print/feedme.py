# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.print.base import PagePrintBase

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageFeedMe(PagePrintBase):
    Name = "feedme"

    def __init__(self, display: Display):
        super(PageFeedMe, self).__init__(display)
        self.pageUI = "feedme"
        self.manual = False
        self.checkCoverOveride = True

    def show(self):
        if self.display.expo.low_resin:
            reason = _("Resin level low!")
        else:
            reason = _("Manual resin refill")

        self.showItems(
            text=_(
                "%s\n\n"
                "Please refill the tank up to the 100 %% mark and press Done.\n\n"
                "If you don't want to refill, please press the Back button on top of the screen."
            )
            % reason
        )
        super().show()

    def backButtonRelease(self):
        if self.display.expo.low_resin:
            self.display.expo.setResinVolume(None)
        self.display.expo.doBack()
        return "_SELF_"

    def refilledButtonRelease(self):
        self.display.hw.powerLed("normal")
        self.display.expo.setResinVolume(defines.resinFilled)
        self.display.expo.doContinue()
        return "_SELF_"
