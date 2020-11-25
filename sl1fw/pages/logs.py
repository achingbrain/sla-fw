# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from sl1fw.api.decorators import wrap_exception
from sl1fw.errors.errors import FailedToSetLogLevel
from sl1fw.errors.exceptions import get_exception_code
from sl1fw.logger_config import get_log_level, set_log_level
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageLogging(Page):
    Name = "logging"

    def __init__(self, display):
        super(PageLogging, self).__init__(display)
        self.pageUI = "setup"
        self.pageTitle = "Logging"
        self.debugEnabled = False

    def show(self):
        self.debugEnabled = get_log_level() == logging.DEBUG

        self.items.update(
            {"label1g1": "Debug", "state1g1": int(self.debugEnabled), "button4": "Save settings",}
        )
        super(PageLogging, self).show()

    def state1g1ButtonRelease(self):
        self.debugEnabled = not self.debugEnabled

    def button4ButtonRelease(self):
        try:
            level = logging.DEBUG if self.debugEnabled else logging.INFO
            set_log_level(level)
        except FailedToSetLogLevel as exception:
            self.logger.exception("Failed to set log level")
            self.display.pages["error"].setParams(
                code=get_exception_code(exception).raw_code, params=wrap_exception(exception)
            )
            return "error"

        # force all forked processes to reload logging settings is overkill, let user do it
        self.display.pages["confirm"].setParams(text="The setting become active after the printer's restart.")
        return "confirm"
