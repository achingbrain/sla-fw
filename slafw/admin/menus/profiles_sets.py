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
from slafw.hardware.axis import AxisId
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
                    partial(self._confirm, AxisId.TILT, self._setAxisProfiles, itemName, filePath)
                ))
            elif filePath.endswith("." + defines.tuneTiltProfilesSuffix):
                self.add_item(AdminAction(
                    itemName,
                    partial(self._confirm, AxisId.TILT, self._setTuneTilt, itemName, filePath)
                ))
            elif filePath.endswith("." + defines.towerProfilesSuffix):
                self.add_item(AdminAction(
                    itemName,
                    partial(self._confirm, AxisId.TOWER, self._setAxisProfiles, itemName, filePath)
                ))

    def _confirm(self, axis: AxisId, action = None, itemName = None, path = None):
        self._control.enter(
            Confirm(
                self._control,
                partial(action, path, axis),
                text="Do you really want to set profiles: " + itemName,
            )
        )

    def _setAxisProfiles(self, path, axis: AxisId):
        with open(path, "r") as f:
            profiles = json.loads(f.read())
            self.logger.info("Overwriting %s profiles to: %s", axis.name, profiles)
            if axis is AxisId.TOWER:
                self._printer.hw.setTowerProfiles(profiles)
            else:
                self._printer.hw.tilt.profiles = profiles

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
