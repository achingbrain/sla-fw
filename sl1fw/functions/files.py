# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sl1fw import defines, test_runtime


def get_save_path() -> Optional[Path]:
    """
    Dynamic USB path, first usb device or None

    :return: First usb device path or None
    """
    if test_runtime.testing:
        return Path(tempfile.tempdir)

    usbs = [p for p in Path(defines.mediaRootPath).glob("*") if p.is_mount()]
    if not usbs:
        return None
    return usbs[0]

def save_wizard_history(path: Path):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if path.parent == defines.factoryMountPoint:
        mode = "factory_data"
    else:
        mode =  "user_data"

    wizard_history = Path(defines.wizardHistoryPath) / mode / f"{path.stem}.{timestamp}{path.suffix}"
    wizard_history.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, wizard_history)

def _save_wizard_history_bach(files: dict, src:Path, dest:Path):
    saved_files = set()
    for file_name in dest.glob("**/*"):
        elem = file_name.name[:file_name.name.index(".")]
        saved_files.add(elem)
    for prefix, names in files.items():
        for name in names:
            if name not in saved_files:
                path = src / (name + prefix)
                if path.is_file():
                    save_wizard_history(path)

def save_all_remain_wizard_history():
    wizard_history_path = Path(defines.wizardHistoryPath)

    _save_wizard_history_bach(
        {".toml": ["factory", "hardware", "uvcalib_data", "wizard_data"]},
        defines.factoryMountPoint,
        wizard_history_path / "factory_data"
    )

    _save_wizard_history_bach(
        {".toml": ["uvcalib_data", "wizard_data"], ".cfg": ["hardware"]},
        defines.configDir,
        wizard_history_path / "user_data"
    )

def ch_mode_owner(src):
    """
        change group and mode of the file or folder.
    """
    shutil.chown(src, group=defines.internalProjectGroup)
    if os.path.isdir(src):
        os.chmod(src, defines.internalProjectDirMode)
        for name in os.listdir(src):
            ch_mode_owner(os.path.join(src, name))
    else:
        os.chmod(src, defines.internalProjectMode)


def usb_remount(path: str):
    if test_runtime.testing:
        print("Skipping usb remount due to testing")
        return

    subprocess.check_call(["usbremount", path])
