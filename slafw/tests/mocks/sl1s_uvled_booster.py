# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Tuple, List
from unittest.mock import Mock


class BoosterMock(Mock):
    _pwm = 0

    @staticmethod
    def status() -> Tuple[bool, List]:
        return True, [1, 2, 3]

    @property
    def pwm(self) -> int:
        return self._pwm

    @pwm.setter
    def pwm(self, pwm: int) -> None:
        self._pwm = pwm

    @property
    def board_serial_no(self) -> str:
        return "booster SN"