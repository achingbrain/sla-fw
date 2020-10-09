# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Event
from time import sleep, time
from typing import Optional

from sl1fw import defines
from sl1fw.errors.errors import (
    TiltHomeCheckFailed,
    TiltEndstopNotReached,
    TiltAxisCheckFailed,
    InvalidTiltAlignPosition,
)
from sl1fw.functions.checks import tilt_calib_start
from sl1fw.libConfig import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw import test_runtime
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker, PushState
from sl1fw.wizard.checks.base import SyncCheck, WizardCheckType
from sl1fw.wizard.setup import Configuration, Resource, TankSetup


class TiltHomeTest(SyncCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.TILT_HOME, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
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


class TiltRangeTest(SyncCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.TILT_RANGE, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )
        self.hw = hw

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.hw.setTiltProfile("homingFast")
            self.hw.tiltMoveAbsolute(self.hw.tilt_end)
            while self.hw.isTiltMoving():
                sleep(0.25)

            self.hw.tiltMoveAbsolute(512)  # go down fast before endstop
            while self.hw.isTiltMoving():
                sleep(0.25)

            self.hw.setTiltProfile("homingSlow")  # finish measurement with slow profile (more accurate)
            self.hw.tiltMoveAbsolute(self.hw.tilt_min)
            while self.hw.isTiltMoving():
                sleep(0.25)

            # TODO make MC homing more accurate
            if (
                self.hw.getTiltPosition() < -defines.tiltHomingTolerance
                or self.hw.getTiltPosition() > defines.tiltHomingTolerance
            ) and not test_runtime.testing:
                raise TiltAxisCheckFailed(self.hw.tilt_position)
            self.hw.setTiltProfile("homingFast")
            self.hw.tiltMoveAbsolute(defines.defaultTiltHeight)
            while self.hw.isTiltMoving():
                sleep(0.25)


class TiltTimingTest(SyncCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.TILT_TIMING, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self.hw_config = hw_config

        self.tilt_slow_time_ms = Optional[int]
        self.tilt_fast_time_ms = Optional[int]

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.hw.towerSync()
            while not self.hw.isTowerSynced():
                sleep(0.25)

            self.hw.tiltSyncWait(2)  # FIXME MC cant properly home tilt while tower is moving
            self.tilt_slow_time_ms = self._get_tilt_time(slowMove=True)
            self.tilt_fast_time_ms = self._get_tilt_time(slowMove=False)
            self.hw.setTowerProfile("homingFast")
            self.hw.setTiltProfile("homingFast")
            self.hw.tiltUpWait()

    def _get_tilt_time(self, slowMove):
        tilt_time = 0
        total = self.hw_config.measuringMoves
        for i in range(total):
            self._logger.info(
                "Slow move %(count)d/%(total)d"
                if slowMove
                else "Fast move %(count)d/%(total)d" % {"count": i + 1, "total": total}
            )
            tilt_start_time = time()
            self.hw.tiltLayerUpWait()
            self.hw.tiltLayerDownWait(slowMove)
            tilt_time += time() - tilt_start_time

        return round(1000 * tilt_time / total)


class TiltCalibrationStartTest(SyncCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.TILT_CALIBRATION_START, Configuration(None, None), [Resource.TILT, Resource.TOWER_DOWN],
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
        self.hw = hw
        self.hw_config = hw_config

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
        position = self.hw.tilt_position
        if position is None:
            self.hw.beepAlarm(3)
            raise InvalidTiltAlignPosition(position)
        self.hw_config.tiltHeight = position
        self.tilt_aligned_event.set()

    def tilt_move(self, direction: int):
        self.hw.tilt_move(direction, fullstep=True)
