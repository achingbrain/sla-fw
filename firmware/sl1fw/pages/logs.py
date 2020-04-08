# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from sl1fw.pages.base import Page
from sl1fw.logger_config import get_log_level, set_log_level
from sl1fw.pages import page


@page
class PageLogging(Page):
    Name = "logging"

    def __init__(self, display):
        super(PageLogging, self).__init__(display)
        self.pageUI = "setup"
        self.pageTitle = "Logging"
        self.debugEnabled = False
    #enddef


    def show(self):
        self.debugEnabled = get_log_level() == logging.DEBUG

        self.items.update({
            'label1g1' : "Debug",
            'state1g1' : int(self.debugEnabled),
            'button1' : "Export to USB",
            'button4' : "Save settings",
        })
        super(PageLogging, self).show()
    #enddef


    def state1g1ButtonRelease(self):
        self.debugEnabled = not self.debugEnabled
    #enddef


    def button1ButtonRelease(self):
        return self.saveLogsToUSB()
    #enddef


    def button4ButtonRelease(self):
        try:
            level = logging.DEBUG if self.debugEnabled else logging.INFO
            set_log_level(level)
        except Exception:
            self.logger.exception("Failed to set log level")
            self.display.pages['error'].setParams(text = "Failed to set log level")
            return "error"
        #endtry

        # force all forked processes to reload logging settings is overkill, let user do it
        self.display.pages['confirm'].setParams(
                text = "The setting become active after the printer's restart.")
        return "confirm"
    #enddef

#endclass
