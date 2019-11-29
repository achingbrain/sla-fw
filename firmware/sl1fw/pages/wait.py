# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.pages.base import Page


class PageWait(Page):
    Name = "wait"

    def __init__(self, display, **kwargs):
        super(PageWait, self).__init__(display)
        self.pageUI = "wait"
        self.items.update(kwargs)

    def fill(self, **kwargs):
        self.items = kwargs
