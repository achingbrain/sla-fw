# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from sl1fw import defines

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


def get_save_path() -> Optional[Path]:
    """
    Dynamic USB path, first usb device or None

    :return: First usb device path or None
    """
    usbs = [p for p in Path(defines.mediaRootPath).glob("*") if p.is_mount()]
    if not usbs:
        return None
    return usbs[0]


def save_logs_to_usb(a64_serial: str) -> None:
    """
    Save logs to USB Flash drive

    :param a64_serial: A64 serial used to name the file
    """
    save_path = get_save_path()
    if save_path is None or not save_path.parent.exists():
        raise FileNotFoundError(save_path)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    serial = re.sub("[^a-zA-Z0-9]", "_", a64_serial)
    log_file = save_path / f"log.{serial}.{timestamp}.txt.xz"

    try:
        subprocess.check_call(["export_logs.bash", log_file])
    except Exception as exception:
        raise Exception(N_("Saving logs failed")) from exception


def start_display_test(display: Display):
    display.hw.startFans()
    display.fanErrorOverride = True
    display.screen.getImg(filename=str(Path(defines.dataPath) / "logo_1440x2560.png"))


def end_display_test(display: Display):
    display.fanErrorOverride = False
    display.hw.saveUvStatistics()  # TODO: Why ???
    # can't call allOff(), motorsRelease() is harmful for the wizard
    display.screen.getImgBlack()
    display.hw.uvLed(False)
    display.hw.stopFans()


def display_test_cover_check(display: Display) -> bool:
    if not display.hwConfig.coverCheck or display.hw.isCoverClosed():
        display.hw.uvLed(True)
        return True
    else:
        display.hw.uvLed(False)
        return False
