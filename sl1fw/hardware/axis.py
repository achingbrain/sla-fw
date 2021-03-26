# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from enum import unique, Enum
from typing import List


@unique
class AxisProfile(Enum):
    temp = -1

class Axis(ABC):

########## position/movement ##########

    @property
    @abstractmethod
    def max(self) -> int:
        """return max tilt position"""

    @property
    @abstractmethod
    def min(self) -> int:
        """return min tilt position"""

    @property
    @abstractmethod
    def position(self) -> int:
        """get current position of the axis"""

    @position.setter
    @abstractmethod
    def position(self, position_ustep: int):
        """set current position of the axis"""

    @property
    @abstractmethod
    def targetPosition(self) -> int:
        """return last target position which has to be set before every move"""

    @property
    @abstractmethod
    def onTargetPosition(self) -> bool:
        """return if axis has completed the movement and is on expected position"""

    @property
    @abstractmethod
    def moving(self) -> bool:
        """determine if tilt is moving at the moment"""

    @abstractmethod
    def moveAbsolute(self, position) -> bool:
        """initiate movement of the axis"""

    @abstractmethod
    def sensitivity(self, sensitivity: int):
        """tune axis profiles to given sensitivity"""

    @abstractmethod
    def move(self, speed: int, set_profiles: bool = True, fullstep=False) -> bool:
        """high level movement of the axis with predefined properties"""

    @abstractmethod
    def stop(self):
        """stop movement of the axis (do not release)"""

########## homing ##########

    @property
    @abstractmethod
    def synced(self) -> bool:
        """basic check if axis is synchronized (homing has succesfully finished)"""

    @property
    @abstractmethod
    def homingStatus(self) -> int:
        """get actual state of axis homing"""

    @abstractmethod
    def sync(self) -> bool:
        """start tilt homing"""

    @abstractmethod
    def syncWait(self, retries: int) -> bool:
        """blocking method for tilt homing. retries = number of additional tries when homing fails"""

########## profiles ##########

    @property
    @abstractmethod
    def profileNames(self) -> List[str]:
        """list of all profile names of given axis"""

    @property
    @abstractmethod
    def profileId(self) -> AxisProfile:
        """return selected profile"""

    @profileId.setter
    @abstractmethod
    def profileId(self, profileId: AxisProfile):
        """select profile"""

    @property
    @abstractmethod
    def profile(self) -> List[int]:
        """get values of currently selected profile in MC"""

    @profile.setter
    @abstractmethod
    def profile(self, profile: List[int]):
        """update values of currently selected profile in MC"""

    @property
    @abstractmethod
    def profiles(self) -> List[List[int]]:
        """get all profiles from MC"""

    @profiles.setter
    @abstractmethod
    def profiles(self, profiles: List[List[int]]):
        """save all profiles to MC"""
