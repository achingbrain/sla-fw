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

        old_data = self.display.runtime_config.last_project_data
        self.display.action_manager.new_exposure(
            self.display.hwConfig,
            self.display.hw,
            self.display.screen,
            self.display.runtime_config,
            old_data["project_file"],
            exp_time_ms=old_data["exp_time_ms"],
            exp_time_first_ms=old_data["exp_time_first_ms"],
            exp_time_calibrate_ms=old_data["exp_time_calibrate_ms"]
        )
        return "reading"

    def _BACK_(self):
        self.readyBeep = False
        return "_SELF_"
