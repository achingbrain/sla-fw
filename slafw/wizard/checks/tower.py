# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep, gather
from typing import Dict, Any

from slafw.errors.errors import TowerBelowSurface, TowerAxisCheckFailed, TowerHomeFailed, TowerEndstopNotReached
from slafw.libHardware import Hardware
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import WizardCheckType, DangerousCheck
from slafw.wizard.setup import Configuration, Resource, TankSetup, PlatformSetup
from slafw.hardware.tilt import TiltProfile
from slafw.configs.writer import ConfigWriter


class TowerHomeTest(DangerousCheck):
    def __init__(self, hw: Hardware, config_writer: ConfigWriter):
        super().__init__(
            hw, WizardCheckType.TOWER_HOME, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.config_writer = config_writer

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            for _ in range(3):
                await sleep(0.1)
                try:
                    await self._hw.towerSyncWaitAsync(retries=0)
                except (TowerHomeFailed, TowerEndstopNotReached) as e:
                    self._logger.exception(e)
                    await sleep(0.1)
                    self.config_writer.towerSensitivity = await self._hw.get_tower_sensitivity_async()

    def get_result_data(self) -> Dict[str, Any]:
        return {
            # measured fake resin volume in wizard (without resin with rotated platform)
            "towerSensitivity": self.config_writer.towerSensitivity
        }


class TowerRangeTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TOWER_RANGE, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        with actions.led_warn:
            await gather(self._hw.verify_tower(), self._hw.verify_tilt())
            self._hw.setTowerPosition(self._hw.tower_end)
            self._hw.setTowerProfile("homingFast")
            self._hw.towerMoveAbsolute(0)
            while self._hw.isTowerMoving():
                await sleep(0.25)

            if self._hw.getTowerPositionMicroSteps() == 0:
                # stop 10 mm before end-stop to change sensitive profile
                self._hw.towerMoveAbsolute(self._hw.tower_end - self._hw.config.calcMicroSteps(10))
                while self._hw.isTowerMoving():
                    await sleep(0.25)

                self._hw.setTowerProfile("homingSlow")
                self._hw.towerMoveAbsolute(self._hw.tower_max)
                while self._hw.isTowerMoving():
                    await sleep(0.25)

            position_microsteps = self._hw.getTowerPositionMicroSteps()
            # MC moves tower by 1024 steps forward in last step of !twho
            if (
                position_microsteps < self._hw.tower_end or position_microsteps > self._hw.tower_end + 1024 + 127
            ):  # add tolerance half full-step
                raise TowerAxisCheckFailed(self._hw.config.tower_microsteps_to_nm(position_microsteps))


class TowerAlignTest(DangerousCheck):
    def __init__(self, hw: Hardware, config_writer: ConfigWriter):
        super().__init__(
            hw,
            WizardCheckType.TOWER_CALIBRATION,
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self._config_writer = config_writer

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        with actions.led_warn:
            self._logger.info("Starting platform calibration")
            self._hw.tilt.profile_id = TiltProfile.layerMoveSlow # set higher current
            self._hw.setTowerPosition(0)
            self._hw.setTowerProfile("homingFast")

            self._logger.info("Moving platform to above position")
            self._hw.towerMoveAbsolute(self._hw.tower_above_surface)
            while self._hw.isTowerMoving():
                await sleep(0.25)

            self._logger.info("tower position above: %d", self._hw.getTowerPositionMicroSteps())
            if self._hw.getTowerPositionMicroSteps() != self._hw.tower_above_surface:
                self._logger.error(
                    "Platform calibration [above] failed %s != %s",
                    self._hw.getTowerPositionMicroSteps(),
                    self._hw.tower_above_surface,
                )
                self._hw.beepAlarm(3)
                await self._hw.towerSyncWaitAsync()
                raise TowerBelowSurface(self._hw.tower_position_nm)

            self._logger.info("Moving platform to min position")
            self._hw.setTowerProfile("homingSlow")
            self._hw.towerToMin()
            while self._hw.isTowerMoving():
                await sleep(0.25)
            self._logger.info("tower position min: %d", self._hw.getTowerPositionMicroSteps())
            if self._hw.getTowerPositionMicroSteps() <= self._hw.tower_min:
                self._logger.error(
                    "Platform calibration [min] failed %s != %s",
                    self._hw.getTowerPositionMicroSteps(),
                    self._hw.tower_above_surface,
                )
                self._hw.beepAlarm(3)
                await self._hw.towerSyncWaitAsync()
                raise TowerBelowSurface(self._hw.tower_position_nm)

            self._logger.debug("Moving tower to calib position x3")
            self._hw.towerMoveAbsolute(self._hw.getTowerPositionMicroSteps() + self._hw.tower_calib_pos * 3)
            while self._hw.isTowerMoving():
                await sleep(0.25)

            self._logger.debug("Moving tower to min")
            self._hw.towerToMin()
            while self._hw.isTowerMoving():
                await sleep(0.25)

            self._logger.debug("Moving tower to calib position")
            self._hw.towerMoveAbsolute(self._hw.getTowerPositionMicroSteps() + self._hw.tower_calib_pos)
            while self._hw.isTowerMoving():
                await sleep(0.25)
            self._logger.info("tower position: %d", self._hw.getTowerPositionMicroSteps())
            self._config_writer.towerHeight = -self._hw.getTowerPositionMicroSteps()

            self._hw.setTowerProfile("homingFast")
            # TODO: Allow to repeat align step on exception

    def get_result_data(self) -> Dict[str, Any]:
        return {"towerHeight": self._config_writer.towerHeight}
