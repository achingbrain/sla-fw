# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from enum import unique
from time import sleep
from typing import List

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.errors.errors import MotionControllerException, TiltPositionFailed
from slafw.hardware.axis import AxisProfileBase, HomingStatus
from slafw.hardware.power_led import PowerLed
from slafw.hardware.sl1.tower import TowerSL1
from slafw.hardware.tilt import Tilt
from slafw.motion_controller.controller import MotionController



@unique
class TiltProfile(AxisProfileBase):
    temp = -1
    homingFast = 0
    homingSlow = 1
    moveFast = 2
    moveSlow = 3
    layerMoveSlow = 4
    layerRelease = 5
    layerMoveFast = 6
    reserved2 = 7


class TiltSL1(Tilt):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    def __init__(self, mcc: MotionController, config: HwConfig,
                 power_led: PowerLed, tower: TowerSL1):
        super().__init__(config, power_led)
        self._mcc = mcc
        self._tower = tower
        self._sensitivity = {
            #                -2       -1        0        +1       +2
            "homingFast": [[20, 5], [20, 6], [20, 7], [21, 9], [22, 12]],
            "homingSlow": [[16, 3], [16, 5], [16, 7], [16, 9], [16, 11]],
        }

    @property
    def position(self) -> int:
        return self._mcc.doGetInt("?tipo")

    # TODO: force unit check
    @position.setter
    def position(self, position):
        if self.moving:
            raise TiltPositionFailed("Failed to set tilt position since its moving")
        self._mcc.do("!tipo", position)
        self._target_position = position
        self._logger.debug("Position set to: %d nm", self._target_position)

    @property
    def moving(self):
        if self._mcc.doGetInt("?mot") & 2:
            return True
        return False

    # TODO: force unit check
    def move(self, position):
        self._mcc.do("!tima", position)
        self._target_position = position
        self._logger.debug("Move initiated. Target position: %d nm",
                           self._target_position)

    def _move_api_get_profile(self, speed) -> TiltProfile:
        if abs(speed) < 2:
            return TiltProfile.moveSlow
        return TiltProfile.homingFast

    def stop(self):
        axis_moving = self._mcc.doGetInt("?mot")
        self._mcc.do("!mot", axis_moving & ~2)
        self._target_position = self.position
        self._logger.debug("Move stopped. Rewriting target position to: %d nm",
                           self._target_position)

    def go_to_fullstep(self, go_up: bool):
        self._mcc.do("!tigf", int(go_up))

    async def layer_down_wait_async(self, slowMove: bool = False) -> None:
        profile = self._config.tuneTilt[0] if slowMove else self._config.tuneTilt[1]
        # initial release movement with optional sleep at the end
        self.profile_id = TiltProfile(profile[0])
        if profile[1] > 0:
            self.move(self.position - profile[1])
            while self.moving:
                await asyncio.sleep(0.1)
        await asyncio.sleep(profile[2] / 1000.0)
        # next movement may be splited
        self.profile_id = TiltProfile(profile[3])
        movePerCycle = int(self.position / profile[4])
        for _ in range(profile[4]):
            self.move(self.position - movePerCycle)
            while self.moving:
                await asyncio.sleep(0.1)
            await asyncio.sleep(profile[5] / 1000.0)
        tolerance = defines.tiltHomingTolerance
        # if not already in endstop ensure we end up at defined bottom position
        if not self._mcc.checkState("endstop"):
            self.move(-tolerance)
            # tilt will stop moving on endstop OR by stallguard
            while self.moving:
                await asyncio.sleep(0.1)
        # check if tilt is on endstop and within tolerance
        if self._mcc.checkState("endstop") and -tolerance <= self.position <= tolerance:
            return
        # unstuck
        self._logger.warning("Tilt unstucking")
        self.profile_id = TiltProfile.layerRelease
        count = 0
        step = 128
        while count < self._config.tiltMax and not self._mcc.checkState("endstop"):
            self.position = step
            self.move(self.home_position)
            while self.moving:
                await asyncio.sleep(0.1)
            count += step
        await self.sync_wait_async(retries=0)

    # TODO: force unit check
    def layer_up_wait(self, slowMove: bool = False, tiltHeight: int = 0) -> None:
        if tiltHeight == self.home_position: # use self._config.tiltHeight by default
            _tiltHeight = self.config_height_position
        else: # in case of calibration there is need to force new unstored tiltHeight
            _tiltHeight = tiltHeight
        profile = self._config.tuneTilt[2] if slowMove else self._config.tuneTilt[3]

        self.profile_id = TiltProfile(profile[0])
        self.move(_tiltHeight - profile[1])
        while self.moving:
            sleep(0.1)
        sleep(profile[2] / 1000.0)
        self.profile_id = TiltProfile(profile[3])

        # finish move may be also splited in multiple sections
        movePerCycle = int((_tiltHeight - self.position) / profile[4])
        for _ in range(profile[4]):
            self.move(self.position + movePerCycle)
            while self.moving:
                sleep(0.1)
            sleep(profile[5] / 1000.0)

    def release(self) -> None:
        axis_enabled = self._mcc.doGetInt("?ena")
        self._mcc.do("!ena", axis_enabled & ~2)

    async def stir_resin_async(self) -> None:
        for _ in range(self._config.stirringMoves):
            self.profile_id = TiltProfile.homingFast
            # do not verify end positions
            self.move(self._config.tiltHeight)
            while self.moving:
                sleep(0.1)
            self.move(self.home_position)
            while self.moving:
                sleep(0.1)
            await self.sync_wait_async()

    @property
    def homing_status(self) -> HomingStatus:
        return HomingStatus(self._mcc.doGetInt("?tiho"))

    def sync(self) -> None:
        self._mcc.do("!tiho")
        sleep(0.1)  #FIXME: mc-fw does not start the movement immediately -> wait a bit

    async def home_calibrate_wait_async(self):
        self._mcc.do("!tihc")
        await super().home_calibrate_wait_async()
        self.position = self.home_position

    async def verify_async(self) -> None:
        if not self.synced:
            while self._tower.moving:
                await asyncio.sleep(0.25)
            await self.sync_wait_async()
        self.profile_id = TiltProfile.moveFast
        await self.move_ensure_async(self._config.tiltHeight)

    @property
    def profile_id(self) -> TiltProfile:
        """return selected profile"""
        return TiltProfile(self._mcc.doGetInt("?tics"))

    @profile_id.setter
    def profile_id(self, profile_id: TiltProfile):
        """select profile"""
        if self.moving:
            raise MotionControllerException(
                "Cannot change profiles while tilt is moving.", None
            )
        if self._current_profile != profile_id:
            self._mcc.do("!tics", profile_id.value)
            self._current_profile = profile_id
            self._logger.debug("Profile set to: %s", self._current_profile)

    @property
    def profile(self) -> List[int]:
        """get values of currently selected profile in MC"""
        return self._mcc.doGetIntList("?ticf")

    @profile.setter
    def profile(self, profile: List[int]):
        """update values of currently selected profile in MC"""
        if self.moving:
            raise MotionControllerException(
                "Cannot edit profile while tilt is moving.", None
            )
        self._mcc.do("!ticf", *profile)

    @property
    def profiles(self) -> List[List[int]]:
        """get all profiles from MC"""
        profiles = list()
        for profile_id in range(8):
            profiles.append(self._mcc.doGetIntList("?ticf %d" % profile_id))
        return profiles

    @profiles.setter
    def profiles(self, profiles: List[List[int]]):
        """save all profiles to MC"""
        currentProfile = self.profile_id
        if len(profiles) != 8:
            raise MotionControllerException("Wrong number of profiles passed", None)
        currentProfile = self.profile_id
        for profile_id in range(8):
            self.profile_id = TiltProfile(profile_id)
            self.profile = profiles[profile_id]
        self.profile_id = currentProfile

    @property
    def profile_names(self) -> List[str]:
        return [profile.name for profile in TiltProfile]
