# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import numpy
from PIL import Image

from slafw.errors.errors import NotUVCalibrated, NotMechanicallyCalibrated
from slafw.configs.hw import HwConfig
from slafw.hardware.printer_model import CalibrationParameters

def get_white_pixels(image: Image) -> int:
    np_array = numpy.array(image.histogram())
    return int(numpy.sum(np_array[128:]))  # simple treshold


def check_ready_to_print(config: HwConfig, calibration_parameters: CalibrationParameters) -> None:
    """
    This raises exceptions when printer is not ready to print

    TODO: Make this consistent with Printer._make_ready_to_print
    TODO: Avoid duplicated condition code

    :return: None
    """
    if config.uvPwm < calibration_parameters.min_pwm:
        raise NotUVCalibrated()

    if not config.calibrated:
        raise NotMechanicallyCalibrated()