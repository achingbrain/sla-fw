# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sl1fw import defines

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


def start(display: Display):
    display.hw.startFans()
    display.runtime_config.fan_error_override = True
    display.screen.getImg(filename=str(Path(defines.dataPath) / "logo_1440x2560.png"))


def end(display: Display):
    display.runtime_config.fan_error_override = False
    display.hw.saveUvStatistics()  # TODO: Why ???
    # can't call allOff(), motorsRelease() is harmful for the wizard
    display.screen.getImgBlack()
    display.hw.uvLed(False)
    display.hw.stopFans()


def cover_check(display: Display) -> bool:
    if not display.hwConfig.coverCheck or display.hw.isCoverClosed():
        display.hw.uvLed(True)
        return True
    display.hw.uvLed(False)
    return False
