# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.libPages import page, Page


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
