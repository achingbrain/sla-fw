# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageAbout(Page):
    Name = "about"

    def __init__(self, display):
        super(PageAbout, self).__init__(display)
        self.pageUI = "about"
        self.items.update({
                'line1' : "2020 Prusa Research a.s.",
                'line2' : defines.aboutURL,
#                'qr' : "https://www.prusa3d.com",
                'qr' : "MECARD:N:Prusa Research a.s.;URL:www.prusa3d.com;EMAIL:info@prusa3d.com;;",
                'about_url': defines.aboutURL
                })
    #enddef

#endclass
