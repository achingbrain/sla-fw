# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import json

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageAbout(Page):
    Name = "about"

    def __init__(self, display):
        super(PageAbout, self).__init__(display)
        self.pageUI = "about"
        self.pageTitle = N_("About")
        self.items.update({
                'line1' : "2018-2019 Prusa Research s.r.o.",
                'line2' : defines.aboutURL,
#                'qr' : "https://www.prusa3d.com",
                'qr' : "MECARD:N:Prusa Research s.r.o.;URL:www.prusa3d.com;EMAIL:info@prusa3d.com;;",
                'about_url': defines.aboutURL
                })
    #enddef


    def showadminButtonRelease(self):
        try:
            query_url = defines.admincheckURL + "/?serial=" + self.display.hw.cpuSerialNo
            self.downloadURL(query_url, defines.admincheckTemp, title=_("Checking admin access"))

            with open(defines.admincheckTemp, 'r') as file:
                admin_check = json.load(file)
                if not admin_check['result']:
                    raise Exception("Admin not enabled")
                #endif
            #endwith
        except:
            self.logger.exception("Admin accesibility check exception")
            self.display.pages['error'].setParams(
                text=_("Admin not accessible"))
            return "error"
        #endexcept

        self.display.pages['yesno'].setParams(
                yesFce = self.showadminContinue,
                text = _("Do you really want to enable the admin menu?\n\n"
                    "Wrong settings will damage your printer!"))
        return "yesno"
    #enddef


    def showadminContinue(self):
        self.display.show_admin = True
        return "_BACK_"
    #enddef

#endclass
