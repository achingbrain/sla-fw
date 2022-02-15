# This file is part of the SLA firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep
from time import time

from slafw.libHardware import Hardware
from slafw.image.exposure_image import ExposureImage
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import WizardCheckType, DangerousCheck, Check
from slafw.wizard.setup import Configuration, Resource
from slafw.errors.errors import CleaningAdaptorMissing


class HomeTower(DangerousCheck):
    """ Home tower and request the user to attach the cleaning adaptor to the platform """

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
        await self._hw.tower_move_absolute_nm_wait_async(36_000_000)
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
        target_position_nm = 1_800_000
        self._hw.tower_position_nm = target_position_nm
        while self._hw.isTowerMoving():
            await sleep(0.25)
        if target_position_nm == self._hw.tower_position_nm:
            # Did you forget to put a cleaning adapter pin on corner of the platform?
            self._hw.setTowerProfile("homingFast")
            await self._hw.tower_move_absolute_nm_wait_async(self._hw.config.tower_height_nm)
            self._hw.motorsRelease()
            # Error: The cleaning adaptor is not present, the platform moved to the exposure display without hitting it.
            raise CleaningAdaptorMissing()
        self._logger.info("TouchDown did detect an obstacle - cleaningAdaptor.?")


class ExposeDebris(DangerousCheck):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage):
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
        self._hw.setTowerProfile("homingSlow")
        await self._hw.tilt.sync_wait_async(retries=2)
        await self._hw.tower_move_absolute_nm_wait_async(50_000_000)
        while self._hw.isTowerMoving():
            await sleep(0.25)
