# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List

from slafw.hardware.printer_model import PrinterModel
from slafw.motion_controller.controller import MotionController


@dataclass(eq=False)
class UvLedParameters:
    pwms: tuple
    intensity_error_threshold: int
    param_p: float
    min_pwm: int = field(init=False)
    max_pwm: int = field(init=False)
    safe_default_pwm: int = field(init=False)

    def __post_init__(self):
        self.min_pwm = self.pwms[0]
        self.max_pwm = self.pwms[1]
        self.safe_default_pwm = self.pwms[2]


class UvLed:
    def __init__(self, printer_model: PrinterModel):
        self._printer_model = printer_model
        self._parameters = self.get_parameters()

    def get_parameters(self) -> UvLedParameters:
        return {
            PrinterModel.NONE: UvLedParameters(
                pwms=(0, 250, 0),
                intensity_error_threshold=1,
                param_p=0.75,
            ),
            PrinterModel.SL1: UvLedParameters(
                pwms=(150, 250, 150) if self._is500khz else (125, 218, 125),
                intensity_error_threshold=1,
                param_p=0.75,
            ),
            PrinterModel.SL1S: UvLedParameters(
                pwms=(30, 250, 208),
                intensity_error_threshold=1,
                param_p=0.75,
            ),
            # same as SL1S
            PrinterModel.M1: UvLedParameters(
                pwms=(30, 250, 208),
                intensity_error_threshold=1,
                param_p=0.75,
            ),
        }[self._printer_model]

    @property
    def parameters(self) -> UvLedParameters:
        return self._parameters

    @property
    @abstractmethod
    def _is500khz(self) -> bool:
        """
        Only applicable for SL1. Return True if motion controller rev is >= 6c
        """

    @property
    @abstractmethod
    def get_check_pwms(self) -> List[int]:
        """
        Return list of PWMs to use in self test
        """
