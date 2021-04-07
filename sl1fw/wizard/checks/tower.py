# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep
from typing import Optional, Dict, Any

from sl1fw import defines
from sl1fw.errors.errors import TowerBelowSurface, TowerAxisCheckFailed
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, DangerousCheck
from sl1fw.wizard.setup import Configuration, Resource, TankSetup, PlatformSetup


class TowerHomeTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TOWER_HOME, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self.wizard_tower_sensitivity = Optional[int]

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.wizard_tower_sensitivity = self.hw.config.towerSensitivity
            for _ in range(3):
                await sleep(0.1)
                if not await self.hw.towerSyncWaitAsync():
                    await sleep(0.1)
                    self.wizard_tower_sensitivity = self.hw.get_tower_sensitivity()

    def get_result_data(self) -> Dict[str, Any]:
        return {
            # measured fake resin volume in wizard (without resin with rotated platform)
            "towerSensitivity": self.wizard_tower_sensitivity
        }


class TowerRangeTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TOWER_RANGE, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        with actions.led_warn:
            await self.hw.towerSyncWaitAsync()
            self.hw.setTowerPosition(self.hw.tower_end)
            self.hw.setTowerProfile("homingFast")
            self.hw.towerMoveAbsolute(0)
            while self.hw.isTowerMoving():
                await sleep(0.25)

            if self.hw.getTowerPositionMicroSteps() == 0:
                # stop 10 mm before end-stop to change sensitive profile
                self.hw.towerMoveAbsolute(self.hw.tower_end - 8000)
                while self.hw.isTowerMoving():
                    await sleep(0.25)

                self.hw.setTowerProfile("homingSlow")
                self.hw.towerMoveAbsolute(self.hw.tower_max)
                while self.hw.isTowerMoving():
                    await sleep(0.25)

            position_microsteps = self.hw.getTowerPositionMicroSteps()
            # MC moves tower by 1024 steps forward in last step of !twho
            if (
                position_microsteps < self.hw.tower_end or position_microsteps > self.hw.tower_end + 1024 + 127
            ):  # add tolerance half full-step
                raise TowerAxisCheckFailed(self.hw.config.tower_microsteps_to_nm(position_microsteps))


class TowerAlignTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw,
            WizardCheckType.TOWER_CALIBRATION,
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self._tower_height = None

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        with actions.led_warn:
            self._logger.info("Starting platform calibration")
            self.hw.setTiltProfile("homingFast")
            self.hw.setTiltCurrent(defines.tiltCalibCurrent)
            self.hw.setTowerPosition(0)
            self.hw.setTowerProfile("homingFast")

            self._logger.info("Moving platform to above position")
            self.hw.towerMoveAbsolute(self.hw.tower_above_surface)
            while self.hw.isTowerMoving():
                await sleep(0.25)

            self._logger.info("tower position above: %d", self.hw.getTowerPositionMicroSteps())
            if self.hw.getTowerPositionMicroSteps() != self.hw.tower_above_surface:
                self._logger.error(
                    "Platform calibration [above] failed %s != %s",
                    self.hw.getTowerPositionMicroSteps(),
                    self.hw.tower_above_surface,
                )
                self.hw.beepAlarm(3)
                await self.hw.towerSyncWaitAsync()
                raise TowerBelowSurface(self.hw.tower_position_nm)

            self._logger.info("Moving platform to min position")
            self.hw.setTowerProfile("homingSlow")
            self.hw.towerToMin()
            while self.hw.isTowerMoving():
                await sleep(0.25)
            self._logger.info("tower position min: %d", self.hw.getTowerPositionMicroSteps())
            if self.hw.getTowerPositionMicroSteps() <= self.hw.tower_min:
                self._logger.error(
                    "Platform calibration [min] failed %s != %s",
                    self.hw.getTowerPositionMicroSteps(),
                    self.hw.tower_above_surface,
                )
                self.hw.beepAlarm(3)
                await self.hw.towerSyncWaitAsync()
                raise TowerBelowSurface(self.hw.tower_position_nm)

            self._logger.debug("Moving tower to calib position x3")
            self.hw.towerMoveAbsolute(self.hw.getTowerPositionMicroSteps() + self.hw.tower_calib_pos * 3)
            while self.hw.isTowerMoving():
                await sleep(0.25)

            self._logger.debug("Moving tower to min")
            self.hw.towerToMin()
            while self.hw.isTowerMoving():
                await sleep(0.25)

            self._logger.debug("Moving tower to calib position")
            self.hw.towerMoveAbsolute(self.hw.getTowerPositionMicroSteps() + self.hw.tower_calib_pos)
            while self.hw.isTowerMoving():
                await sleep(0.25)
            self._logger.info("tower position: %d", self.hw.getTowerPositionMicroSteps())
            self._tower_height = -self.hw.getTowerPositionMicroSteps()

            # TODO remove this once output value setting in implemented on wizard finish
            self.hw.config.towerHeight = self._tower_height

            self.hw.setTowerProfile("homingFast")
            # TODO: Allow to repeat align step on exception

    def get_result_data(self) -> Dict[str, Any]:
        return {"towerHeight": self._tower_height}

    def wizard_finished(self):
        writer = self._hw.config.get_writer()
        writer.towerHeight = self._tower_height
        writer.commit()
