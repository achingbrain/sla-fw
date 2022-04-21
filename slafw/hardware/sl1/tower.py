# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique
from typing import List

from slafw.configs.hw import HwConfig
from slafw.configs.unit import Nm
from slafw.errors.errors import MotionControllerException, \
    TowerPositionFailed
from slafw.hardware.axis import AxisProfileBase, HomingStatus
from slafw.hardware.power_led import PowerLed
from slafw.hardware.tower import Tower
from slafw.motion_controller.controller import MotionController


@unique
class TowerProfile(AxisProfileBase):
    temp = -1
    homingFast = 0
    homingSlow = 1
    moveFast = 2
    moveSlow = 3
    layer = 4
    layerMove = 5
    superSlow = 6
    resinSensor = 7


class TowerSL1(Tower):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    def __init__(self, mcc: MotionController, config: HwConfig, power_led: PowerLed):
        super().__init__(config, power_led)
        self._mcc = mcc
        self._sensitivity = {
            #                -2       -1        0        +1       +2
            "homingFast": [[22, 0], [22, 2], [22, 4], [22, 6], [22, 8]],
            "homingSlow": [[14, 0], [15, 0], [16, 1], [16, 3], [16, 5]],
        }

    @property
    def position(self) -> Nm:
        return self._config.tower_microsteps_to_nm(self._mcc.doGetInt("?twpo"))

    @position.setter
    def position(self, position: Nm) -> None:
        self._check_units(position, Nm)
        if self.moving:
            raise TowerPositionFailed(
                "Failed to set tower position since its moving")
        self._mcc.do("!twpo", int(self._config.nm_to_tower_microsteps(position)))
        self._target_position = position
        self._logger.debug("Position set to: %d nm", self._target_position)

    @property
    def moving(self):
        if self._mcc.doGetInt("?mot") & 1:
            return True
        return False

    def move(self, position: Nm) -> None:
        self._check_units(position, Nm)
        self._mcc.do("!twma", int(self._config.nm_to_tower_microsteps(position)))
        self._target_position = position
        self._logger.debug("Move initiated. Target position: %d nm", position)

    # TODO use !brk instead. Motor might stall at !mot 0
    def stop(self):
        axis_moving = self._mcc.doGetInt("?mot")
        self._mcc.do("!mot", axis_moving & ~1)
        self._target_position = self.position
        self._logger.debug("Move stopped. Rewriting target position to: %d nm", self._target_position)

    def go_to_fullstep(self, go_up: bool):
        self._mcc.do("!twgf", int(go_up))

    def release(self) -> None:
        axis_enabled = self._mcc.doGetInt("?ena")
        self._mcc.do("!ena", axis_enabled & ~1)

    @property
    def homing_status(self) -> HomingStatus:
        return HomingStatus(self._mcc.doGetInt("?twho"))

    def sync(self):
        self._mcc.do("!twho")

    async def home_calibrate_wait_async(self):
        self._mcc.do("!twhc")
        await super().home_calibrate_wait_async()

    async def verify_async(self) -> None:
        if not self.synced:
            await self.sync_ensure_async()
        else:
            self.profile_id = TowerProfile.moveFast
            await self.move_ensure_async(self._config.tower_height_nm)

    @property
    def profile_id(self) -> TowerProfile:
        return TowerProfile(self._mcc.doGetInt("?twcs"))

    @profile_id.setter
    def profile_id(self, profile_id: TowerProfile):
        if self.moving:
            raise MotionControllerException(
                "Cannot change profiles while tower is moving.", None
            )
        if self._current_profile != profile_id:
            self._mcc.do("!twcs", profile_id.value)
            self._current_profile = profile_id
            self._logger.debug("Profile set to: %s", self._current_profile)

    @property
    def profile(self) -> List[int]:
        return self._mcc.doGetIntList("?twcf")

    @profile.setter
    def profile(self, profile: List[int]):
        if self.moving:
            raise MotionControllerException(
                "Cannot edit profile while tower is moving.", None
            )
        self._mcc.do("!twcf", *profile)

    @property
    def profiles(self) -> List[List[int]]:
        profiles = list()
        for profile_id in range(8):
            profiles.append(self._mcc.doGetIntList("?twcf %d" % profile_id))
        return profiles

    @profiles.setter
    def profiles(self, profiles: List[List[int]]):
        if len(profiles) != 8:
            raise MotionControllerException("Wrong number of profiles passed",
                                            None)
        currentProfile = self.profile_id
        for profile_id in range(8):
            self.profile_id = TowerProfile(profile_id)
            self.profile = profiles[profile_id]
        self.profile_id = currentProfile

    @property
    def profile_names(self) -> List[str]:
        return [profile.name for profile in TowerProfile]

    def _move_api_get_profile(self, speed) -> TowerProfile:
        if abs(speed) < 2:
            return TowerProfile.moveSlow
        return TowerProfile.homingFast
