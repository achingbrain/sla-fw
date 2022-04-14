# This file is part of the SLA firmware
# Copyright (C) 2021-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import subprocess
from typing import Optional
from time import sleep

from slafw import defines
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminBoolValue, AdminAction, AdminLabel
from slafw.admin.menus.dialogs import Error, Info, Wait
from slafw.admin.safe_menu import SafeAdminMenu
from slafw.errors.errors import FailedToSetLogLevel
from slafw.logger_config import get_log_level, set_log_level
from slafw.libPrinter import Printer
from slafw.state_actions.logs import ServerUploadLogs
from slafw.states.data_export import ExportState


class LoggingMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer
        self._status: Optional[AdminLabel] = None

        self.add_back()
        self.add_items(
            (
                AdminBoolValue("Debug logging", self._get_debug_enabled, self._set_debug_enabled, "logs-icon"),
                AdminAction("Truncate logs", self._truncate_logs, "delete_small_white"),
                AdminAction("Upload to Cucek", self._upload_dev, "upload_cloud_color"),
            )
        )

    @staticmethod
    def _get_debug_enabled() -> bool:
        return get_log_level() == logging.DEBUG

    def _set_debug_enabled(self, value: bool) -> None:
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
                [defines.TruncLogsCommand, "60s"],
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
            self._control.enter(Info(self._control, "Logs was truncated successfully", pop=2))
        except Exception as e:
            self.logger.exception("truncate_logs exception: %s", str(e))
            text = f"{type(e).__name__}\n{Exception.__str__(e)}"
            self._control.enter(Error(self._control, text=text, headline="Failed to truncate logs"))

    def _upload_dev(self):
        self.enter(Wait(self._control, self._do_upload_dev))

    def _do_upload_dev(self, status: AdminLabel):
        self._status = status
        exporter = ServerUploadLogs(self._printer.hw, defines.log_url_dev)
        exporter.state_changed.connect(self._state_callback)
        exporter.store_progress_changed.connect(self._store_progress_callback)
        exporter.start()
        while exporter.state not in ExportState.finished_states():
            sleep(0.5)
        self._printer.hw.beepEcho()
        if exporter.state == ExportState.FINISHED:
            self._control.enter(Info(self._control, "Logs was uploaded successfully", pop=2))
        else:
            self._control.enter(Error(self._control,
                text=exporter.format_exception(),
                headline="Failed to upload logs"))

    def _state_callback(self, state: ExportState):
        self._status.set(state.name)

    def _store_progress_callback(self, value: float):
        self._status.set("UPLOADING: %d %%" % int(value * 100))
