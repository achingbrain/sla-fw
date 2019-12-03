# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw.pages import page
from sl1fw.pages.base import Page

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageNetwork(Page):
    Name = "network"

    def __init__(self, display: Display):
        super(PageNetwork, self).__init__(display)
        self.pageUI = "network"

    def wifiButtonRelease(self):
        self.logger.debug("Skipping wifi button, already at page network")
