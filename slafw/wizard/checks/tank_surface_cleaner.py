# This file is part of the SLA firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep
from time import time
from enum import Enum, unique

from slafw.libHardware import Hardware
from slafw.image.exposure_image import ExposureImage
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import WizardCheckType, DangerousCheck, Check
from slafw.wizard.setup import Configuration, Resource
from slafw.errors.errors import GarbageCollectorMissing

@unique
class GentlyUpProfile(Enum):
    """Gives meaning to the value config.tankCleaningGentlyUpProfile,
    which should be restricted to the prepared(here) selection of
    available profiles for "GentlyUp" operation.
    """

    SPEED0 = 0
    SPEED1 = 1
    SPEED2 = 2
    SPEED3 = 3

    def map_to_tower_profile_name(self) -> str:
        """Transform the value passed from the frontend via configuration into a name of an actual tower profile"""
        if self == GentlyUpProfile.SPEED0:
            return "moveSlow"
        elif self == GentlyUpProfile.SPEED1:
            return "superSlow"
        elif self == GentlyUpProfile.SPEED2:
            return "homingSlow"
        elif self == GentlyUpProfile.SPEED3:
            return "resinSensor"
        else:
            return "moveSlow"


class HomeTower(DangerousCheck):
    """ Home tower and request the user to attach the garbage collector to the platform """

    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TOWER_HOME, Configuration(None, None), [Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        await self._hw.towerSyncWaitAsync(retries=2)


class TiltHome(DangerousCheck):
    """ Home the platform (to the top) """

    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_HOME, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN]
        )

    async def async_task_run(self, actions: UserActionBroker):
        await self._hw.tilt.sync_wait_async(retries=2)


class TiltUp(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_LEVEL, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN]
        )

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.tilt.layer_up_wait()


class TowerSafeDistance(DangerousCheck):
    """ Move the platform to save distance from the tank """

    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TOWER_SAFE_DISTANCE, Configuration(None, None), [Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.setTowerProfile("homingFast")
        await self._hw.towerMoveAbsoluteWaitAsync(self._hw.config.calcMicroSteps(56))
        while self._hw.isTowerMoving():
            await sleep(0.25)


class TouchDown(DangerousCheck):
    """ Move slowly down until you hit something """

    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TOWER_TOUCHDOWN, Configuration(None, None), [Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.setTowerProfile("homingSlow")
        # Note: Do not use towerMoveAbsoluteWaitAsync here. It's periodically calling isTowerOnPosition which
        # is causing the printer to try to fix the tower position
        target_microsteps = self._hw.config.calcMicroSteps(1.8)
        self._hw.towerMoveAbsolute(target_microsteps)
        while self._hw.isTowerMoving():
            await sleep(0.25)
        if target_microsteps == self._hw.getTowerPositionMicroSteps():
            # Did you forget to put a garbage collector pin on corner of the platform?
            self._hw.setTowerProfile("homingFast")
            await self._hw.towerMoveAbsoluteWaitAsync(self._hw.config.towerHeight)
            self._hw.motorsRelease()
            # Error: The garbage collector is not present, the platform moved to the exposure display without hitting it.
            raise GarbageCollectorMissing()
        self._logger.info("TouchDown did detect an obstacle - garbageCollector.?")


class ExposeGarbage(DangerousCheck):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage):
        super().__init__(
            hw, WizardCheckType.EXPOSING_GARBAGE, Configuration(None, None),
            [Resource.UV, Resource.FANS, Resource.TOWER_DOWN, Resource.TILT]
        )
        self._exposure_image = exposure_image
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        try:  # Handle the possible interruption
            # Exposure display turn "white"
            self._exposure_image.open_screen()
            self._hw.startFans()
            self._hw.uvLed(True)
            finish_time = time() + self._hw.config.tankCleaningExposureTime
            while time() < finish_time:
                await sleep(0.25)
        finally:
            # Return the display to black
            self._exposure_image.blank_screen()
            self._hw.uvLed(False)
            self._hw.stopFans()


class GentlyUp(Check):
    """ Move slowly up until you hit something """

    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.TOWER_GENTLY_UP, Configuration(None, None), [Resource.TILT, Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        up_profile = GentlyUpProfile(self._hw.config.tankCleaningGentlyUpProfile)
        self._logger.info("GentlyUp with %s -> %s", up_profile.name, up_profile.map_to_tower_profile_name())
        self._hw.setTowerProfile(up_profile.map_to_tower_profile_name())
        await self._hw.tilt.sync_wait_async(retries=2)
        await self._hw.towerMoveAbsoluteWaitAsync(self._hw.config.calcMicroSteps(50))
        while self._hw.isTowerMoving():
            await sleep(0.25)
