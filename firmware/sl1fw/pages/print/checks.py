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
class PageChecks(PagePrintBase):
    Name = "checks"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"
        self.pageTitle = N_("Performing pre-print checks")

    def callback(self):
        temps = _("Checking temperatures...") + self._tri_state_string(self.display.expo.temp_check_result)
        project = _("Checking project data...") + self._tri_state_string(self.display.expo.project_check_result)
        hw = _("Setting start positions...") + self._tri_state_string(self.display.expo.start_position_check_result)
        fans = _("Checking fans...") + self._tri_state_string(self.display.expo.fans_check_result)

        self.showItems(text=f"{temps}\n{project}\n{hw}\n{fans}")
        super().callback()

    @staticmethod
    def _tri_state_string(value: bool) -> str:
        if value is None:
            return ""
        elif value:
            return _("Ok")
        else:
            return _("Fail")
