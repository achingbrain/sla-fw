# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import shutil
import tarfile
import tempfile

import distro

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageNetUpdate(Page):
    Name = "netupdate"

    def __init__(self, display):
        super(PageNetUpdate, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Net Update")
        self.firmwares = []
    #enddef


    def show(self):
        # Create item for downloading examples
        self.items.update({
            "button15" : _("Download examples"),
        })

        try:
            pageWait = PageWait(self.display, line1=_("Downloading firmware list"))
            pageWait.show()
            query_url = defines.firmwareListURL + "/?serial=" + self.display.hw.cpuSerialNo + "&version=" + distro.version()
            self.display.inet.download_url(query_url,
                    defines.firmwareListTemp,
                    distro.version(),
                    self.display.hw.cpuSerialNo,
                    page=pageWait,
                    timeout_sec=5)

            with open(defines.firmwareListTemp) as list_file:
                self.firmwares = list(enumerate(json.load(list_file)))
            #endwith
        except:
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
        try:
            if not os.path.isdir(defines.internalProjectPath):
                os.makedirs(defines.internalProjectPath)
            #endif

            with tempfile.NamedTemporaryFile() as archive:
                pageWait = PageWait(self.display, line1=_("Fetching examples"))
                pageWait.show()
                self.display.inet.download_url(defines.examplesURL,
                        archive.name,
                        distro.version(),
                        self.display.hw.cpuSerialNo,
                        page=pageWait)

                pageWait.showItems(line1=_("Extracting examples"), line2="")

                with tempfile.TemporaryDirectory() as temp:
                    with tarfile.open(fileobj=archive) as tar:
                        for member in tar.getmembers():
                            tar.extract(member, temp)
                        #endfor
                    #endwith

                    pageWait.showItems(line1=_("Storing examples"))
                    for item in os.listdir(temp):
                        dest = os.path.join(defines.internalProjectPath, item)
                        if os.path.exists(dest):
                            shutil.rmtree(dest)
                        #endif
                        shutil.copytree(os.path.join(temp, item), dest)
                    #endfor

                    pageWait.showItems(line1=_("Cleaning up"))
                #endwith
            #endwith

            return "_BACK_"
        #endtry

        except Exception as e:
            self.logger.exception("Exaples fetch failed: " + str(e))
            self.display.pages['error'].setParams(
                text=_("Examples fetch failed"))
            return "error"
        #endexcept
    #enddef


    def makeUpdateButton(self, i, name, url):
        setattr(self.__class__, 'button%dButtonRelease' % i, lambda x: x.update(name, url))
    #enddef


    def update(self, name, url):
        self.display.pages['yesno'].setParams(
            yesFce = self.display.pages['firmwareupdate'].fetchUpdate,
            yesParams = { 'fw_url': url },
            text = _("Updating to %s.\n\nProceed update?") % name)
        return "yesno"
    #enddef

#endclass
