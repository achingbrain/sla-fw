# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
from abc import abstractmethod, ABC
from typing import Optional, Callable

from PySignal import Signal

from slafw.hardware.base.component import HardwareComponent
from slafw.hardware.base.temp_sensor import TempSensor


class FanState:
    # pylint: disable = too-few-public-methods
    """
    Capture fan state, allows to restore it
    """

    def __init__(self, fan: Fan):
        self._fan = fan
        self._enabled = fan.enabled
        self._target_rpm = fan.target_rpm
        self._auto_control = fan.auto_control

    def restore(self):
        self._fan.enabled = self._enabled
        self._fan.target_rpm = self._target_rpm
        self._fan.auto_control = self._auto_control


class Fan(HardwareComponent, ABC):
    # pylint: disable = too-many-arguments
    # pylint: disable = too-many-instance-attributes

    AUTO_CONTROL_INTERVAL_S = 30
    VALUE_LOGGING_THRESHOLD_RPM = 500

    def __init__(
        self,
        name: str,
        min_rpm: int,
        max_rpm: int,
        default_rpm: int,
        reference: Optional[TempSensor] = None,
        auto_control_inhibitor: Callable[[], bool] = lambda: False,
    ):
        super().__init__(name)
        self.rpm_changed = Signal()
        self.error_changed = Signal()
        self._min_rpm = min_rpm
        self._max_rpm = max_rpm
        self._default_rpm = default_rpm
        self._reference = reference
        self._auto_control = bool(reference)
        self._auto_control_inhibitor = auto_control_inhibitor
        self._last_logged_rpm: Optional[int] = None

        self.rpm_changed.connect(self._on_rpm_changed)
        self.error_changed.connect(self._on_error_changed)

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """
        Whenever fan is enabled
        """
        ...

    @enabled.setter
    @abstractmethod
    def enabled(self, value: bool):
        ...

    @property
    @abstractmethod
    def rpm(self) -> int:
        """
        Fan RPM as reported by the fan
        """
        ...

    @property
    @abstractmethod
    def error(self) -> bool:
        """
        Fan failed status as reported by the fan
        """
        ...

    @property
    @abstractmethod
    def target_rpm(self) -> int:
        """
        Target RPM to be maintained by fan
        """
        ...

    @target_rpm.setter
    @abstractmethod
    def target_rpm(self, rpm: int):
        ...

    @property
    def default_rpm(self) -> int:
        return self._default_rpm

    @default_rpm.setter
    def default_rpm(self, rpm: int):
        self._default_rpm = rpm

    @property
    def min_rpm(self) -> int:
        return self._min_rpm

    @property
    def max_rpm(self) -> int:
        return self._max_rpm

    @property
    def auto_control(self):
        return self._auto_control

    @auto_control.setter
    def auto_control(self, value: bool):
        if value and not self._reference:
            raise ValueError("Cannot set auto control, no reference temperature sensor")

        self._auto_control = value

    async def run(self):
        await super().run()
        if self._reference:
            await asyncio.create_task(self._fan_rpm_control_task())

    async def _fan_rpm_control_task(self):
        """
        Automatic RPM control based on reference temp sensor value
        """
        self._logger.info("Starting automatic RPM control")
        while True:
            try:
                await asyncio.sleep(self.AUTO_CONTROL_INTERVAL_S)
                await self._fan_rpm_control()
            except Exception:
                self._logger.exception("Fan auto RPM control crashed - running at max RPM")
                self.target_rpm = self.max_rpm
                raise

    async def _fan_rpm_control(self):
        if not self.auto_control:
            self._logger.debug("Skipping auto control - disabled")
            return

        if self._auto_control_inhibitor():
            self._logger.info("Skipping auto control - inhibited")
            return

        map_constant = (self.max_rpm - self.min_rpm) / (self._reference.max - self._reference.min)
        rpm = round((self._reference.value - self._reference.min) * map_constant + self.min_rpm)
        rpm = max(min(rpm, self.max_rpm), self.min_rpm)
        self._logger.debug("Fan RPM control setting RPMs: %s", rpm)
        self.target_rpm = rpm

    def _on_rpm_changed(self, rpm: int):
        if rpm is not None and (
            self._last_logged_rpm is None or abs(self._last_logged_rpm - rpm) > self.VALUE_LOGGING_THRESHOLD_RPM
        ):
            self._logger.info("%d RPMs", rpm)
            self._last_logged_rpm = rpm

    def _on_error_changed(self, error: bool):
        if error:
            self._logger.error("Failed")
        else:
            self._logger.info("Recovered")
