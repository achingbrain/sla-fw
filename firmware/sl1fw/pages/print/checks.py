# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw.exposure_state import ExposureCheckResult, ExposureCheck
from sl1fw.pages import page
from sl1fw.pages.print.base import PagePrintBase

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageChecks(PagePrintBase):
    Name = "checks"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"
        self.pageTitle = N_("Performing pre-print checks")

    def callback(self):
        results = self.display.expo.check_results
        cover = _("Cover closed...") + self._state_to_string(results[ExposureCheck.COVER])
        temps = _("Temperatures...") + self._state_to_string(results[ExposureCheck.TEMPERATURE])
        project = _("Project data...") + self._state_to_string(results[ExposureCheck.PROJECT])
        hw = _("Axis check...") + self._state_to_string(results[ExposureCheck.HARDWARE])
        fans = _("Fans...") + self._state_to_string(results[ExposureCheck.FAN])
        resin = _("Resin volume...") + self._resin_to_string(results[ExposureCheck.RESIN])
        start_positions = _("Start positions...") + self._state_to_string(results[ExposureCheck.START_POSITIONS])
        stirring = _("Resin stirring...") + self._state_to_string(results[ExposureCheck.STIRRING])

        self.showItems(text=f"{cover}\n{temps}\n{project}\n{hw}\n{fans}\n{resin}\n{start_positions}\n{stirring}")
        super().callback()

    @staticmethod
    def _state_to_string(value: ExposureCheckResult) -> str:
        return {
            ExposureCheckResult.SCHEDULED: _("Waiting"),
            ExposureCheckResult.RUNNING: _("Running"),
            ExposureCheckResult.SUCCESS: _("Ok"),
            ExposureCheckResult.FAILURE: _("Fail"),
            ExposureCheckResult.WARNING: _("Warn"),
            ExposureCheckResult.DISABLED: _("Disabled"),
        }[value]

    def _resin_to_string(self, value: ExposureCheckResult) -> str:
        if value == ExposureCheckResult.RUNNING:
            return _("Running, do NOT TOUCH the printer.")

        if value == ExposureCheckResult.SUCCESS:
            return _("approx. %d %%") % self.display.hw.calcPercVolume(self.display.expo.resinVolume)

        return self._state_to_string(value)
