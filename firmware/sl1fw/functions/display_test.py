# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from sl1fw import defines
from sl1fw.libConfig import RuntimeConfig, HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen


def start(hw: Hardware, screen : Screen, runtime_config: RuntimeConfig):
    hw.startFans()
    runtime_config.fan_error_override = True
    screen.getImg(filename=str(Path(defines.dataPath) / "logo_1440x2560.png"))


def end(hw: Hardware, screen : Screen, runtime_config: RuntimeConfig):
    runtime_config.fan_error_override = False
    hw.saveUvStatistics()
    # can't call allOff(), motorsRelease() is harmful for the wizard
    screen.getImgBlack()
    hw.uvLed(False)
    hw.stopFans()


def cover_check(hw: Hardware, hw_config: HwConfig) -> bool:
    if not hw_config.coverCheck or hw.isCoverClosed():
        hw.uvLedPwm = hw.getMinPwm()
        hw.uvLed(True)
        return True
    hw.uvLed(False)
    return False
