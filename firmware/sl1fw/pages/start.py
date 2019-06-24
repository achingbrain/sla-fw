# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.libPages import page, Page


@page
class PageStart(Page):
    Name = "start"

    def __init__(self, display):
        super(PageStart, self).__init__(display)
    #enddef

#endclass
