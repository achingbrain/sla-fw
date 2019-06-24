# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.libPages import page, Page


@page
class PageException(Page):
    Name = "exception"

    def __init__(self, display):
        super(PageException, self).__init__(display)
        self.pageUI = "exception"
        self.pageTitle = N_("System Error")
    #enddef


    def setParams(self, **kwargs):
        self.items = kwargs
    #enddef

#endclass
