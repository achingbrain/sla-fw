# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Callable, Optional

from slafw.hardware.base.fan import Fan
from slafw.hardware.base.temp_sensor import TempSensor


class MockFan(Fan):
    # pylint: disable = too-many-arguments
    def __init__(
        self,
        name,
        min_rpm: int,
        max_rpm: int,
        default_rpm: int,
        reference: Optional[TempSensor] = None,
        auto_control_inhibitor: Callable[[], bool] = lambda: False,
    ):
        super().__init__(
            name, min_rpm, max_rpm, default_rpm, reference=reference, auto_control_inhibitor=auto_control_inhibitor
        )
        self._enabled = False
        self._target_rpm = default_rpm

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def rpm(self) -> int:
        return self._target_rpm

    @property
    def error(self) -> bool:
        return False

    @property
    def target_rpm(self) -> int:
        return self._target_rpm

    @target_rpm.setter
    def target_rpm(self, value: bool):
        self._target_rpm = value
