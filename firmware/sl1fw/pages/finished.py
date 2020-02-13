# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

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
        self.data = {}
        self.readyBeep = True

    def show(self):
        if not self.display.runtime_config.last_project_data:
            raise AttributeError("Page finished shown without data set.")

        self.items.update(self.display.runtime_config.last_project_data)
        super().show()
        if self.readyBeep:
            self.display.hw.beepRepeat(3)
            self.readyBeep = True

    def homeButtonRelease(self):
        self.display.pages[PageHome.Name].readyBeep = False
        return PageHome.Name

    @staticmethod
    def printButtonRelease():
        return PageSrcSelect.Name

    def reprintButtonRelease(self):
        if not self.display.runtime_config.last_project_data:
            raise AttributeError("Page finished reprint without data set.")

        self.loadProject(self.display.runtime_config.last_project_data["project_file"])
        return "reading"

    def _BACK_(self):
        self.readyBeep = False
        return "_SELF_"
