# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from functools import partial
from pathlib import Path
from typing import Iterable

from sl1fw import defines
from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menus.dialogs import Info
from sl1fw.admin.safe_menu import SafeAdminMenu
from sl1fw.libPrinter import Printer
from sl1fw.functions.files import get_save_path


class ProfilesSetsMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer, usb=False):
        super().__init__(control)
        self._printer = printer

        self.usb = usb
        self.sets_dir_name = "profiles_sets"
        self.internal_path = Path(defines.dataPath) / self.sets_dir_name
        self.internal_path.mkdir(exist_ok=True)
        self.sets = self.get_sets()

        self.add_back()

        self.add_label("<h2>Source</h2>")
        self.add_item(
            AdminAction(
                "--> Internal" if not self.usb else "Internal",
                partial(self.set_source, source="internal"),
            )
        )
        self.add_item(
            AdminAction(
                "--> USB" if self.usb else "USB", partial(self.set_source, source="usb")
            )
        )

        self.add_label("<h2>Profiles sets</h2>")
        if self.sets:
            for profiles_set in self.sets:
                cfg_set_name = "%s:%s" % (
                    "usb" if self.usb else "internal",
                    profiles_set.stem,
                )
                self.add_item(
                    AdminAction(
                        (
                            "--> "
                            if self._printer.hw.config.currentProfilesSet == cfg_set_name
                            else ""
                        )
                        + profiles_set.stem,
                        partial(self.apply_set, profiles_set=profiles_set),
                    )
                )
        else:
            self.add_label("<strong>No profiles in selected storage!</strong>")

    @property
    def path(self) -> Path:
        return self.internal_path if not self.usb else get_save_path()

    def get_sets(self) -> Iterable[Path]:
        return sorted(
            [
                f
                for f in self.path.iterdir()
                if f.is_file() and f.suffix.lower() == ".profiles"
            ]
        )

    @SafeAdminMenu.safe_call
    def set_source(self, source=None):
        if source == "usb" and get_save_path() is None:
            source = "internal"
            self._printer.hw.beepAlarm(2)

        self._control.pop()
        self.enter(ProfilesSetsMenu(self._control, self._printer, source == "usb"))

    @SafeAdminMenu.safe_call
    def apply_set(self, profiles_set: Path):
        with profiles_set.open("r") as f:
            data = json.load(f)

        writer = None
        applied = []
        if "tower" in data:
            self._set_profiles("tower", data["tower"])
            applied.append("tower")
        if "tilt" in data:
            self._set_profiles("tilt", data["tilt"])
            applied.append("tilt")
        if "tune_tilt" in data:
            writer = self._set_tune_tilt(data["tune_tilt"])
            applied.append("tune tilt")

        if writer is None:
            writer = self._printer.hw.config.get_writer()

        writer.currentProfilesSet = (
            "usb:" if self.usb else "internal:"
        ) + profiles_set.stem
        writer.commit()

        self._control.enter(
            Info(
                self._control,
                f"Selected set: {profiles_set.stem}\n\n"
                f"Applied profiles for: {', '.join(applied)}",
                pop=2,
            )
        )

    def _set_profiles(self, profile_type, profiles):
        data = []
        names = (
            self._printer.hw.tilt.profileNames
            if profile_type == "tilt"
            else self._printer.hw.getTowerProfilesNames()
        )
        for name in names:
            if name in profiles:
                batch = []
                for key in [
                    "starting_steprate",
                    "maximum_steprate",
                    "acceleration",
                    "deceleration",
                    "current",
                    "stallguard_threshold",
                    "coolstep_threshold",
                ]:
                    if key not in profiles[name]:
                        raise Exception(
                            "Profile '%s' is missing key '%s'!" % (name, key)
                        )
                    if profiles[name][key] == "":
                        raise Exception(
                            "Profile '%s' has empty value for key '%s'!" % (name, key)
                        )
                    batch.append(profiles[name][key])

                data.append(batch)
            else:
                raise Exception("Missing profile '%s' in selected file!" % name)

        if profile_type == "tilt":
            self._printer.hw.tilt.profiles(data)
        else:
            self._printer.hw.setTowerProfiles(data)

    def _set_tune_tilt(self, tune_tilt):
        names = [
            "tiltdownlargefill",
            "tiltdownsmallfill",
            "tiltuplargefill",
            "tiltupsmallfill",
        ]
        keys = [
            "init_profile",
            "offset_steps",
            "offset_delay",
            "finish_profile",
            "tilt_cycles",
            "tilt_delay",
            "homing_tolerance",
            "homing_cycles",
        ]

        for (
            name
        ) in names:  # check it in first pass so we don't apply only part of new data..
            if name in tune_tilt:
                for key in keys:
                    if key not in tune_tilt[name]:
                        raise Exception(
                            "Tilt tuning '%s' is missing key '%s'!" % (name, key)
                        )
                    if tune_tilt[name][key] == "":
                        raise Exception(
                            "Tilt tuning '%s' has empty value for key '%s'!"
                            % (name, key)
                        )
            else:
                raise Exception("Missing tilt tuning '%s' in selected file!" % name)

        writer = self._printer.hw.config.get_writer()
        for name in names:
            attr = [-1, -1, -1, -1, -1, -1, -1, -1]
            for i, key in enumerate(keys):
                attr[i] = tune_tilt[name][key]
            setattr(writer, "raw_" + name, attr)
        return writer
