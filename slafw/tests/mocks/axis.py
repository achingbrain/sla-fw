# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from typing import List

from slafw.configs.hw import HwConfig
from slafw.hardware.axis import Axis, AxisProfileBase, HomingStatus
from slafw.hardware.power_led import PowerLed
from slafw.hardware.tilt import Tilt
from slafw.hardware.tower import Tower
from slafw.motion_controller.controller import MotionController


class MockAxis(Axis):
    # pylint: disable = too-many-arguments
    def __init__(self, mcc: MotionController, config: HwConfig,
                 power_led: PowerLed):
        super().__init__(config, power_led)
        self._mcc = mcc
        self._target_position = 0
        self._homing_status = HomingStatus.UNKNOWN
        self._current_profile = None

    @property
    def position(self) -> int:
        return self._target_position

    @position.setter
    def position(self, position):
        self._target_position = position

    @property
    def moving(self) -> bool:
        return False

    def move(self, position: int) -> None:
        self.position = position

    def stop(self) -> None:
        self.position = self.position

    def release(self) -> None:
        self._homing_status = HomingStatus.UNKNOWN

    def go_to_fullstep(self, go_up: bool):
        pass

    def sync(self) -> None:
        self._homing_status = HomingStatus.SYNCED

    @property
    def homing_status(self) -> HomingStatus:
        return self._homing_status

    async def home_calibrate_wait_async(self):
        pass

    async def verify_async(self) -> None:
        self.sync()

    @property
    def profile_names(self) -> List[str]:
        pass

    @property
    def profile_id(self) -> AxisProfileBase:
        return self._current_profile

    @profile_id.setter
    def profile_id(self, profile_id: AxisProfileBase):
        self._current_profile = profile_id

    @property
    def profile(self) -> List[int]:
        pass

    @property
    def profiles(self) -> List[List[int]]:
        pass

    def sensitivity(self) -> int:
        pass

    def _move_api_get_profile(self, speed: int) -> AxisProfileBase:
        pass


class MockTower(Tower, MockAxis):
    pass


class MockTilt(Tilt, MockAxis):
    def layer_up_wait(self, slowMove: bool = False,
                      tiltHeight: int = 0) -> None:
        self.move(self._config.tiltHeight)

    async def layer_down_wait_async(self, slowMove: bool = False) -> None:
        self._move_api_min()

    async def stir_resin_async(self) -> None:
        pass
