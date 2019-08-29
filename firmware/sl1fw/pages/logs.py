# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageLogging(Page):
    Name = "logging"

    def __init__(self, display):
        super(PageLogging, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Logging")
    #enddef


    def show(self):
        self.items.update({
            "button1": _("Save logs to USB"),
        })
        super(PageLogging, self).show()
    #enddef


    def button1ButtonRelease(self):
        return self.saveLogsToUSB()
    #enddef

#endclass
