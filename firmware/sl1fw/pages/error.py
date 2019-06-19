# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.libPages import page, Page


@page
class PageError(Page):
    Name = "error"

    def __init__(self, display):
        super(PageError, self).__init__(display)
        self.pageUI = "error"
        self.pageTitle = N_("Error")
        self.stack = False
    #enddef


    def show(self):
        super(PageError, self).show()
        self.display.hw.powerLed("error")
        self.display.hw.beepAlarm(3)
    #enddef


    def setParams(self, **kwargs):
        self.backFce = kwargs.pop("backFce", None)
        self.backParams = kwargs.pop("backParams", dict())
        self.items = kwargs
    #enddef


    def okButtonRelease(self):
        self.display.hw.powerLed("normal")
        if self.backFce is None:
            return "_EXIT_"
        else:
            return self.backFce(**self.backParams)
        #endif
    #enddef

#endclass
