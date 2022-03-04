# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.hardware.base.exposure_screen import ExposureScreen, ExposureScreenParameters
from slafw.hardware.printer_model import PrinterModel


class ExposureScreenSL1(ExposureScreen):
    @staticmethod
    def get_parameters(printer_model: PrinterModel) -> ExposureScreenParameters:
        return {
            PrinterModel.SL1: ExposureScreenParameters(
                size_px=(1440, 2560),
                thumbnail_factor=5,
                output_factor=1,
                pixel_size_nm=46875,
                refresh_delay_ms=0,
                monochromatic=False,
                bgr_pixels=False,
            ),
            PrinterModel.SL1S: ExposureScreenParameters(
                size_px=(540, 2560),
                thumbnail_factor=5,
                output_factor=1,
                pixel_size_nm=50000,
                refresh_delay_ms=0,
                monochromatic=True,
                bgr_pixels=True,
            ),
            # same as SL1S
            PrinterModel.M1: ExposureScreenParameters(
                size_px=(540, 2560),
                thumbnail_factor=5,
                output_factor=1,
                pixel_size_nm=50000,
                refresh_delay_ms=0,
                monochromatic=True,
                bgr_pixels=True,
            ),
        }.get(printer_model, ExposureScreen.get_parameters(printer_model))
