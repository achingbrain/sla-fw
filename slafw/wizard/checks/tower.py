# This file is part of the SLA firmware
# Copyright (C) 2020-2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
from asyncio import sleep, gather
from typing import Dict, Any

from slafw.configs.unit import Nm
from slafw.errors.errors import TowerBelowSurface, TowerAxisCheckFailed, TowerHomeFailed, TowerEndstopNotReached
from slafw.hardware.base.hardware import BaseHardware
from slafw.hardware.sl1.tower import TowerProfile
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import WizardCheckType, DangerousCheck
from slafw.wizard.setup import Configuration, Resource, TankSetup, PlatformSetup
from slafw.hardware.sl1.tilt import TiltProfile
from slafw.configs.writer import ConfigWriter


class TowerHomeTest(DangerousCheck):
    def __init__(self, hw: BaseHardware, config_writer: ConfigWriter):
        super().__init__(
            hw, WizardCheckType.TOWER_HOME, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.config_writer = config_writer

    async def async_task_run(self, actions: UserActionBroker):
        for sens in range(4):
            sensitivity_failed = False
            for _ in range(3):
                try:
                    await self._hw.tower.sync_ensure_async(retries=0)
                except (TowerHomeFailed, TowerEndstopNotReached) as e:
                    sensitivity_failed = True
                    self._logger.exception(e)
                    if sens == 3:
                        raise e
                    self._hw.set_stepper_sensitivity(self._hw.tower, sens=sens)
                    self.config_writer.towerSensitivity = sens
                    break
            if sensitivity_failed is False:
                break

    def get_result_data(self) -> Dict[str, Any]:
        return {
            # measured fake resin volume in wizard (without resin with rotated platform)
            "towerSensitivity": self.config_writer.towerSensitivity
        }


class TowerRangeTest(DangerousCheck):
    def __init__(self, hw: BaseHardware):
        super().__init__(
            hw, WizardCheckType.TOWER_RANGE, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        await gather(self._hw.tower.verify_async(), self._hw.tilt.verify_async())
        self._hw.tower.position = self._hw.tower.end_nm

        self._hw.tower.profile_id = TowerProfile.homingFast
        await self._hw.tower.move_ensure_async(Nm(0))

        if self._hw.tower.position == Nm(0):
            # stop 10 mm before end-stop to change sensitive profile
            await self._hw.tower.move_ensure_async(self._hw.tower.end_nm - Nm(10_000_000))

            self._hw.tower.profile_id = TowerProfile.homingSlow
            self._hw.tower.move(self._hw.tower.max_nm)
            while self._hw.tower.moving:
                asyncio.sleep(0.25)

        position_nm = self._hw.tower.position
        # MC moves tower by 1024 steps forward in last step of !twho
        maximum_nm = self._hw.tower.end_nm + self._hw.config.tower_microsteps_to_nm(1024 + 127)
        self._logger.info("maximum nm %d", maximum_nm)
        if (
            position_nm < self._hw.tower.end_nm or position_nm > maximum_nm
        ):  # add tolerance half full-step
            raise TowerAxisCheckFailed(position_nm)


class TowerAlignTest(DangerousCheck):
    def __init__(self, hw: BaseHardware, config_writer: ConfigWriter):
        super().__init__(
            hw,
            WizardCheckType.TOWER_CALIBRATION,
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self._config_writer = config_writer

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        self._logger.info("Starting platform calibration")
        self._hw.tilt.profile_id = TiltProfile.layerMoveSlow # set higher current
        self._hw.tower.position = Nm(0)
        self._hw.tower.profile_id = TowerProfile.homingFast

        self._logger.info("Moving platform to above position")
        self._hw.tower.move(self._hw.tower.above_surface_nm)
        while self._hw.tower.moving:
            await sleep(0.25)

        self._logger.info("tower position above: %d nm", self._hw.tower.position)
        if self._hw.tower.position != self._hw.tower.above_surface_nm:
            self._logger.error(
                "Platform calibration [above] failed %s != %s Nm",
                self._hw.tower.position,
                self._hw.tower.above_surface_nm,
            )
            self._hw.beepAlarm(3)
            await self._hw.tower.sync_ensure_async()
            raise TowerBelowSurface(self._hw.tower.position)

        self._logger.info("Moving platform to min position")
        self._hw.tower.profile_id = TowerProfile.homingSlow
        self._hw.tower.move(self._hw.tower.min_nm)
        while self._hw.tower.moving:
            await asyncio.sleep(0.25)
        self._logger.info("tower position min: %d nm", self._hw.tower.position)
        if self._hw.tower.position <= self._hw.tower.min_nm:
            self._logger.error(
                "Platform calibration [min] failed %s != %s",
                self._hw.tower.position,
                self._hw.tower.min_nm,
            )
            self._hw.beepAlarm(3)
            await self._hw.tower.sync_ensure_async()
            raise TowerBelowSurface(self._hw.tower.position)

        self._logger.debug("Moving tower to calib position x3")
        await self._hw.tower.move_ensure_async(
            self._hw.tower.position + self._hw.tower.calib_pos_nm * 3)

        self._logger.debug("Moving tower to min")
        # do not ensure position here. We expect tower to stop on stallguard
        self._hw.tower.move(self._hw.tower.position + self._hw.tower.min_nm)
        while self._hw.tower.moving:
            await asyncio.sleep(0.25)

        self._logger.debug("Moving tower to calib position")
        await self._hw.tower.move_ensure_async(
            self._hw.tower.position + self._hw.tower.calib_pos_nm)

        tower_position_nm = self._hw.tower.position
        self._logger.info("tower position: %d nm", tower_position_nm)
        self._config_writer.tower_height_nm = -tower_position_nm

        self._hw.tower.profile_id = TowerProfile.homingFast
        # TODO: Allow to repeat align step on exception

    def get_result_data(self) -> Dict[str, Any]:
        return {
            "tower_height_nm": int(self._config_writer.tower_height_nm),
        }
