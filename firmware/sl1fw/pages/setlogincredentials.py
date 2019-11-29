# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess

from sl1fw.pages.base import Page
from sl1fw.pages import page

@page
class PageSetLoginCredentials(Page):
    Name = "setlogincredentials"

    def __init__(self, display):
        super(PageSetLoginCredentials, self).__init__(display)
        self.pageUI = "setlogincredentials"
    #enddef


    def fillData(self):
        return {
            'api_key' : self.octoprintAuth,
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetLoginCredentials, self).show()
    #enddef


    def saveButtonSubmit(self, data):
        apikey = data['api_key']

        try:
            subprocess.check_call(["/bin/api-keygen.sh", apikey])
        except subprocess.CalledProcessError as e:
            self.display.pages['error'].setParams(
                text = _("Octoprint API key change failed"))
            return "error"
        #endexcept

        return "_BACK_"
    #enddef

#endclass
