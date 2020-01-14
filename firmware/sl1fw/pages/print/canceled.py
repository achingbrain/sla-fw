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
class PagePrintCanceled(PagePrintBase):
    Name = "printcanceled"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"
        self.pageTitle = N_("Print canceled")

    def show(self):
        self.showItems(line1=_("Job will be canceled after layer finish"))
        super().show()
