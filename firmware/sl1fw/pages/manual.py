# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw import defines
from sl1fw.libPages import page, Page


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
