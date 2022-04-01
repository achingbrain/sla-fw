# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import json
from functools import partial
from pathlib import Path
from glob import glob

from slafw import defines
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction, AdminBoolValue
from slafw.admin.menus.dialogs import Info, Confirm
from slafw.admin.safe_menu import SafeAdminMenu
from slafw.hardware.axis import Axis
from slafw.libPrinter import Printer
from slafw.functions.files import get_save_path
from slafw.errors.errors import ConfigException
from slafw.hardware.printer_model import PrinterModel


class ProfilesSetsMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer
        self._temp = self._printer.hw.config.get_writer()

        self.add_back()

        usbPath = get_save_path()
        if usbPath is None:
            self.add_label("USB not present. To get profiles from USB, plug the USB and re-enter.")
        else:
            self.add_label("<h2>USB</h2>")
            self._listProfiles(usbPath, internal = False)
        self.add_label("<h2>Internal</h2>")
        for model in PrinterModel:
            self._listProfiles(os.path.join(defines.dataPath, model.name), internal=True)

        self.add_item(AdminBoolValue.from_value("Lock profiles", self._temp, "lockProfiles"))
        self.add_item(AdminAction("Save", self._save))

    def _listProfiles(self, basePath: Path, internal: bool):
        files = glob(os.path.join(basePath, "*.tilt"))
        files.extend(glob(os.path.join(basePath, "*.tune_tilt")))
        files.extend(glob(os.path.join(basePath, "*.tower")))
        for filePath in files:
            itemName = os.path.basename(filePath)
            if internal:
                itemName = os.path.basename(basePath) + " - " + itemName
            if filePath.endswith(".tilt"):
                self.add_item(AdminAction(
                    itemName,
                    partial(self._confirm, self._printer.hw.tilt, self._setAxisProfiles, itemName, filePath)
                ))
            elif filePath.endswith(".tune_tilt"):
                self.add_item(AdminAction(
                    itemName,
                    partial(self._confirm, self._printer.hw.tilt, self._setTuneTilt, itemName, filePath)
                ))
            elif filePath.endswith(".tower"):
                self.add_item(AdminAction(
                    itemName,
                    partial(self._confirm, self._printer.hw.tower, self._setAxisProfiles, itemName, filePath)
                ))

    def _confirm(self, axis: Axis, action = None, itemName = None, path = None):
        self._control.enter(
            Confirm(
                self._control,
                partial(action, path, axis),
                text="Do you really want to set profiles: " + itemName,
            )
        )

    def _setAxisProfiles(self, path, axis: Axis):
        with open(path, "r") as f:
            profiles = json.loads(f.read())
            self.logger.info("Overwriting %s profiles to: %s", axis.name, profiles)
            axis.profiles = profiles

    def _setTuneTilt(self, path, _):
        with open(path, "r") as f:
            profiles = json.loads(f.read())
            self.logger.info("Overwriting tune tilt profiles to: %s", profiles)
            writer = self._printer.hw.config.get_writer()
            writer.tuneTilt = profiles
            try:
                writer.commit()
            except Exception as e:
                raise ConfigException() from e

    def _save(self):
        self._temp.commit()
        self._control.enter(Info(self._control, "Configuration saved"))
