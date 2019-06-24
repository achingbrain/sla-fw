# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import pydbus

from sl1fw.libPages import page, Page


@page
class PageSetHostname(Page):
    Name = "sethostname"

    def __init__(self, display):
        super(PageSetHostname, self).__init__(display)
        self.pageUI = "sethostname"
        self.pageTitle = N_("Set Hostname")
        self._hostname = None
    #enddef


    @property
    def hostname(self):
        if not self._hostname:
            self._hostname = pydbus.SystemBus().get("org.freedesktop.hostname1")
        #endif
        return self._hostname
    #enddef


    def fillData(self):
        return {
            'hostname' : self.hostname.StaticHostname,
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetHostname, self).show()
    #enddef


    def sethostnameButtonSubmit(self, data):
        try:
            hostname = data['hostname']
            self.hostname.SetStaticHostname(hostname, False)
            self.hostname.SetHostname(hostname, False)
        except:
            self.display.pages['error'].setParams(
                text=_("Failed to set hostname"))
            return "error"
        #endtry

        return "_BACK_"
    #enddef

#endclass
