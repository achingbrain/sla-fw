# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw import defines
from sl1fw.exposure_state import ExposureState
from sl1fw.libConfig import TomlConfig
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.home import PageHome
from sl1fw.pages.sourceselect import PageSrcSelect


@page
class PageFinished(Page):
    Name = "finished"

    def __init__(self, display):
        super(PageFinished, self).__init__(display)
        self.pageUI = "finished"
        self.clearStack = True
        self.data = None
        self.readyBeep = True
    #enddef


    def show(self):
        if not self.data:
            expo = self.display.expo

            self.data = {
                'name' : expo.project.name,
                'print_time' : expo.printTime,
                'layers' : expo.actualLayer,
                'consumed_resin' : expo.resinCount,
                'project_file' : self.display.expo.project.origin,
                }

            self.display.hw.stopFans()
            self.display.hw.motorsRelease()
            if self.display.hwConfig.autoOff and not expo.state == ExposureState.CANCELED:
                if not TomlConfig(defines.lastProjectData).save(self.data):
                    self.logger.error("Last project data was not saved!")
                #endif
                self.display.shutDown(True)
            #endif
        #endif

        self.items.update(self.data)
        super(PageFinished, self).show()
        if self.readyBeep:
            self.display.hw.beepRepeat(3)
            self.readyBeep = True
        #endif
    #enddef


    def homeButtonRelease(self):
        self.display.pages[PageHome.Name].readyBeep = False
        return PageHome.Name
    #enddef


    def printButtonRelease(self):
        return PageSrcSelect.Name
    #enddef


    def reprintButtonRelease(self):
        self.loadProject(self.data['project_file'])
        return "reading"
    #enddef


    def _BACK_(self):
        self.readyBeep = False
        return "_SELF_"
    #enddef

#endclass
