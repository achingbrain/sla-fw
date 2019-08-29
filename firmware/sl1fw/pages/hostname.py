# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageSetHostname(Page):
    Name = "sethostname"

    def __init__(self, display):
        super(PageSetHostname, self).__init__(display)
        self.pageUI = "sethostname"
        self.pageTitle = N_("Set Hostname")
    #enddef


    def fillData(self):
        return {
            'hostname' : self.display.inet.hostname
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetHostname, self).show()
    #enddef


    def sethostnameButtonSubmit(self, data):
        try:
            self.display.inet.hostname = data['hostname']
        except:
            self.logger.exception("Failed to set hostname")
            self.display.pages['error'].setParams(
                text=_("Failed to set hostname"))
            return "error"
        #endtry

        return "_BACK_"
    #enddef

#endclass
