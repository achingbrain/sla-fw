# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess

from sl1fw import defines
from sl1fw.libConfig import TomlConfig
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
            'htdigest': self.httpDigest
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetLoginCredentials, self).show()
    #enddef


    def saveButtonSubmit(self, data):
        apikey = data['api_key']
        htdigest = data.get('htdigest', self.httpDigest)

        try:
            subprocess.check_call(["/bin/api-keygen.sh", apikey])
            remoteConfig = TomlConfig(defines.remoteConfig)
            newData = remoteConfig.load()
            newData['htdigest'] = htdigest
            if not remoteConfig.save(data=newData):
                self.display.pages['error'].setParams(
                text = _("Octoprint API key change failed"))
                return "error"
            if htdigest:
                subprocess.check_call([defines.htDigestCommand, "enable"])
            else:
                subprocess.check_call([defines.htDigestCommand, "disable"])
        except subprocess.CalledProcessError:
            self.display.pages['error'].setParams(
                text = _("Octoprint API key change failed"))
            return "error"
        #endexcept

        return "_BACK_"
    #enddef

#endclass
