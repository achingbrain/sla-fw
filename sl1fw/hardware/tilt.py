# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from abc import abstractmethod
from time import sleep
from enum import unique, Enum
from typing import List, Dict
import logging

from PySignal import Signal

from sl1fw import defines
from sl1fw.motion_controller.controller import MotionController
from sl1fw.configs.hw import HwConfig
from sl1fw.functions.decorators import safe_call
from sl1fw.errors.errors import TiltPositionFailed, TiltHomeFailed, MotionControllerException
from sl1fw.hardware.axis import Axis, AxisProfileBase


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
    def __init__(self):
        super().__init__()
        self.movement_ended = Signal()

    @abstractmethod
    def go_to_fullstep(self, goUp: int):
        """move axis to the fullstep (stable position) in given direction"""

    @abstractmethod
    def move_down(self):
        """move tilt to zero"""

    @abstractmethod
    def move_down_wait(self):
        """move tilt to zero (synchronous)"""

    @abstractmethod
    def move_up(self):
        """move tilt to max"""

    @abstractmethod
    def move_up_wait(self):
        """move tilt to max (synchronous)"""

    @abstractmethod
    def layer_up_wait(self, slowMove: bool = False, tiltHeight: int = 0) -> None:
        """tilt up during the print"""

    def layer_down_wait(self, slowMove: bool = False) -> None:
        """tilt up during the print"""
        asyncio.run(self.layer_down_wait_async(slowMove=slowMove))

    @abstractmethod
    async def layer_down_wait_async(self, slowMove: bool = False) -> None:
        """tilt up during the print"""

    @abstractmethod
    def stir_resin(self):
        """mix the resin"""

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


class TiltSL1(Tilt):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    def __init__(self, mcc: MotionController, config: HwConfig):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._mcc = mcc
        self._config = config
        self._targetPosition: int = 0
        self._lastPosition: int = 0

        self._sensitivity = {
            #                -2       -1        0        +1       +2
            "homingFast": [[20, 5], [20, 6], [20, 7], [21, 9], [22, 12]],
            "homingSlow": [[16, 3], [16, 5], [16, 7], [16, 9], [16, 11]],
        }

########## position/movement ##########

    @property
    def max(self) -> int:
        return self._config.tiltMax

    @property
    def min(self) -> int:
        return self._config.tiltMin

    @property
    @safe_call(False, MotionControllerException)
    def position(self) -> int:
        return self._mcc.doGetInt("?tipo")

    @position.setter
    @safe_call(-1, MotionControllerException)
    def position(self, position_ustep):
        if self.moving:
            raise TiltPositionFailed("Failed to set tilt position since its moving")
        self._mcc.do("!tipo", position_ustep)
        self._targetPosition = position_ustep

    @property
    def target_position(self) -> int:
        return self._targetPosition

    @property
    @safe_call(False, MotionControllerException)
    def on_target_position(self):
        if self.moving:
            return False
        if self.position != self._targetPosition:
            self.logger.warning(
                "Tilt is not on required position! Actual position: %d, Target position: %d ",
                self.position,
                self._targetPosition,
            )
            return False
        return True

    @property
    @safe_call(False, MotionControllerException)
    def moving(self):
        if self._mcc.doGetInt("?mot") & 2:
            return True
        return False

    @safe_call(False, MotionControllerException)
    def move_absolute(self, position):
        self._targetPosition = position
        self._mcc.do("!tima", position)

    @safe_call(False, MotionControllerException)
    def move(self, speed: int, set_profiles: bool = True, fullstep=False) -> bool:
        """
        Start / stop tilt movement

        TODO: This should be checked by heartbeat or the command should have limited ttl

        :param: Movement speed

           :-2: Fast down
           :-1: Slow down
           :0: Stop
           :1: Slow up
           :2: Fast up
        :return: True on success, False otherwise
        """
        if not self.moving and set_profiles:
            self.profile_id = TiltProfile.moveSlow if abs(speed) < 2 else TiltProfile.homingFast

        if speed != 0:
            self._lastPosition = self.position
            if self.moving:
                if self.on_target_position:
                    return False
            else:
                self.move_absolute(
                    self._config.tiltMax if speed > 0 else 0
                )
            return True

        self.stop()
        if fullstep:
            if self._lastPosition < self.position:
                self.go_to_fullstep(goUp=1)
            elif self._lastPosition > self.position:
                self.go_to_fullstep(goUp=0)
            self._lastPosition = self._config.tiltMin
        self.movement_ended.emit()
        return True

    @safe_call(False, MotionControllerException)
    def stop(self):
        self._mcc.do("!mot", 1)

    @safe_call(False, MotionControllerException)
    def go_to_fullstep(self, goUp: int = 0):
        self._mcc.do("!tigf", goUp)

    @safe_call(False, MotionControllerException)
    def move_down(self):
        self.move_absolute(0)

    @safe_call(False, MotionControllerException)
    def move_down_wait(self):
        self.move_down()
        while not self.on_target_position:
            sleep(0.1)

    @safe_call(False, MotionControllerException)
    def move_up(self):
        self.move_absolute(self._config.tiltHeight)

    @safe_call(False, MotionControllerException)
    def move_up_wait(self):
        self.move_up()
        while not self.on_target_position:
            sleep(0.1)

    @safe_call(False, MotionControllerException)
    async def layer_down_wait_async(self, slowMove: bool = False) -> None:
        profile = self._config.tuneTilt[0] if slowMove else self._config.tuneTilt[1]
        # initial release movement with optional sleep at the end
        self.profile_id = TiltProfile(profile[0])
        if profile[1] > 0:
            self.move_absolute(self.position - profile[1])
            while self.moving:
                await asyncio.sleep(0.1)
        await asyncio.sleep(profile[2] / 1000.0)
        # next movement may be splited
        self.profile_id = TiltProfile(profile[3])
        movePerCycle = int(self.position / profile[4])
        for _ in range(profile[4]):
            self.move_absolute(self.position - movePerCycle)
            while self.moving:
                await asyncio.sleep(0.1)
            await asyncio.sleep(profile[5] / 1000.0)
        tolerance = defines.tiltHomingTolerance
        # if not already in endstop ensure we end up at defined bottom position
        if not self._mcc.checkState("endstop"):
            self.move_absolute(-tolerance)
            # tilt will stop moving on endstop OR by stallguard
            while self.moving:
                await asyncio.sleep(0.1)
        # check if tilt is on endstop and within tolerance
        if self._mcc.checkState("endstop") and -tolerance <= self.position <= tolerance:
            return
        # unstuck
        self.logger.warning("Tilt unstucking")
        self.profile_id = TiltProfile.layerRelease
        count = 0
        step = 128
        while count < self._config.tiltMax and not self._mcc.checkState("endstop"):
            self.position = step
            self.move_absolute(0)
            while self.moving:
                await asyncio.sleep(0.1)
            count += step
        await self.sync_wait_async(retries=0)

    @safe_call(False, MotionControllerException)
    def layer_up_wait(self, slowMove: bool = False, tiltHeight: int = 0) -> None:
        if tiltHeight == 0: # use self._config.tiltHeight by default
            _tiltHeight = self._config.tiltHeight
        else: # in case of calibration there is need to force new unstored tiltHeight
            _tiltHeight = tiltHeight
        profile = self._config.tuneTilt[2] if slowMove else self._config.tuneTilt[3]

        self.profile_id = TiltProfile(profile[0])
        self.move_absolute(_tiltHeight - profile[1])
        while self.moving:
            sleep(0.1)
        sleep(profile[2] / 1000.0)
        self.profile_id = TiltProfile(profile[3])

        # finish move may be also splited in multiple sections
        movePerCycle = int((_tiltHeight - self.position) / profile[4])
        for _ in range(profile[4]):
            self.move_absolute(self.position + movePerCycle)
            while self.moving:
                sleep(0.1)
            sleep(profile[5] / 1000.0)

    @safe_call(False, MotionControllerException)
    def stir_resin(self) -> None:
        for _ in range(self._config.stirringMoves):
            self.profile_id = TiltProfile.homingFast
            # do not verify end positions
            self.move_up()
            while self.moving:
                sleep(0.1)
            self.move_down()
            while self.moving:
                sleep(0.1)
            self.sync_wait()

    @safe_call(False, MotionControllerException)
    def level(self) -> None:
        # assume tilt is up (there may be error from print)
        self.position = self.max
        self.layer_down_wait()
        if not self.synced:
            self.sync_wait()
        self.profile_id = TiltProfile.moveFast
        self.layer_up_wait()

########## homing ##########

    @property
    def synced(self) -> bool:
        return self.homing_status == 0

    @property
    @safe_call(-1, MotionControllerException)
    def homing_status(self) -> int:
        return self._mcc.doGetInt("?tiho")

    @safe_call(False, MotionControllerException)
    def sync(self):
        self._mcc.do("!tiho")

    @safe_call(False, (MotionControllerException, TiltHomeFailed))
    async def sync_wait_async(self, retries: int = 2) -> None:
        self.sync()
        while True:
            homing_status = self.homing_status
            if homing_status == 0:
                self.position = 0
                return
            if homing_status < 0:
                self.logger.warning("Tilt homing failed! Status: %d", homing_status)
                if retries < 1:
                    self.logger.error("Tilt homing max tries reached!")
                    raise TiltHomeFailed()
                retries -= 1
                self.sync()
            await asyncio.sleep(0.25)

    @safe_call(False, MotionControllerException)
    async def home_calibrate_wait_async(self):
        self._mcc.do("!tihc")
        homing_status = 1
        while homing_status > 0:  # not done and not error
            homing_status = self.homing_status
            if homing_status < 0:
                raise MotionControllerException("Tilt homing calibration failed", None)
            await asyncio.sleep(0.1)
        self.position = 0

########## profiles ##########

    @property
    @safe_call(False, MotionControllerException)
    def profile_id(self) -> TiltProfile:
        """return selected profile"""
        return TiltProfile(self._mcc.doGetInt("?tics"))

    @profile_id.setter
    @safe_call(False, MotionControllerException)
    def profile_id(self, profile_id: TiltProfile):
        """select profile"""
        if self.moving:
            raise MotionControllerException(
                "Cannot change profiles while tilt is moving.", None
            )
        self._mcc.do("!tics", profile_id.value)

    @property
    @safe_call(False, MotionControllerException)
    def profile(self) -> List[int]:
        """get values of currently selected profile in MC"""
        return self._mcc.doGetIntList("?ticf")

    @profile.setter
    @safe_call(False, MotionControllerException)
    def profile(self, profile):
        """update values of currently selected profile in MC"""
        if self.moving:
            raise MotionControllerException(
                "Cannot edit profile while tilt is moving.", None
            )
        self._mcc.do("!ticf", *profile)

    @property
    @safe_call(False, MotionControllerException)
    def profiles(self) -> List[List[int]]:
        """get all profiles from MC"""
        profiles = list()
        for profile_id in range(8):
            profiles.append(self._mcc.doGetIntList("?ticf %d" % profile_id))
        return profiles

    @profiles.setter
    @safe_call(False, MotionControllerException)
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
    def sensitivity_dict(self) -> Dict[str, List[List[int]]]:
        return self._sensitivity
