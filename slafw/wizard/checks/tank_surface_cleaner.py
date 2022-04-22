# This file is part of the SLA firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from asyncio import sleep
from time import time
from enum import Enum, unique

from slafw.configs.unit import Nm
from slafw.hardware.base.hardware import BaseHardware
from slafw.hardware.sl1.tower import TowerProfile
from slafw.image.exposure_image import ExposureImage
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import WizardCheckType, DangerousCheck, Check
from slafw.wizard.setup import Configuration, Resource
from slafw.errors.errors import CleaningAdaptorMissing

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

    def map_to_tower_profile_name(self) -> TowerProfile:
        """Transform the value passed from the frontend via configuration into a name of an actual tower profile"""
        if self == GentlyUpProfile.SPEED0:  # pylint: disable=no-else-return
            return TowerProfile.moveSlow
        elif self == GentlyUpProfile.SPEED1:
            return TowerProfile.superSlow
        elif self == GentlyUpProfile.SPEED2:
            return TowerProfile.homingSlow
        elif self == GentlyUpProfile.SPEED3:
            return TowerProfile.resinSensor
        return TowerProfile.moveSlow


class HomeTower(DangerousCheck):
    """ Home tower and request the user to attach the cleaning adaptor to the platform """

    def __init__(self, hw: BaseHardware):
        super().__init__(
            hw, WizardCheckType.TOWER_HOME, Configuration(None, None), [Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        await self._hw.tower.sync_ensure_async()


class HomeTowerFinish(DangerousCheck):
    """ Home tower at the end of wizard """

    def __init__(self, hw: BaseHardware):
        super().__init__(
            hw, WizardCheckType.TOWER_HOME_FINISH, Configuration(None, None), [Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        await self._hw.tower.sync_ensure_async()

class TiltHome(DangerousCheck):
    """ Home the platform (to the top) """

    def __init__(self, hw: BaseHardware):
        super().__init__(
            hw, WizardCheckType.TILT_HOME, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN]
        )

    async def async_task_run(self, actions: UserActionBroker):
        await self._hw.tilt.sync_ensure_async()


class TiltUp(DangerousCheck):
    def __init__(self, hw: BaseHardware):
        super().__init__(
            hw, WizardCheckType.TILT_LEVEL, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN]
        )

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.tilt.layer_up_wait()


class TowerSafeDistance(DangerousCheck):
    """ Move the platform to save distance from the tank """

    def __init__(self, hw: BaseHardware):
        super().__init__(
            hw, WizardCheckType.TOWER_SAFE_DISTANCE, Configuration(None, None), [Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.tower.profile_id = TowerProfile.homingFast
        await self._hw.tower.move_ensure_async(self._hw.tower.resin_start_pos_nm)


class TouchDown(DangerousCheck):
    """ Move slowly down until you hit something """

    def __init__(self, hw: BaseHardware):
        super().__init__(
            hw, WizardCheckType.TOWER_TOUCHDOWN, Configuration(None, None), [Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.tower.profile_id = TowerProfile.resinSensor
        # Note: Do not use towerMoveAbsoluteWaitAsync here. It's periodically calling isTowerOnPosition which
        # is causing the printer to try to fix the tower position

        target_position_nm = self._hw.config.tankCleaningAdaptorHeight_nm - Nm(3_000_000)
        self._hw.tower.move(target_position_nm)
        while self._hw.tower.moving:
            await sleep(0.25)
        if target_position_nm == self._hw.tower.position:
            # Did you forget to put a cleaning adapter pin on corner of the platform?
            self._hw.tower.profile_id = TowerProfile.homingFast
            await self._hw.tower.move_ensure_async(self._hw.config.tower_height_nm)
            self._hw.motors_release()
            # Error: The cleaning adaptor is not present, the platform moved to the exposure display without hitting it.
            raise CleaningAdaptorMissing()
        self._logger.info("TouchDown did detect an obstacle - cleaningAdaptor.?")

        self._logger.info("Moving up to the configured height(%d nm)...", self._hw.config.tankCleaningMinDistance_nm)
        lifted_position = self._hw.tower.position + self._hw.config.tankCleaningMinDistance_nm
        self._hw.tower.move(lifted_position)
        while self._hw.tower.moving:
            await sleep(0.25)
        if lifted_position == self._hw.tower.position:
            self._logger.info("Garbage collector successfully lifted to the initial position.")
        else:
            self._logger.warning("Garbage collector failed to be lifted to the initial position(should be %d, is %d). Continuing anyway.", lifted_position, self._hw.tower.position)


class ExposeDebris(DangerousCheck):
    def __init__(self, hw: BaseHardware, exposure_image: ExposureImage):
        super().__init__(
            hw, WizardCheckType.EXPOSING_DEBRIS, Configuration(None, None),
            [Resource.UV, Resource.FANS, Resource.TOWER_DOWN, Resource.TILT]
        )
        self._exposure_image = exposure_image
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        try:  # Handle the possible interruption
            # Exposure display turn "white"
            self._exposure_image.open_screen()
            self._hw.start_fans()
            self._hw.uv_led.on()
            start_time = time()
            finish_time = time() + self._hw.config.tankCleaningExposureTime
            while time() < finish_time:
                self.progress = 1 - (finish_time - time()) / (finish_time - start_time)
                await sleep(0.25)
        finally:
            # Return the display to black
            self._exposure_image.blank_screen()
            self._hw.uv_led.off()
            self._hw.stop_fans()


class GentlyUp(Check):
    """ Move slowly up until you hit something """

    def __init__(self, hw: BaseHardware):
        super().__init__(
            WizardCheckType.TOWER_GENTLY_UP, Configuration(None, None), [Resource.TILT, Resource.TOWER],
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        up_profile = GentlyUpProfile(self._hw.config.tankCleaningGentlyUpProfile)
        self._logger.info("GentlyUp with %s -> %s", up_profile.name, up_profile.map_to_tower_profile_name())
        self._hw.tower.profile_id = up_profile.map_to_tower_profile_name()

        await self._hw.tilt.layer_down_wait_async(slowMove=True)
        # TODO: constant in code !!!
        target_position = Nm(50_000_000)
        for _ in range(3):
            self._hw.tower.move(target_position)
            while self._hw.tower.moving:
                await asyncio.sleep(0.25)
            if abs(target_position - self._hw.tower.position) < Nm(10):
                break
