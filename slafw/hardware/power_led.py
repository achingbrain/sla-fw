# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.motion_controller.controller import MotionController
from slafw.errors.errors import MotionControllerException
from slafw.functions.decorators import safe_call
from enum import Enum

class PowerLedActions(str, Enum):
    Normal = 'normal'
    Warning = 'warn'
    Error = 'error'
    Off = 'off'


class PowerLed:

    def __init__(self, mcc: MotionController):
        self._mcc = mcc
        # (mode, speed)
        self._powerLedStates = {
            PowerLedActions.Normal: (1, 2),
            PowerLedActions.Warning: (2, 10),
            PowerLedActions.Error: (3, 15),
            PowerLedActions.Off: (3, 64)
        }
#        self.reset()

    def powerLed(self, state: PowerLedActions):
        mode, speed = self._powerLedStates.get(state, (1, 1))
        self.powerLedMode = mode
        self.powerLedSpeed = speed

    @property
    def powerLedMode(self):
        return self._mcc.doGetInt("?pled")

    @powerLedMode.setter
    def powerLedMode(self, value):
        self._mcc.do("!pled", value)

    @property
    def powerLedPwm(self):
        try:
            pwm = self._mcc.do("?ppwm")
            return int(pwm) * 5
        except MotionControllerException:
            self.logger.exception("Failed to read power led pwm")
            return -1

    @powerLedPwm.setter
    def powerLedPwm(self, pwm):
        try:
            self._mcc.do("!ppwm", int(pwm / 5))
        except MotionControllerException:
            self.logger.exception("Failed to set power led pwm")

    @property
    @safe_call(-1, MotionControllerException)
    def powerLedSpeed(self):
        return self._mcc.doGetInt("?pspd")

    @powerLedSpeed.setter
    @safe_call(None, MotionControllerException)
    def powerLedSpeed(self, speed):
        self._mcc.do("!pspd", speed)

    @property
    def screensaver_enabled(self) -> bool:
        return self._screensaver_enabled

    def set_error(self) -> int:
        if self._error_level_counter == 0:
            self.powerLed(PowerLedActions.Error)
        self._error_level_counter += 1
        return self._error_level_counter

    def remove_error(self) -> int:
        assert self._error_level_counter > 0
        self._error_level_counter -= 1
        if self._error_level_counter == 0:
            if self._warn_level_counter > 0:
                self.powerLed(PowerLedActions.Warning)
            else:
                self.powerLed(PowerLedActions.Normal)
        return self._error_level_counter

    def set_warning(self) -> int:
        if self._error_level_counter == 0 and self._warn_level_counter == 0:
            self.powerLed(PowerLedActions.Warning)
        self._warn_level_counter += 1
        return self._warn_level_counter

    def remove_warning(self) -> int:
        assert self._warn_level_counter > 0
        self._warn_level_counter -= 1
        if self._error_level_counter == 0 and self._warn_level_counter == 0:
            self.powerLed(PowerLedActions.Normal)
        return self._warn_level_counter

    def reset(self):
        self._screensaver_enabled = False
        self._warn_level_counter = 0
        self._error_level_counter = 0
        self.powerLed(PowerLedActions.Normal)
