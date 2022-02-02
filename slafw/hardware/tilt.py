# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from abc import abstractmethod
from time import sleep
from enum import unique, Enum
from typing import List, Dict
import logging

from PySignal import Signal

from slafw import defines
from slafw.motion_controller.controller import MotionController
from slafw.configs.hw import HwConfig
from slafw.functions.decorators import safe_call
from slafw.errors.errors import TiltPositionFailed, TiltHomeFailed, MotionControllerException
from slafw.hardware.axis import Axis, AxisProfileBase


@unique
class TiltProfile(AxisProfileBase, Enum):
    temp = -1
    homingFast = 0
    homingSlow = 1
    moveFast = 2
    moveSlow = 3
    layerMoveSlow = 4
    layerRelease = 5
    layerMoveFast = 6
    reserved2 = 7


class Tilt(Axis):
    def __init__(self, config: HwConfig):
        super().__init__()
        self.movement_ended = Signal()
        self._config = config

    @abstractmethod
    def go_to_fullstep(self, goUp: int):
        """move axis to the fullstep (stable position) in given direction"""

    @abstractmethod
    def move_down(self):
        """move tilt to zero"""

    @safe_call(False, MotionControllerException)
    def move_down_wait(self):
        self.move_down()
        while not self.on_target_position:
            sleep(0.1)

    @abstractmethod
    def move_up(self):
        """move tilt to max"""

    @safe_call(False, MotionControllerException)
    def move_up_wait(self):
        self.move_up()
        while not self.on_target_position:
            sleep(0.1)

    @abstractmethod
    def layer_up_wait(self, slowMove: bool = False, tiltHeight: int = 0) -> None:
        """tilt up during the print"""

    def layer_down_wait(self, slowMove: bool = False) -> None:
        """tilt up during the print"""
        asyncio.run(self.layer_down_wait_async(slowMove=slowMove))

    @abstractmethod
    async def layer_down_wait_async(self, slowMove: bool = False) -> None:
        """tilt up during the print"""

    @safe_call(False, MotionControllerException)
    def stir_resin(self) -> None:
        asyncio.run(self.stir_resin_async())

    @safe_call(False, MotionControllerException)
    async def stir_resin_async(self) -> None:
        for _ in range(self._config.stirringMoves):
            self.profile_id = TiltProfile.homingFast
            # do not verify end positions
            self.move_up()
            while self.moving:
                sleep(0.1)
            self.move_down()
            while self.moving:
                sleep(0.1)
            await self.sync_wait_async()

    def home_calibrate_wait(self):
        """test and save tilt motor phase for accurate homing"""
        return asyncio.run(self.home_calibrate_wait_async())

    @abstractmethod
    async def home_calibrate_wait_async(self):
        """test and save tilt motor phase for accurate homing"""

    @property
    def profile_names(self) -> List[str]:
        names = list()
        for profile in TiltProfile:
            names.append(profile.name)
        return names

    @abstractmethod
    def level(self) -> None:
        """Level tilt (print position)"""
