# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import json
from functools import partial
from pathlib import Path
from glob import glob

from sl1fw import defines
from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction, AdminBoolValue
from sl1fw.admin.menus.dialogs import Info, Confirm
from sl1fw.admin.safe_menu import SafeAdminMenu
from sl1fw.libPrinter import Printer
from sl1fw.functions.files import get_save_path
from sl1fw.errors.exceptions import ConfigException
from sl1fw.hardware.printer_model import PrinterModel


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
        files = glob(os.path.join(basePath, "*." + defines.tiltProfilesSuffix))
        files.extend(glob(os.path.join(basePath, "*." + defines.tuneTiltProfilesSuffix)))
        files.extend(glob(os.path.join(basePath, "*." + defines.towerProfilesSuffix)))
        for filePath in files:
            itemName = os.path.basename(filePath)
            if internal:
                itemName = os.path.basename(basePath) + " - " + itemName
            if filePath.endswith("." + defines.tiltProfilesSuffix):
                self.add_item(AdminAction(
                    itemName,
                    partial(self._confirm, self._setTiltProfiles, itemName, filePath)
                ))
            elif filePath.endswith("." + defines.tuneTiltProfilesSuffix):
                self.add_item(AdminAction(
                    itemName,
                    partial(self._confirm, self._setTuneTilt, itemName, filePath)
                ))
            elif filePath.endswith("." + defines.towerProfilesSuffix):
                self.add_item(AdminAction(
                    itemName,
                    partial(self._confirm, self._setTowerProfiles, itemName, filePath)
                ))

    def _confirm(self, action = None, itemName = None, path = None):
        self._control.enter(
            Confirm(
                self._control,
                partial(action, path),
                text="Do you really want to set profiles: " + itemName,
            )
        )

    def _setTiltProfiles(self, path):
        with open(path, "r") as f:
            profiles = json.loads(f.read())
            self.logger.info("Overwriting tilt profiles to: %s", profiles)
            self._printer.hw.tilt.profiles = profiles
            self._printer.hw.tilt.sensitivity(self._printer.hw.config.tiltSensitivity)

    def _setTowerProfiles(self, path):
        with open(path, "r") as f:
            profiles = json.loads(f.read())
            self.logger.info("Overwriting tower profiles to: %s", profiles)
            self._printer.hw.setTowerProfiles(profiles)
            self._printer.hw.updateMotorSensitivity(
                self._printer.hw.config.tiltSensitivity,
                self._printer.hw.config.towerSensitivity
            )

    def _setTuneTilt(self, path):
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
