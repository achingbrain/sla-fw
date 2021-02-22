# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from abc import ABC
from threading import Event
from time import time
from typing import Optional, Dict, Any

from sl1fw import defines
from sl1fw.errors.errors import (
    TiltHomeCheckFailed,
    TiltEndstopNotReached,
    TiltAxisCheckFailed,
    InvalidTiltAlignPosition,
)
from sl1fw.functions.checks import tilt_calib_start
from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw import test_runtime
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker, PushState
from sl1fw.wizard.checks.base import WizardCheckType, SyncDangerousCheck, SyncCheck, DangerousCheck
from sl1fw.wizard.setup import Configuration, Resource, TankSetup


class TiltHomeTest(SyncDangerousCheck, ABC):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_HOME, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )
        self.hw = hw

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            home_status = self.hw.tiltHomingStatus
            for _ in range(3):
                self.hw.tiltSyncWait()
                home_status = self.hw.tiltHomingStatus
                if home_status == -2:
                    raise TiltEndstopNotReached()

                if home_status == 0:
                    self.hw.tiltHomeCalibrateWait()
                    self.hw.setTiltPosition(0)
                    break

            if home_status == -3:
                raise TiltHomeCheckFailed()


class TiltLevelTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_LEVEL, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN]
        )
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.setTiltProfile("homingFast")
        self._hw.tiltUp()
        while self._hw.isTiltMoving():
            await asyncio.sleep(0.25)


class TiltRangeTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_RANGE, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )
        self.hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.hw.setTiltProfile("homingFast")
            self.hw.tiltMoveAbsolute(self.hw.tilt_end)
            while self.hw.isTiltMoving():
                await asyncio.sleep(0.25)
            self.progress = 0.25

            self.hw.tiltMoveAbsolute(512)  # go down fast before endstop
            while self.hw.isTiltMoving():
                await asyncio.sleep(0.25)
            self.progress = 0.5

            self.hw.setTiltProfile("homingSlow")  # finish measurement with slow profile (more accurate)
            self.hw.tiltMoveAbsolute(self.hw.tilt_min)
            while self.hw.isTiltMoving():
                await asyncio.sleep(0.25)
            self.progress = 0.75

            # TODO make MC homing more accurate
            if (
                self.hw.getTiltPosition() < -defines.tiltHomingTolerance
                or self.hw.getTiltPosition() > defines.tiltHomingTolerance
            ) and not test_runtime.testing:
                raise TiltAxisCheckFailed(self.hw.tilt_position)
            self.hw.setTiltProfile("homingFast")
            self.hw.tiltMoveAbsolute(defines.defaultTiltHeight)
            while self.hw.isTiltMoving():
                await asyncio.sleep(0.25)


class TiltTimingTest(DangerousCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            hw, WizardCheckType.TILT_TIMING, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )
        self._hw = hw
        self._hw_config = hw_config

        self.tilt_slow_time_ms = Optional[int]
        self.tilt_fast_time_ms = Optional[int]

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self._hw.towerSync()
            while not self._hw.isTowerSynced():
                await asyncio.sleep(0.25)

            self._hw.tiltSyncWait(2)  # FIXME MC cant properly home tilt while tower is moving
            self.tilt_slow_time_ms = await self._get_tilt_time(slowMove=True)
            self.tilt_fast_time_ms = await self._get_tilt_time(slowMove=False)
            self._hw.setTowerProfile("homingFast")
            self._hw.setTiltProfile("homingFast")
            self._hw.tiltUp()
            while self._hw.isTiltMoving():
                await asyncio.sleep(0.25)

    async def _get_tilt_time(self, slowMove):
        tilt_time = 0
        total = self._hw_config.measuringMoves
        for i in range(total):
            if slowMove:
                self.progress = i / total / 2
            else:
                self.progress = 0.5 + i / total
            self._logger.info(
                "Slow move %(count)d/%(total)d" % {"count": i + 1, "total": total}
                if slowMove
                else "Fast move %(count)d/%(total)d" % {"count": i + 1, "total": total}
            )
            await asyncio.sleep(0)
            tilt_start_time = time()
            self._hw.tiltLayerUpWait()
            await asyncio.sleep(0)
            self._hw.tiltLayerDownWait(slowMove)
            tilt_time += time() - tilt_start_time

        return round(1000 * tilt_time / total)


class TiltCalibrationStartTest(SyncDangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.TILT_CALIBRATION_START, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )
        self.hw = hw

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            tilt_calib_start(self.hw)


class TiltAlignTest(SyncCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.TILT_CALIBRATION,
            Configuration(TankSetup.REMOVED, None),
            [Resource.TILT, Resource.TOWER_DOWN],
        )
        self._hw = hw
        self.hw_config = hw_config
        self._tilt_height = None
        self.tilt_aligned_event = Event()

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            actions.tilt_aligned.register_callback(self.tilt_aligned)
            actions.tilt_move.register_callback(self.tilt_move)

            level_tilt_state = PushState(WizardState.LEVEL_TILT)
            actions.push_state(level_tilt_state)
            self.tilt_aligned_event.wait()
            actions.drop_state(level_tilt_state)

    def tilt_aligned(self):
        position = self._hw.tilt_position
        if position is None:
            self._hw.beepAlarm(3)
            raise InvalidTiltAlignPosition(position)
        self._tilt_height = position
        self.hw_config.tiltHeight = self._tilt_height
        self.tilt_aligned_event.set()

    def tilt_move(self, direction: int):
        self._logger.debug("Tilt move direction: %s", direction)
        self._hw.tilt_move(direction, fullstep=True)

    def get_result_data(self) -> Dict[str, Any]:
        return {"tiltHeight": self._tilt_height}
