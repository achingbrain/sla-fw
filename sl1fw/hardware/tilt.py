# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import abstractmethod
from time import sleep
from enum import unique, Enum
from typing import List
import logging

from sl1fw import defines
from sl1fw.motion_controller.controller import MotionController
from sl1fw.configs.hw import HwConfig
from sl1fw.functions.decorators import safe_call
from sl1fw.errors.errors import TiltPositionFailed, TiltHomeFailed
from sl1fw.errors.exceptions import MotionControllerException
from sl1fw.hardware.axis import Axis


@unique
class TiltProfile(Enum):
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
    @abstractmethod
    def goToFullstep(self, goUp: int):
        """move axis to the fullstep (stable position) in given direction"""

    @abstractmethod
    def moveDown(self):
        """move tilt to zero"""

    @abstractmethod
    def moveDownWait(self):
        """move tilt to zero (synchronous)"""

    @abstractmethod
    def moveUp(self):
        """move tilt to max"""

    @abstractmethod
    def moveUpWait(self):
        """move tilt to max (synchronous)"""

    @abstractmethod
    def layerUpWait(self, slowMove: bool = False):
        """tilt up during the print"""

    @abstractmethod
    def layerDownWait(self, slowMove: bool = False) -> bool:
        """tilt up during the print"""

    @abstractmethod
    def stirResin(self):
        """mix the resin"""

    @abstractmethod
    def homeCalibrateWait(self):
        """test and save tilt motor phase for accurate homing"""

    @property
    def profileNames(self) -> List[str]:
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

        self._tiltAdjust = {
            #                          -2       -1        0        +1       +2
            TiltProfile.homingFast: [[20, 5], [20, 6], [20, 7], [21, 9], [22, 12]],
            TiltProfile.homingSlow: [[16, 3], [16, 5], [16, 7], [16, 9], [16, 11]],
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
    def targetPosition(self) -> int:
        return self._targetPosition

    @property
    @safe_call(False, MotionControllerException)
    def onTargetPosition(self):
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
    def moveAbsolute(self, position):
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
            self.profileId = TiltProfile.moveSlow if abs(speed) < 2 else TiltProfile.homingFast

        if speed != 0:
            self._lastPosition = self.position
            if self.moving:
                if self.onTargetPosition:
                    return False
            else:
                self.moveAbsolute(
                    self._config.tiltMax if speed > 0 else self._config.tiltMin
                )
            return True

        self.stop()
        if fullstep:
            if self._lastPosition < self.position:
                self.goToFullstep(goUp=1)
            elif self._lastPosition > self.position:
                self.goToFullstep(goUp=0)
            self._lastPosition = self._config.tiltMin
        return True

    @safe_call(False, MotionControllerException)
    def sensitivity(self, sensitivity: int = 0):
        if sensitivity < -2 or sensitivity > 2:
            raise ValueError("Sensitivity must be from -2 to +2")
        newProfiles = self.profiles
        newProfiles[0][4] = self._tiltAdjust[TiltProfile.homingFast][sensitivity + 2][0]
        newProfiles[0][5] = self._tiltAdjust[TiltProfile.homingFast][sensitivity + 2][1]
        newProfiles[1][4] = self._tiltAdjust[TiltProfile.homingSlow][sensitivity + 2][0]
        newProfiles[1][5] = self._tiltAdjust[TiltProfile.homingSlow][sensitivity + 2][1]
        self.profileId = TiltProfile.homingFast
        self.profile = newProfiles[TiltProfile.homingFast.value]
        self.profileId = TiltProfile.homingSlow
        self.profile = newProfiles[TiltProfile.homingSlow.value]
        self.logger.info("tilt profiles changed to: %s", newProfiles)

    @safe_call(False, MotionControllerException)
    def stop(self):
        self._mcc.do("!mot", 1)

    @safe_call(False, MotionControllerException)
    def goToFullstep(self, goUp: int = 0):
        self._mcc.do("!tigf", goUp)

    @safe_call(False, MotionControllerException)
    def moveDown(self):
        self.moveAbsolute(0)

    @safe_call(False, MotionControllerException)
    def moveDownWait(self):
        self.moveDown()
        while not self.onTargetPosition:
            sleep(0.1)

    @safe_call(False, MotionControllerException)
    def moveUp(self):
        self.moveAbsolute(self._config.tiltHeight)

    @safe_call(False, MotionControllerException)
    def moveUpWait(self):
        self.moveUp()
        while not self.onTargetPosition:
            sleep(0.1)


    @safe_call(False, MotionControllerException)
    def layerDownWait(self, slowMove: bool = False):
        profile = self._config.tuneTilt[0] if slowMove else self._config.tuneTilt[1]

        # initial release movement with optional sleep at the end
        self.profileId = TiltProfile(profile[0])
        if profile[1] > 0:
            self.moveAbsolute(self.position - profile[1])
            while self.moving:
                sleep(0.1)
        sleep(profile[2] / 1000.0)

        # next movement may be splited
        self.profileId = TiltProfile(profile[3])
        movePerCycle = int(self.position / profile[4])
        for _ in range(profile[4]):
            self.moveAbsolute(self.position - movePerCycle)
            while self.moving:
                sleep(0.1)
            sleep(profile[5] / 1000.0)

        # if not already in endstop ensure we end up at defined bottom position
        if not self._mcc.checkState("endstop"):
            self.moveAbsolute(-defines.tiltHomingTolerance)
            while self.moving:
                sleep(0.1)

        # check if tilt is on endstop
        if self._mcc.checkState("endstop"):
            if (
                -defines.tiltHomingTolerance
                <= self.position
                <= defines.tiltHomingTolerance
            ):
                return True

        # unstuck
        self.logger.warning("Tilt unstucking")
        self.profileId = TiltProfile.layerRelease
        count = 0
        step = 128
        while count < self._config.tiltMax and not self._mcc.checkState("endstop"):
            self.position = step
            self.moveAbsolute(0)
            while self.moving:
                sleep(0.1)
            count += step
        return self.syncWait(retries=1)

    @safe_call(False, MotionControllerException)
    def layerUpWait(self, slowMove: bool = False):
        profile = self._config.tuneTilt[2] if slowMove else self._config.tuneTilt[3]

        self.profileId = TiltProfile(profile[0])
        self.moveAbsolute(self._config.tiltHeight - profile[1])
        while self.moving:
            sleep(0.1)
        sleep(profile[2] / 1000.0)
        self.profileId = TiltProfile(profile[3])

        # finish move may be also splited in multiple sections
        movePerCycle = int((self._config.tiltHeight - self.position) / profile[4])
        for _ in range(profile[4]):
            self.moveAbsolute(self.position + movePerCycle)
            while self.moving:
                sleep(0.1)
            sleep(profile[5] / 1000.0)

    @safe_call(False, MotionControllerException)
    def stirResin(self):
        for _ in range(self._config.stirringMoves):
            self.profileId = TiltProfile.homingFast
            # do not verify end positions
            self.moveUp()
            while self.moving:
                sleep(0.1)

            self.moveDown()
            while self.moving:
                sleep(0.1)

            self.syncWait()


########## homing ##########

    @property
    def synced(self) -> bool:
        return self.homingStatus == 0

    @property
    @safe_call(-1, MotionControllerException)
    def homingStatus(self) -> int:
        return self._mcc.doGetInt("?tiho")

    @safe_call(False, MotionControllerException)
    def sync(self):
        self._mcc.do("!tiho")

    @safe_call(False, (MotionControllerException, TiltHomeFailed))
    def syncWait(self, retries=0):
        self.sync()

        while True:
            homingStatus = self.homingStatus
            if homingStatus == 0:
                self.position = 0
                return True

            if homingStatus < 0:
                self.logger.warning("Tilt homing failed! Status: %d", homingStatus)
                if retries < 1:
                    self.logger.error("Tilt homing max tries reached!")
                    raise TiltHomeFailed()
                retries -= 1
                self.sync()
            sleep(0.25)

    @safe_call(False, MotionControllerException)
    def homeCalibrateWait(self):
        self._mcc.do("!tihc")
        homingStatus = 1
        while homingStatus > 0:  # not done and not error
            homingStatus = self.homingStatus
            if homingStatus < 0:
                raise MotionControllerException("Tilt homing calibration failed", None)
            sleep(0.1)
        self.position = 0

########## profiles ##########

    @property
    @safe_call(False, MotionControllerException)
    def profileId(self) -> TiltProfile:
        """return selected profile"""
        return TiltProfile(self._mcc.doGetInt("?tics"))

    @profileId.setter
    @safe_call(False, MotionControllerException)
    def profileId(self, profileId: TiltProfile):
        """select profile"""
        if self.moving:
            raise MotionControllerException(
                "Cannot change profiles while tilt is moving.", None
            )
        self._mcc.do("!tics", profileId.value)

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
        currentProfile = self.profileId
        for profileId in range(8):
            try:
                self.profileId = TiltProfile(profileId)
                profiles.append(self.profile)
            finally:
                self.profileId = currentProfile
        return profiles

    @profiles.setter
    @safe_call(False, MotionControllerException)
    def profiles(self, profiles: List[List[int]]):
        """save all profiles to MC"""
        currentProfile = self.profileId
        if len(profiles) != 8:
            raise MotionControllerException("Wrong number of profiles passed", None)
        currentProfile = self.profileId
        for profileId in range(8):
            self.profileId = TiltProfile(profileId)
            self.profile = profiles[profileId]
        self.profileId = currentProfile
