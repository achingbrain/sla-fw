# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw.pages.base import Page
from sl1fw.states.exposure import ExposureState

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


class PagePrintBase(Page):
    def __init__(self, display: Display):
        super().__init__(display)
        self.callbackSkip = 5
        self.callbackPeriod = 0.1

    def callback(self):
        self._exposure_state_switch()

        self.callbackSkip += 1
        if self.callbackSkip >= 5:
            self.callbackSkip = 0
            return super().callback()
        return None

    def _exposure_state_switch(self):
        mapping = {
            ExposureState.READING_DATA: "reading",
            ExposureState.CONFIRM: "printpreviewswipe",
            ExposureState.CHECKS: "checks",
            ExposureState.PRINTING: "print",
            ExposureState.GOING_UP: "goingup",
            ExposureState.GOING_DOWN: "goingdown",
            ExposureState.WAITING: "waiting",
            ExposureState.STIRRING: "stirring",
            ExposureState.PENDING_ACTION: "printactionpending",
            ExposureState.COVER_OPEN: "printcoveropen",
            ExposureState.FEED_ME: "feedme",
            ExposureState.STUCK: "printstuck",
            ExposureState.STUCK_RECOVERY: "printstuckrecovery",
            ExposureState.TILTING_DOWN: "tiltingdown",
            ExposureState.RESIN_WARNING: "resinconfirm",
            ExposureState.CHECK_WARNING: "checkconfirm",
        }

        if self.display.expo.state in mapping and self.display.actualPage.Name != mapping[self.display.expo.state]:
            self.logger.debug(
                "Print state: %s, current page: %s, switching to: %s",
                self.display.expo.state,
                self.display.actualPage.Name,
                mapping[self.display.expo.state],
            )
            self.display.forcePage(mapping[self.display.expo.state])
