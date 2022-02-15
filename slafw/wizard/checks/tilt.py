# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from abc import ABC
from time import time
from typing import Optional, Dict, Any

from slafw import defines
from slafw.errors.errors import (
    TiltHomeCheckFailed,
    TiltEndstopNotReached,
    TiltAxisCheckFailed,
    InvalidTiltAlignPosition,
    PrinterException,
)
from slafw.libHardware import Hardware
from slafw import test_runtime
from slafw.states.wizard import WizardState
from slafw.wizard.actions import UserActionBroker, PushState
from slafw.wizard.checks.base import WizardCheckType, DangerousCheck, Check
from slafw.wizard.setup import Configuration, Resource, TankSetup
from slafw.hardware.tilt import TiltProfile, TiltSpeed
from slafw.configs.writer import ConfigWriter


class TiltHomeTest(DangerousCheck, ABC):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_HOME, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            home_status = self._hw.tilt.homing_status
            for _ in range(3):
                await self._hw.tilt.sync_wait_async()
                home_status = self._hw.tilt.homing_status
                if home_status == -2:
                    raise TiltEndstopNotReached()

                if home_status == 0:
                    await self._hw.tilt.home_calibrate_wait_async()
                    break

            if home_status == -3:
                raise TiltHomeCheckFailed()


class TiltLevelTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_LEVEL, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN]
        )

    async def async_task_run(self, actions: UserActionBroker):
        # This just homes tilt
        # TODO: We should have such a method in Hardware
        self._hw.tilt.profile_id = TiltProfile.homingFast
        self._hw.tilt.sync()
        home_status = self._hw.tilt.homing_status
        while home_status != 0:
            if home_status == -2:
                raise TiltEndstopNotReached()
            if home_status == -3:
                raise TiltHomeCheckFailed()
            if home_status < 0:
                raise PrinterException("Unknown printer home error")
            await asyncio.sleep(0.25)
            home_status = self._hw.tilt.homing_status
        self._hw.tilt.position = 0

        # Set tilt to leveled position
        self._hw.tilt.profile_id = TiltProfile.moveFast
        self._hw.tilt.move_up()
        while self._hw.tilt.moving:
            await asyncio.sleep(0.25)


class TiltRangeTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_RANGE, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self._hw.tilt.profile_id = TiltProfile.moveFast
            self._hw.tilt.move_absolute(self._hw.tilt.max)
            while self._hw.tilt.moving:
                await asyncio.sleep(0.25)
            self.progress = 0.25

            self._hw.tilt.move_absolute(512)  # go down fast before endstop
            while self._hw.tilt.moving:
                await asyncio.sleep(0.25)
            self.progress = 0.5

            self._hw.tilt.profile_id = TiltProfile.homingSlow  # finish measurement with slow profile (more accurate)
            self._hw.tilt.move_absolute(self._hw.tilt.min)
            while self._hw.tilt.moving:
                await asyncio.sleep(0.25)
            self.progress = 0.75

            # TODO make MC homing more accurate
            if (
                self._hw.tilt.position < -defines.tiltHomingTolerance
                or self._hw.tilt.position > defines.tiltHomingTolerance
            ) and not test_runtime.testing:
                raise TiltAxisCheckFailed(self._hw.tilt.position)
            self._hw.tilt.profile_id = TiltProfile.moveFast
            self._hw.tilt.move_absolute(defines.defaultTiltHeight)
            while self._hw.tilt.moving:
                await asyncio.sleep(0.25)


class TiltTimingTest(DangerousCheck):
    def __init__(self, hw: Hardware, config_writer: ConfigWriter):
        super().__init__(
            hw, WizardCheckType.TILT_TIMING, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )
        self._config_writer = config_writer

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self._hw.towerSync()
            while not self._hw.isTowerSynced():
                await asyncio.sleep(0.25)

            await self._hw.tilt.sync_wait_async()  # FIXME MC cant properly home tilt while tower is moving
            self._config_writer.tiltFastTime = await self._get_tilt_time_sec(TiltSpeed.DEFAULT, 1/3)
            self._config_writer.tiltSlowTime = await self._get_tilt_time_sec(TiltSpeed.SLOW, 1 / 3)
            self._config_writer.tiltSuperSlowTime = await self._get_tilt_time_sec(TiltSpeed.SUPERSLOW, 1/3)
            self._hw.setTowerProfile("homingFast")
            self._hw.tilt.profile_id = TiltProfile.moveFast
            self.progress = 1
            self._hw.tilt.move_up()
            while self._hw.tilt.moving:
                await asyncio.sleep(0.25)

    async def _get_tilt_time_sec(self, tilt_speed: TiltSpeed, progress_multiplier: float = 1.0) -> float:
        """
        Get tilt time in seconds
        :param tilt_speed: How slow tilts
        :param progress_multiplier: How big part of the total amount of work does this function
                call consist of?
        :return: Tilt time in seconds
        """
        tilt_time: float = 0
        total = self._hw.config.measuringMoves
        for i in range(total):
            await asyncio.sleep(0)
            tilt_start_time = time()
            self._hw.tilt.layer_up_wait(tilt_speed=tilt_speed, tiltHeight=self._config_writer.tiltHeight)
            await asyncio.sleep(0)
            await self._hw.tilt.layer_down_wait_async(tilt_speed)
            tilt_time += time() - tilt_start_time
            self.progress += progress_multiplier * (i / total)
            self._logger.info(
                "%(what)s move %(count)d/%(total)d" % {"what": tilt_speed.name, "count": i + 1, "total": total}
            )

        return tilt_time / total

    def get_result_data(self) -> Dict[str, Any]:
        return {
            "tilt_slow_time_ms": int(self._config_writer.tiltSlowTime * 1000),
            "tilt_fast_time_ms": int(self._config_writer.tiltFastTime * 1000),
            "tilt_superslow_time_ms": int(self._config_writer.tiltSuperSlowTime * 1000),
        }


class TiltCalibrationStartTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_CALIBRATION_START, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self._hw.tilt.profile_id = TiltProfile.homingFast
            self._hw.tilt.move_absolute(defines.tiltCalibrationStart)
            while self._hw.tilt.moving:
                await asyncio.sleep(0.25)


class TiltAlignTest(Check):
    def __init__(self, hw: Hardware, config_writer: ConfigWriter):
        super().__init__(
            WizardCheckType.TILT_CALIBRATION,
            Configuration(TankSetup.REMOVED, None),
            [Resource.TILT, Resource.TOWER_DOWN],
        )
        self._hw = hw
        self._config_writer = config_writer
        self.tilt_aligned_event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def async_task_run(self, actions: UserActionBroker):
        self.tilt_aligned_event = asyncio.Event()
        self._loop = asyncio.get_running_loop()
        with actions.led_warn:
            actions.tilt_aligned.register_callback(self.tilt_aligned)
            actions.tilt_move.register_callback(self.tilt_move)

            level_tilt_state = PushState(WizardState.LEVEL_TILT)
            actions.push_state(level_tilt_state)
            await self.tilt_aligned_event.wait()
            actions.drop_state(level_tilt_state)

    def tilt_aligned(self):
        position = self._hw.tilt.position
        if position is None:
            self._hw.beepAlarm(3)
            raise InvalidTiltAlignPosition(position)
        self._config_writer.tiltHeight = position
        self._loop.call_soon_threadsafe(self.tilt_aligned_event.set)

    def tilt_move(self, direction: int):
        self._logger.debug("Tilt move direction: %s", direction)
        self._hw.tilt.move(direction, fullstep=True)

    def get_result_data(self) -> Dict[str, Any]:
        return {"tiltHeight": self._config_writer.tiltHeight}
