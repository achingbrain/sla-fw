# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import subprocess

from sl1fw.defines import TruncLogsCommand
from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminBoolValue, AdminAction, AdminLabel
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Error, Info, Wait
from sl1fw.admin.safe_menu import SafeAdminMenu
from sl1fw.errors.errors import FailedToSetLogLevel
from sl1fw.logger_config import get_log_level, set_log_level


class LoggingMenu(AdminMenu):
    def __init__(self, control: AdminControl):
        super().__init__(control)

        self.add_back()
        self.add_item(AdminBoolValue("Debug logging", self.get_debug_enabled, self.set_debug_enabled))
        self.add_item(AdminAction("Truncate logs", self._truncate_logs))

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
            self._control.enter(Error(self._control, text="Failed to set log level"))
            return

        # force all forked processes to reload logging settings is overkill, let user do it
        self._control.enter(Info(self._control, "The setting become active after the printer's restart."))

    def _truncate_logs(self):
        self.enter(Wait(self._control, self._do_truncate_logs))

    @SafeAdminMenu.safe_call
    def _do_truncate_logs(self, status: AdminLabel):
        status.set("Truncating logs")

        # FIXME copy&paste from controller.py, create method/function for calling shell
        try:
            process = subprocess.Popen(
                [TruncLogsCommand, "60s"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )
            while True:
                line = process.stdout.readline()
                if line == "" and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    if line == "":
                        continue
                    self.logger.info("truncate_logs: '%s'", line)
            status.set("Done")
        except Exception as e:
            self.logger.exception("truncate_logs exception: %s", str(e))
            self._control.enter(Error(self._control, text="Failed to truncate logs"))
