# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.hardware.printer_model import PrinterModel


def start(hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
    hw.startFans()
    runtime_config.fan_error_override = True
    exposure_image.show_system_image("logo.png")


def end(hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
    runtime_config.fan_error_override = False
    hw.saveUvStatistics()
    # can't call allOff(), motorsRelease() is harmful for the wizard
    exposure_image.blank_screen()
    hw.uvLed(False)
    hw.stopFans()


def cover_check(hw: Hardware, printer_model: PrinterModel) -> bool:
    if hw.isCoverVirtuallyClosed():
        hw.uvLedPwm = printer_model.calibration_parameters(hw.is500khz).min_pwm
        hw.uvLed(True)
        return True
    hw.uvLed(False)
    return False
