# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json

import distro

from sl1fw import defines
from sl1fw.errors.exceptions import get_exception_code
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait
from sl1fw.state_actions.examples import download_examples_legacy


@page
class PageNetUpdate(Page):
    Name = "netupdate"

    def __init__(self, display):
        super(PageNetUpdate, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Net Update"
        self.firmwares = []
    #enddef


    def show(self):
        # Create item for downloading examples
        self.items.update({
            "button15" : "Download examples",
        })

        try:
            pageWait = PageWait(self.display, line1="Downloading firmware list")
            pageWait.show()
            query_url = defines.firmwareListURL + "/?serial=" + self.display.hw.cpuSerialNo + "&version=" + distro.version()
            self.display.inet.download_url(query_url, defines.firmwareListTemp, page=pageWait, timeout_sec=5)

            with open(defines.firmwareListTemp) as list_file:
                self.firmwares = list(enumerate(json.load(list_file)))
            #endwith
        except Exception:
            self.logger.exception("Failed to load firmware list from the net")
        #endtry

        # Create items for updating firmwares
        self.items.update({
            "button%s" % (i + 1): ("%s - %s") % (firmware['version'], firmware['branch']) for (i, firmware) in self.firmwares
        })

        # Create action handlers
        for (i, firmware) in self.firmwares:
            self.makeUpdateButton(i + 1, firmware['version'], firmware['url'])
        #endfor

        super(PageNetUpdate, self).show()
    #enddef


    def button15ButtonRelease(self):
        pageWait = PageWait(self.display)
        pageWait.show()
        try:
            download_examples_legacy(pageWait, self.display.inet)
            return "_BACK_"
        except Exception as exception:
            self.logger.exception("Fetching of samples failed")
            self.display.pages['error'].setParams(code=get_exception_code(exception).raw_code)
            return "error"
        #endtry
    #enddef


    def makeUpdateButton(self, i, name, url):
        setattr(self.__class__, 'button%dButtonRelease' % i, lambda x: x.update(name, url))
    #enddef


    def update(self, name, url):
        self.display.pages['yesno'].setParams(
            yesFce = self.display.pages['firmwareupdate'].fetchUpdate,
            yesParams = { 'fw_url': url },
            text = "Updating to %s.\n\nProceed with the update?" % name)
        return "yesno"
    #enddef

#endclass
