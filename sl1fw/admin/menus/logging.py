# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminBoolValue
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Error, Info
from sl1fw.errors.errors import FailedToSetLogLevel
from sl1fw.logger_config import get_log_level, set_log_level


class LoggingMenu(AdminMenu):
    def __init__(self, control: AdminControl):
        super().__init__(control)

        self.add_back()
        self.add_item(AdminBoolValue("Debug logging", self.get_debug_enabled, self.set_debug_enabled))

    @staticmethod
    def get_debug_enabled() -> bool:
        return get_log_level() == logging.DEBUG

    def set_debug_enabled(self, value: bool) -> None:
        try:
            if value:
                set_log_level(logging.DEBUG)
            else:
                set_log_level(logging.INFO)
        except FailedToSetLogLevel:
            self.logger.exception("Failed to set loglevel from admin")
            self._control.enter(Error(self._control, text="Failed to set log level", pop=2))

        # force all forked processes to reload logging settings is overkill, let user do it
        self._control.enter(Info(self._control, "The setting become active after the printer's restart."))
