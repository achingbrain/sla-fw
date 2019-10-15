# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageManual(Page):
    Name = "manual"

    def __init__(self, display):
        super(PageManual, self).__init__(display)
        self.pageUI = "manual"
        self.pageTitle = N_("Manual")
        self.items.update({
            'manual_url': defines.manualURL,
            #'text' : "",
        })
    #enddef

#endclass
