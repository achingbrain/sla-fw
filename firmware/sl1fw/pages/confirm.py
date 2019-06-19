# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.libPages import page, Page


@page
class PageConfirm(Page):
    Name = "confirm"

    def __init__(self, display):
        super(PageConfirm, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Confirm")
        self.stack = False
    #enddef


    def setParams(self, **kwargs):
        self.continueFce = kwargs.pop("continueFce", None)
        self.continueParams = kwargs.pop("continueParams", dict())
        self.backFce = kwargs.pop("backFce", None)
        self.backParams = kwargs.pop("backParams", dict())
        self.beep = kwargs.pop("beep", False)
        self.items = kwargs
    #enddef


    def show(self):
        super(PageConfirm, self).show()
        if self.beep:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def contButtonRelease(self):
        if self.continueFce is None:
            return "_EXIT_"
        else:
            return self.continueFce(**self.continueParams)
        #endif
    #enddef


    def backButtonRelease(self):
        if self.backFce is None:
            return super(PageConfirm, self).backButtonRelease()
        else:
            return self.backFce(**self.backParams)
        #endif
    #enddef

#endclass
