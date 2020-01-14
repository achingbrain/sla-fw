# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw.exposure_state import ExposureState, ResinFailure
from sl1fw.pages import page
from sl1fw.pages.print.base import PagePrintBase

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageStirring(PagePrintBase):
    Name = "resinmeasure"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"
        self.pageTitle = N_("Wait")

    def show(self):
        if not self.display.hwConfig.resinSensor:
            self.showItems(line1=_("Resin volume measurement is turned off"))
        else:
            self.showItems(line1=_("Measuring resin volume"), line2=_("Do NOT TOUCH the printer"))
        super().show()

    def callback(self):
        if self.display.expo.state == ExposureState.FAILURE and isinstance(self.display.expo.exception, ResinFailure):
            self.showItems(line1=_("There is a problem with resin volume"), line2=_("Moving platform up"))

        if self.display.expo.resinVolume:
            self.showItems(
                line2=_("Measured resin volume is approx. %d %%")
                % self.display.hw.calcPercVolume(self.display.expo.resinVolume)
            )

        super().callback()
