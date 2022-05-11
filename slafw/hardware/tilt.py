# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from abc import abstractmethod
from functools import cached_property

from slafw.configs.unit import Ustep
from slafw.errors.errors import TiltMoveFailed, TiltHomeFailed
from slafw.hardware.axis import Axis


class Tilt(Axis):

    @property
    def name(self) -> str:
        return "tilt"

    @cached_property
    def sensitivity(self) -> int:
        return self._config.tiltSensitivity

    @cached_property
    def home_position(self) -> Ustep:
        return Ustep(0)

    @cached_property
    def config_height_position(self) -> Ustep:
        return self._config.tiltHeight

    @cached_property
    def minimal_position(self) -> Ustep:
        return self.home_position

    @abstractmethod
    def layer_up_wait(self, slowMove: bool = False, tiltHeight: Ustep = Ustep(0)) -> None:
        """tilt up during the print"""

    def layer_down_wait(self, slowMove: bool = False) -> None:
        asyncio.run(self.layer_down_wait_async(slowMove=slowMove))

    @abstractmethod
    async def layer_down_wait_async(self, slowMove: bool = False) -> None:
        """tilt up during the print"""

    def stir_resin(self) -> None:
        asyncio.run(self.stir_resin_async())

    @abstractmethod
    async def stir_resin_async(self) -> None:
        """stiring moves of tilt."""

    def _move_api_min(self) -> None:
        self.move(self.home_position)

    def _move_api_max(self) -> None:
        self.move(self._config.tiltMax)

    @staticmethod
    def _raise_move_failed():
        raise TiltMoveFailed()

    @staticmethod
    def _raise_home_failed():
        raise TiltHomeFailed()
