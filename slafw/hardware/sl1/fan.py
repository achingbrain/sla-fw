# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict, Optional, Callable

from slafw import defines

from slafw.configs.hw import HwConfig
from slafw.hardware.base.fan import Fan
from slafw.hardware.base.temp_sensor import TempSensor
from slafw.motion_controller.controller import MotionController


class SL1Fan(Fan):
    # pylint: disable = too-many-arguments
    # pylint: disable = too-many-instance-attributes
    def __init__(
        self,
        mcc: MotionController,
        name: str,
        index: int,
        min_rpm: int,
        max_rpm: int,
        default_rpm: int,
        enabled: bool,
        reference: Optional[TempSensor] = None,
        auto_control_inhibitor: Callable[[], bool] = lambda: False,
    ):
        super().__init__(
            name, min_rpm, max_rpm, default_rpm, reference=reference, auto_control_inhibitor=auto_control_inhibitor
        )
        self._index = index
        self._rpm: Optional[int] = None
        self._error: Optional[bool] = False
        self._target_rpm = self.default_rpm
        self._enabled = enabled
        self._mcc = mcc
        mcc.fans_error_changed.connect(self._on_fans_error_changed)
        mcc.fans_rpm_changed.connect(self._on_fans_rpm_changed)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        self._mcc.set_fan_enabled(self._index, value)
        self._mcc.set_fan_rpm(self._index, self.target_rpm)  # MC forgets RPM configuration ???

    @property
    def rpm(self) -> int:
        return self._rpm

    @property
    def target_rpm(self) -> int:
        return self._target_rpm

    @target_rpm.setter
    def target_rpm(self, value: int):
        if not self.min_rpm <= value <= self.max_rpm:
            raise ValueError("RPM out of range")
        self._target_rpm = value
        self._mcc.set_fan_rpm(self._index, value)

    @property
    def error(self) -> bool:
        return self._error

    async def run(self):
        await super().run()
        self.target_rpm = self.default_rpm

    def _on_fans_rpm_changed(self, rpms: Dict[int, int]):
        if rpms[self._index] != self._rpm:
            self._rpm = rpms[self._index]
            self.rpm_changed.emit(self._rpm)

    def _on_fans_error_changed(self, error: Dict[int, bool]):
        if error[self._index] != self._error:
            self._error = error[self._index]
            self.error_changed.emit(self._error)


class SL1FanUVLED(SL1Fan):
    def __init__(
        self,
        mcc: MotionController,
        config: HwConfig,
        reference: TempSensor,
        auto_control_inhibitor: Callable[[], bool] = lambda: False,
    ):
        super().__init__(
            mcc,
            "UV LED",
            0,
            defines.fanMinRPM,
            defines.fanMaxRPM[0],
            config.fan1Rpm,
            config.fan1Enabled,
            reference=reference,
            auto_control_inhibitor=auto_control_inhibitor,
        )


class SL1FanBlower(SL1Fan):
    def __init__(self, mcc: MotionController, config: HwConfig):
        super().__init__(
            mcc,
            "Blower",
            1,
            defines.fanMinRPM,
            defines.fanMaxRPM[1],
            config.fan2Rpm,
            config.fan2Enabled,
        )


class SL1FanRear(SL1Fan):
    def __init__(self, mcc: MotionController, config: HwConfig):
        super().__init__(
            mcc,
            "Rear",
            2,
            defines.fanMinRPM,
            defines.fanMaxRPM[2],
            config.fan3Rpm,
            config.fan3Enabled,
        )
