# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.pages.base import Page
from sl1fw.pages import page

# FIXME obsolete?
@page
class PageQRCode(Page):
    Name = "qrcode"

    def __init__(self, display):
        super(PageQRCode, self).__init__(display)
        self.pageUI = "qrcode"
        self.pageTitle = N_("QR Code")
    #enddef

    # TODO: Display parametric qrcode passed from previous page

    def connectButtonRelease(self):
        return "_BACK_"
    #enddef

#endclass
