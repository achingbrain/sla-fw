# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageService(Page):
    Name = "service"

    def __init__(self, display):
        super(PageService, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Service")
    #enddef


    def show(self):
        self.items.update({
                'button1' : _("TODO"),
                })
        super(PageService, self).show()
    #enddef

#endclass
