# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum
import logging

from slafw.motion_controller.controller import MotionController
from slafw.errors.errors import MotionControllerException

class PowerLedActions(str, Enum):
    Normal = 'normal'
    Warning = 'warn'
    Error = 'error'
    Off = 'off'
    Unspecified = 'unspecified'


class PowerLed:

    def __init__(self, mcc: MotionController):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._mcc = mcc
        self._error_level_counter = 0
        self._warn_level_counter  = 0
        self._modes = {
            # (mode, speed)
            PowerLedActions.Normal: (1, 2),
            PowerLedActions.Warning: (2, 10),
            PowerLedActions.Error: (3, 15),
            PowerLedActions.Off: (3, 64)
        }

    @property
    def mode(self) -> PowerLedActions:
        result = PowerLedActions.Unspecified
        try:
            mode = self._mcc.doGetInt("?pled")
            speed = self._mcc.doGetInt("?pspd")
            for k, v in self._modes.items():
                if v[0] == mode and v[1] == speed:
                    result = k
        except MotionControllerException:
            self.logger.exception("Failed to read power led pwm")
        return result

    @mode.setter
    def mode(self, value: PowerLedActions):
        m, s = self._modes[value]
        try:
            self._mcc.do("!pled", m)
            self._mcc.do("!pspd", s)
        except MotionControllerException:
            self.logger.exception("Failed to read power led pwm")

    @property
    def intensity(self):
        try:
            pwm = self._mcc.do("?ppwm")
            return int(pwm) * 5
        except MotionControllerException:
            self.logger.exception("Failed to read power led pwm")
            return -1

    @intensity.setter
    def intensity(self, pwm):
        try:
            self._mcc.do("!ppwm", int(pwm / 5))
        except MotionControllerException:
            self.logger.exception("Failed to set power led pwm")

    def set_error(self) -> int:
        if self._error_level_counter == 0:
            self.mode = PowerLedActions.Error
        self._error_level_counter += 1
        return self._error_level_counter

    def remove_error(self) -> int:
        assert self._error_level_counter > 0
        self._error_level_counter -= 1
        if self._error_level_counter == 0:
            if self._warn_level_counter > 0:
                self.mode = PowerLedActions.Warning
            else:
                self.mode =PowerLedActions.Normal
        return self._error_level_counter

    def set_warning(self) -> int:
        if self._error_level_counter == 0 and self._warn_level_counter == 0:
            self.mode = PowerLedActions.Warning
        self._warn_level_counter += 1
        return self._warn_level_counter

    def remove_warning(self) -> int:
        assert self._warn_level_counter > 0
        self._warn_level_counter -= 1
        if self._error_level_counter == 0 and self._warn_level_counter == 0:
            self.mode = PowerLedActions.Normal
        return self._warn_level_counter

    def reset(self):
        self._warn_level_counter = 0
        self._error_level_counter = 0
        self.mode = PowerLedActions.Normal
