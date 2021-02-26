# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
import json
import logging
from threading import Thread
from time import sleep

import distro
import pydbus

from sl1fw import defines
from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction, AdminTextValue
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Error, Confirm
from sl1fw.functions.system import shut_down
from sl1fw.libPrinter import Printer


class NetUpdate(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer
        self._status = "Downloading list of updates"

        self.add_back()
        self.add_label("<h2>Custom updates to latest dev builds</h2>")
        self.add_item(AdminTextValue.from_property(self, NetUpdate.status))

        self._thread = Thread(target=self._download_list)
        self._thread.start()

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value: str):
        self._status = value

    def on_leave(self):
        self._thread.join()

    def _download_list(self):
        query_url = f"{defines.firmwareListURL}/?serial={self._printer.hw.cpuSerialNo}&version={distro.version()}"

        self._printer.inet.download_url(
            query_url, defines.firmwareListTemp, timeout_sec=5, progress_callback=self._download_callback
        )

        with open(defines.firmwareListTemp) as list_file:
            firmwares = json.load(list_file)
            for firmware in firmwares:
                item = AdminAction(firmware["version"], functools.partial(self._install_fw, firmware))
                self.add_item(item)
        self.del_item(self.items["status"])

    def _download_callback(self, progress: float):
        self.status = f"Downloading list of updates: {round(progress * 100)}%"

    def _install_fw(self, firmware):
        self._control.enter(
            Confirm(
                self._control,
                functools.partial(self._do_install_fw, firmware),
                text=f"Really install firmware: {firmware['version']}",
            )
        )

    def _do_install_fw(self, firmware):
        self._control.enter(FwInstall(self._control, self._printer, firmware))


class FwInstall(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer, firmware):
        super().__init__(control)
        self._logger = logging.getLogger(__name__)
        self._printer = printer
        self._firmware = firmware
        self._status = "Downloading firmware"

        self.add_label(f"<h2>Updating firmware</h2><br/>Version: {self._firmware['version']}")
        self.add_item(AdminTextValue.from_property(self, FwInstall.status))

        self._thread = Thread(target=self._install, daemon=True)
        self._thread.start()

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value: str):
        self._status = value

    def _install(self):
        self.fetch_update(self._firmware["url"])
        self.do_update(defines.firmwareTempFile)

    def fetch_update(self, fw_url):
        try:
            self._printer.inet.download_url(fw_url, defines.firmwareTempFile, progress_callback=self._download_callback)
        except Exception as e:
            self._logger.error("Firmware fetch failed: %s", str(e))
            self._control.enter(Error(self._control, text="Firmware fetch failed"))

    def do_update(self, fw_file):
        self._logger.info("Flashing: %s", fw_file)
        try:
            rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
            rauc.Install(fw_file)
        except Exception as e:
            self._logger.error("Rauc install call failed: %s", str(e))
            return

        self.status = "Updating firmware"

        try:
            while True:
                progress = rauc.Progress

                self.status = f"{progress[0]}<br/>{progress[1]}"

                # Check progress for update done
                if progress[1] == "Installing done.":
                    self.status = "Install done -> shutting down"
                    sleep(3)
                    shut_down(self._printer.hw, True)

                # Check for operation failure
                if progress[1] == "Installing failed.":
                    raise Exception(f"Update failed: {rauc.LastError}")
                # Wait for a while
                sleep(1)

        except Exception as e:
            self._logger.error("Rauc update failed: %s", str(e))
            self._control.enter(Error(self._control, text=str(e)))

    def _download_callback(self, progress: float):
        self.status = f"Downloading firmware: {round(progress * 100)}%"
