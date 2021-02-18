# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-lines
# pylint: disable=too-many-arguments
# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods


from __future__ import annotations

import asyncio
import concurrent.futures
import glob
import logging
import os
from abc import abstractmethod
from datetime import datetime, timedelta, timezone
from hashlib import md5
from logging import Logger
from queue import Queue, Empty
from threading import Thread, Event, Lock
from time import sleep
from typing import Optional, Any

import psutil
from PySignal import Signal

from sl1fw import defines, test_runtime
from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.configs.stats import TomlConfigStats
from sl1fw.errors.errors import (
    ExposureError,
    TiltFailed,
    TowerFailed,
    TowerMoveFailed,
    TempSensorFailed,
    FanFailed,
    ResinFailed,
    ResinTooLow,
    ResinTooHigh,
    WarningEscalation,
)
from sl1fw.errors.exceptions import NotAvailableInState, ExposureCheckDisabled
from sl1fw.errors.warnings import AmbientTooHot, AmbientTooCold, ResinNotEnough
from sl1fw.exposure.persistance import ExposurePickler, ExposureUnpickler
from sl1fw.functions.system import shut_down
from sl1fw.libHardware import Hardware
from sl1fw.project.functions import check_ready_to_print
from sl1fw.project.project import Project
from sl1fw.screen.screen import Screen
from sl1fw.states.exposure import ExposureState, ExposureCheck, ExposureCheckResult
from sl1fw.utils.traceable_collections import TraceableDict


class ExposureCheckRunner:
    def __init__(self, check: ExposureCheck, expo: Exposure):
        self.logger = logging.getLogger(__name__)
        self.check_type = check
        self.expo = expo
        self.warnings = []

    def __call__(self):
        self.logger.info("Running: %s", self.check_type)
        self.expo.check_results[self.check_type] = ExposureCheckResult.RUNNING
        try:
            self.run()
            if self.warnings:
                self.logger.warning("Check warnings: %s", self.warnings)
                self.expo.check_results[self.check_type] = ExposureCheckResult.WARNING
            else:
                self.logger.info("Success: %s", self.check_type)
                self.expo.check_results[self.check_type] = ExposureCheckResult.SUCCESS
        except ExposureCheckDisabled:
            self.logger.info("Disabled: %s", self.check_type)
            self.expo.check_results[self.check_type] = ExposureCheckResult.DISABLED
        except Exception:
            self.logger.exception("Exception: %s", self.check_type)
            self.expo.check_results[self.check_type] = ExposureCheckResult.FAILURE
            raise

    def raise_warning(self, warning):
        self.warnings.append(warning)
        self.expo.raise_preprint_warning(warning)

    @abstractmethod
    def run(self):
        ...


class TempsCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.TEMPERATURE, *args, **kwargs)

    def run(self):
        temperatures = self.expo.hw.getMcTemperatures()
        failed = [i for i in range(2) if temperatures[i] < 0]
        if failed:
            failed_names = [self.expo.hw.getSensorName(i) for i in failed]
            raise TempSensorFailed(failed, failed_names)

        if temperatures[1] < defines.minAmbientTemp:
            self.raise_warning(AmbientTooCold(temperatures[1]))
        elif temperatures[1] > defines.maxAmbientTemp:
            self.raise_warning(AmbientTooHot(temperatures[1]))


class CoverCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.COVER, *args, **kwargs)

    def run(self):
        if not self.expo.hw_config.coverCheck:
            self.logger.info("Disabling cover check")
            raise ExposureCheckDisabled()

        self.logger.info("Waiting for user to close the cover")
        with self.expo.pending_warning:
            while True:
                if self.expo.hw.isCoverClosed():
                    self.expo.state = ExposureState.CHECKS
                    self.logger.info("Cover closed")
                    return

                self.expo.state = ExposureState.COVER_OPEN
                sleep(0.1)


class ProjectDataCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.PROJECT, *args, **kwargs)

    def run(self):
        # Remove old projects
        self.logger.debug("Running disk cleanup")
        self.expo.check_and_clean_last_data()

        self.logger.debug("Running project copy and check")
        self.expo.project.copy_and_check()

        self.logger.info("Project after copy and check: %s", str(self.expo.project))

        # start data preparation by Screen
        self.logger.debug("Initiating project in Screen")
        self.expo.startProject()

        # show all warnings
        if self.expo.project.warnings:
            for warning in self.expo.project.warnings:
                self.raise_warning(warning)


class HardwareCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.HARDWARE, *args, **kwargs)

    def run(self):
        if test_runtime.injected_preprint_warning:
            self.raise_warning(test_runtime.injected_preprint_warning)

        self.logger.info("Syncing tower")
        self.expo.hw.towerSyncWait()
        if not self.expo.hw.isTowerSynced():
            raise TowerFailed()

        self.logger.info("Syncing tilt")
        self.expo.hw.tiltSyncWait()

        if not self.expo.hw.isTiltSynced():
            raise TiltFailed()

        self.logger.info("Tilting up")
        self.expo.hw.setTiltProfile("homingFast")
        self.expo.hw.tiltUp()
        while self.expo.hw.isTiltMoving():
            sleep(0.1)
        if not self.expo.hw.isTiltOnPosition():
            raise TiltFailed()


class FansCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.FAN, *args, **kwargs)

    def run(self):
        # Warm-up fans
        self.logger.info("Warming up fans")
        self.expo.hw.startFans()
        if not test_runtime.testing:
            self.logger.debug("Waiting %.2f secs for fans", defines.fanStartStopTime)
            sleep(defines.fanStartStopTime)
        else:
            self.logger.debug("Not waiting for fans to start due to testing")

        # Check fans
        self.logger.info("Checking fan errors")
        fans_state = self.expo.hw.getFansError().values()
        if any(fans_state) and not defines.fan_check_override:
            failed_fans = [num for num, state in enumerate(fans_state) if state]
            self.expo.check_results[ExposureCheck.FAN] = ExposureCheckResult.FAILURE
            failed_fan_names = [self.expo.hw.fans[i].name for i in failed_fans]
            failed_fans_text = ",".join(failed_fan_names)
            raise FanFailed(failed_fans, failed_fan_names, failed_fans_text)
        self.logger.info("Fans OK")

        self.expo.runtime_config.fan_error_override = False
        self.expo.runtime_config.check_cooling_expo = True


class ResinCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.RESIN, *args, **kwargs)

    def run(self):
        if not self.expo.hw_config.resinSensor:
            raise ExposureCheckDisabled()

        volume_ml = self.expo.hw.getResinVolume()
        self.expo.setResinVolume(volume_ml)

        try:
            if not volume_ml:
                raise ResinFailed(volume_ml)

            if volume_ml < defines.resinMinVolume:
                raise ResinTooLow(volume_ml, defines.resinMinVolume)

            if volume_ml > defines.resinMaxVolume:
                raise ResinTooHigh(volume_ml)
        except ResinFailed:
            self.expo.hw.setTowerProfile("homingFast")
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)
            raise

        required_volume_ml = self.expo.project.used_material + defines.resinMinVolume
        self.logger.debug(
            "min: %d [ml], requested: %d [ml], measured: %d [ml]", defines.resinMinVolume, required_volume_ml, volume_ml
        )
        if volume_ml < required_volume_ml:
            self.logger.info("Raising resin not enough warning")
            self.raise_warning(ResinNotEnough(volume_ml, required_volume_ml))


class StartPositionsCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.START_POSITIONS, *args, **kwargs)

    def run(self):
        self.logger.info("Prepare tank and resin")
        if self.expo.hw_config.tilt:
            self.logger.info("Tilting down")
            self.expo.hw.tiltDownWait()

        self.logger.info("Tower to print start position")
        self.expo.hw.setTowerProfile("homingFast")
        self.expo.hw.towerToPosition(0.25)  # TODO: Constant in code, seems important
        while not self.expo.hw.isTowerOnPosition(retries=2):
            sleep(0.25)

        if self.expo.hw.towerPositonFailed():
            exception = TowerMoveFailed()
            self.expo.exception = exception
            self.expo.hw.setTowerProfile("homingFast")
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)

            raise exception


class StirringCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.STIRRING, *args, **kwargs)

    def run(self):
        if not self.expo.hw_config.tilt:
            raise ExposureCheckDisabled()
        self.expo.hw.stirResin()


class Exposure:
    def __init__(
        self, job_id: int, hw_config: HwConfig, hw: Hardware, screen: Screen, runtime_config: RuntimeConfig,
    ):
        self.change = Signal()
        self.logger = logging.getLogger(__name__)
        self.hw_config = hw_config
        self.runtime_config = runtime_config
        self.project: Optional[Project] = None
        self.hw = hw
        self.screen = screen
        self.resin_count = 0.0
        self.resin_volume = None
        self.expoThread: Optional[Thread] = None
        self.tower_position_nm = 0
        self.actual_layer = 0
        self.slow_layers_done = 0
        self.printStartTime = datetime.fromtimestamp(0, tz=timezone.utc)
        self.printEndTime = datetime.fromtimestamp(0, tz=timezone.utc)
        self.state = ExposureState.READING_DATA
        self.remaining_wait_sec = 0
        self.low_resin = False
        self.warn_resin = False
        self.remain_resin_ml: Optional[float] = None
        self.exposure_end: Optional[datetime] = None
        self.instance_id = job_id
        self.check_results = TraceableDict()
        self.check_results.changed.connect(self._on_check_result_change)
        self.exception: Optional[ExposureError] = None
        self.warning: Optional[Warning] = None
        self.canceled = False
        self.commands = Queue()
        self.warning_dismissed = Event()
        self.warning_result: Optional[Exception] = None
        self.pending_warning = Lock()
        self.expoThread = Thread(target=self.run)

    def read_project(self, project_file: str):
        check_ready_to_print(self.hw_config, self.screen.printer_model.calibration(self.hw.is500khz))
        try:
            # Read project
            self.project = Project(self.hw_config, self.screen.printer_model, project_file)
            self.state = ExposureState.CONFIRM
            # Signal project change on its parameter change. This lets Exposure0 emit
            # property changed on properties bound to project parameters.
            self.project.params_changed.connect(self._on_project_changed)
        except Exception as exception:
            self.logger.exception("Exposure init exception")
            self.exception = exception
            self.state = ExposureState.FAILURE
            self.hw.uvLed(False)
            self.hw.stopFans()
            self.hw.motorsRelease()
        self.logger.info("Created new exposure object id: %s", self.instance_id)

    def _on_check_result_change(self):
        self.change.emit("check_results", self.check_results)

    def _on_project_changed(self):
        self.change.emit("project", None)

    def confirm_print_start(self):
        self.expoThread.start()
        self.commands.put("checks")

    def confirm_print_warning(self):
        self.logger.info("User confirmed print check warnings")
        self.warning_dismissed.set()

    def reject_print_warning(self):
        self.logger.info("User rejected print due to warnings")
        self.warning_result = WarningEscalation(self.warning)
        self.warning_dismissed.set()

    def cancel(self):
        self.logger.info("Canceling exposure")
        self.canceled = True
        if self.in_progress:
            # Will be terminated by after layer finished
            self.state = ExposureState.PENDING_ACTION
            self.doExitPrint()
        else:
            # Exposure thread not yet running (cancel before start)
            self.state = ExposureState.DONE
            self.write_last_exposure()

    def try_cancel(self):
        self.logger.info("Trying cancel exposure")
        cancelable_states = ExposureState.cancelable_states()
        if self.state in cancelable_states:
            self.canceled = True
            self.state = ExposureState.DONE
        else:
            raise NotAvailableInState(self.state, cancelable_states)
        return True

    def __setattr__(self, key: str, value: Any):
        # TODO: This is too generic
        # Would be better to have properties for all important attributes with separate signals
        # Or to separate important attributes to another object

        if key == "state" and hasattr(self, "state"):
            self.logger.info("State changed: %s -> %s", self.state, value)

        object.__setattr__(self, key, value)
        if not key.startswith("_"):
            self.change.emit(key, value)

    def startProject(self):
        self.tower_position_nm = 0
        self.actual_layer = 0
        self.resin_count = 0.0
        self.slow_layers_done = 0
        self.screen.new_project(self.project)

    def prepare(self):
        self.screen.preload_image(0)
        self.hw.setTowerProfile("layer")
        self.hw.towerMoveAbsoluteWait(0)  # first layer will move up

        self.screen.blank_screen()
        self.hw.uvLedPwm = self.hw_config.uvPwm
        if not self.hw_config.blinkExposure:
            self.hw.uvLed(True)

    @property
    def in_progress(self):
        if not self.expoThread:
            return False

        return self.expoThread.is_alive()

    @property
    def done(self):
        return self.state in ExposureState.finished_states()

    @property
    def progress(self) -> float:
        if self.state == ExposureState.FINISHED:
            return 1

        completed_layers = self.actual_layer - 1 if self.actual_layer else 0
        return completed_layers / self.project.total_layers

    def waitDone(self):
        if self.expoThread:
            self.expoThread.join()

    def doUpAndDown(self):
        self.state = ExposureState.PENDING_ACTION
        self.commands.put("updown")

    def doExitPrint(self):
        self.commands.put("exit")

    def doFeedMe(self):
        self.state = ExposureState.PENDING_ACTION
        self.commands.put("feedme")

    def doPause(self):
        self.commands.put("pause")

    def doContinue(self):
        self.commands.put("continue")

    def doBack(self):
        self.commands.put("back")

    def setResinVolume(self, volume):
        if volume is None:
            self.resin_volume = None
        else:
            self.resin_volume = volume + int(self.resin_count)

    def countRemainTime(self):
        if self.project:
            return self.project.count_remain_time(self.actual_layer, self.slow_layers_done)
        self.logger.warning("No active project to get remaining time")
        return -1

    def write_last_exposure(self):
        if self.hw_config.autoOff and not self.canceled:
            self.save()

    def save(self):
        self.logger.debug("Storing Exposure data")
        with open(defines.lastProjectPickler, "wb") as pickle_io:
            ExposurePickler(pickle_io).dump(self)

    @staticmethod
    def load(logger: Logger, hw: Hardware) -> Optional[Exposure]:
        try:
            with open(defines.lastProjectPickler, "rb") as pickle_io:
                exposure = ExposureUnpickler(pickle_io).load()
                # Fix missing (and still required attributes of exposure)
                exposure.change = Signal()
                exposure.hw = hw
                return exposure
        except FileNotFoundError:
            logger.info("Last exposure data not present")
        except Exception:
            logger.exception("Last exposure data failed to load!")
            return None

    def check_and_clean_last_data(self) -> None:
        clear_all = self.project.path and not str(self.project.path).startswith(defines.previousPrints)
        Exposure.cleanup_last_data(self.logger, clear_all=clear_all)

    @staticmethod
    def cleanup_last_data(logger: Logger, clear_all=False) -> None:
        if clear_all:
            files = glob.glob(defines.previousPrints + "/*")
        else:
            files = [
                defines.lastProjectHwConfig,
                defines.lastProjectFactoryFile,
                defines.lastProjectConfigFile,
                defines.lastProjectPickler,
            ]
        for project_file in files:
            logger.debug("removing '%s'", project_file)
            try:
                os.remove(project_file)
            except Exception:
                logger.exception("cleanup_last_data() exception:")

    def stats_seen(self):
        self.state = ExposureState.DONE

    def _do_frame(self, times_ms, prev_white_pixels, was_stirring, second):
        position_steps = self.hw_config.nm_to_tower_microsteps(self.tower_position_nm) + self.hw_config.calibTowerOffset
        slow_move = prev_white_pixels > self.screen.white_pixels_threshold

        if self.hw_config.tilt:
            if self.hw_config.layerTowerHop and slow_move:
                self.hw.towerMoveAbsoluteWait(position_steps + self.hw_config.layerTowerHop)
                self.hw.tiltLayerUpWait(slow_move)
                self.hw.towerMoveAbsoluteWait(position_steps)
            else:
                self.hw.towerMoveAbsoluteWait(position_steps)
                self.hw.tiltLayerUpWait(slow_move)
        else:
            self.hw.towerMoveAbsoluteWait(position_steps + self.hw_config.layerTowerHop)
            self.hw.towerMoveAbsoluteWait(position_steps)
        self.hw.setTowerCurrent(defines.towerHoldCurrent)

        white_pixels = self.screen.sync_preloader()
        self.screen.screenshot_rename(second)

        if self.hw_config.delayBeforeExposure:
            self.logger.info("delayBeforeExposure [s]: %f", self.hw_config.delayBeforeExposure / 10.0)
            sleep(self.hw_config.delayBeforeExposure / 10.0)

        if was_stirring:
            self.logger.info("stirringDelay [s]: %f", self.hw_config.stirringDelay / 10.0)
            sleep(self.hw_config.stirringDelay / 10.0)

        # FIXME WTF?
        if self.hw_config.tilt:
            self.hw.getMcTemperatures()

        self.screen.blit_image(second)

        exp_time_ms = sum(times_ms)
        self.exposure_end = datetime.now(tz=timezone.utc) + timedelta(seconds=exp_time_ms / 1e3)
        self.logger.info("Exposure started: %d ms, end: %s", exp_time_ms, self.exposure_end)

        i = 0
        for time_ms in times_ms:
            uv_on_remain_ms = time_ms
            if self.hw_config.blinkExposure:
                uv_is_on = True
                self.logger.debug("uv on")
                self.hw.uvLed(True, time_ms)
                while uv_is_on:
                    sleep(uv_on_remain_ms / 1100.0)
                    uv_is_on, uv_on_remain_ms = self.hw.getUvLedState()
            else:
                sleep(time_ms / 1e3)
            self.screen.fill_area(i)
            i += 1

        self.screen.blank_screen()
        self.logger.info("exposure done")
        self.screen.preload_image(self.actual_layer + 1)

        temperatures = self.hw.getMcTemperatures()
        self.logger.info("UV temperature [C]: %.1f  Ambient temperature [C]: %.1f", temperatures[0], temperatures[1])

        if self.hw_config.delayAfterExposure:
            self.logger.info("delayAfterExposure [s]: %f", self.hw_config.delayAfterExposure / 10.0)
            sleep(self.hw_config.delayAfterExposure / 10.0)

        if self.hw_config.tilt:
            slow_move = white_pixels > self.screen.white_pixels_threshold
            if slow_move:
                self.slow_layers_done += 1
            if not self.hw.tiltLayerDownWait(slow_move):
                return False, white_pixels

        return True, white_pixels

    def upAndDown(self):
        self.hw.powerLed("warn")
        if self.hw_config.blinkExposure and self.hw_config.upAndDownUvOn:
            self.hw.uvLed(True)

        self.state = ExposureState.GOING_UP
        self.hw.setTowerProfile("homingFast")
        self.hw.towerToTop()
        while not self.hw.isTowerOnTop():
            sleep(0.25)

        self.state = ExposureState.WAITING
        for sec in range(self.hw_config.upAndDownWait):
            cnt = self.hw_config.upAndDownWait - sec
            self.remaining_wait_sec = cnt
            sleep(1)
            if self.hw_config.coverCheck and not self.hw.isCoverClosed():
                self.state = ExposureState.COVER_OPEN
                while not self.hw.isCoverClosed():
                    sleep(1)
                self.state = ExposureState.WAITING

        if self.hw_config.tilt:
            self.state = ExposureState.STIRRING
            self.hw.stirResin()

        self.state = ExposureState.GOING_DOWN
        position = self.hw_config.upAndDownZoffset
        if position < 0:
            position = 0
        self.hw.towerMoveAbsolute(position)
        while not self.hw.isTowerOnPosition():
            sleep(0.25)
        self.hw.setTowerProfile("layer")
        self.hw.powerLed("normal")

        self.state = ExposureState.PRINTING

    def doWait(self, beep=False):
        command = None
        break_free = {"exit", "back", "continue"}
        while not command:
            if beep:
                self.hw.beepAlarm(3)
            sleep(1)

            try:
                command = self.commands.get_nowait()
            except Empty:
                command = None
            except Exception:
                self.logger.exception("getCommand exception")
                command = None

            if command in break_free:
                break

        return command

    def doStuckRelease(self):
        self.state = ExposureState.STUCK
        self.hw.powerLed("error")
        self.hw.towerHoldTiltRelease()
        if self.doWait(True) == "back":
            raise TiltFailed()

        self.hw.powerLed("warn")
        self.state = ExposureState.STUCK_RECOVERY

        if not self.hw.tiltSyncWait(retries=1):
            self.logger.error("Stuck release failed")
            raise TiltFailed()

        self.state = ExposureState.STIRRING
        self.hw.stirResin()
        self.hw.powerLed("normal")
        self.state = ExposureState.PRINTING

    def run(self):
        try:
            self.logger.info("Started exposure thread")

            while not self.done:
                command = self.commands.get()
                if command == "exit":
                    self.logger.info("Exiting exposure thread on exit command")
                    break

                if command == "checks":
                    asyncio.run(self._run_checks())
                    self.run_exposure()
                else:
                    self.logger.error('Undefined command: "%s" ignored', command)

            self.logger.info("Exiting exposure thread on state: %s", self.state)
        except Exception as exception:
            self.logger.exception("Exposure thread exception")
            self.exception = exception
            if not isinstance(exception, (TiltFailed, TowerFailed)):
                self._final_go_up()
            self.state = ExposureState.FAILURE
            self.hw.uvLed(False)
            self.hw.stopFans()
            self.hw.motorsRelease()
        if self.project:
            self.project.data_close()

    def raise_preprint_warning(self, warning: Warning):
        self.logger.warning("Warning being raised in pre-print: %s", type(warning))
        with self.pending_warning:
            self.warning_result = None
            self.warning = warning
            old_state = self.state
            self.state = ExposureState.CHECK_WARNING
            self.warning_dismissed.clear()
            self.logger.debug("Waiting for warning resolution")
            self.warning_dismissed.wait()
            self.logger.debug("Warnings resolved")
            self.warning = None
            self.state = old_state
            if self.warning_result:
                raise self.warning_result  # pylint: disable = raising-bad-type

    async def _run_checks(self):
        self.state = ExposureState.CHECKS
        self.logger.info("Running pre-print checks")
        self.check_results.update({check: ExposureCheckResult.SCHEDULED for check in ExposureCheck})

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            fans = loop.run_in_executor(pool, FansCheck(self))
            temps = loop.run_in_executor(pool, TempsCheck(self))
            project = loop.run_in_executor(pool, ProjectDataCheck(self))
            hw = asyncio.create_task(self._check_hw_related())

            self.logger.debug("Waiting for pre-print checks to finish")
            await asyncio.gather(fans, temps, project, hw)

    async def _check_hw_related(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, CoverCheck(self))
            await loop.run_in_executor(pool, HardwareCheck(self))
            await loop.run_in_executor(pool, ResinCheck(self))
            await loop.run_in_executor(pool, StartPositionsCheck(self))
            await loop.run_in_executor(pool, StirringCheck(self))

    def run_exposure(self):
        # TODO: Where is this supposed to be called from?
        self.prepare()

        self.logger.info("Running exposure")
        self.state = ExposureState.PRINTING
        self.printStartTime = datetime.now(tz=timezone.utc)
        statistics = TomlConfigStats(defines.statsData, self.hw)
        statistics.load()
        statistics["started_projects"] += 1
        statistics.save_raw()
        seconds = 0

        project = self.project
        project_hash = md5(project.name.encode()).hexdigest()[:8] + "_"
        prev_white_pixels = 0
        was_stirring = True
        exposure_compensation = 0

        while self.actual_layer < project.total_layers:
            try:
                command = self.commands.get_nowait()
            except Empty:
                command = None
            except Exception:
                self.logger.exception("getCommand exception")
                command = None

            if command == "updown":
                self.upAndDown()
                was_stirring = True
                exposure_compensation = self.hw_config.upAndDownExpoComp * 100

            if command == "exit":
                break

            if command == "pause":
                if not self.hw_config.blinkExposure:
                    self.hw.uvLed(False)

                if self.doWait(False) == "exit":
                    break

                if not self.hw_config.blinkExposure:
                    self.hw.uvLed(True)

            if self.resin_volume:
                self.remain_resin_ml = self.resin_volume - int(self.resin_count)
                self.warn_resin = self.remain_resin_ml < defines.resinLowWarn
                self.low_resin = self.remain_resin_ml < defines.resinFeedWait

            if command == "feedme" or self.low_resin:
                self.hw.powerLed("warn")
                if self.hw_config.tilt:
                    self.hw.tiltLayerUpWait()
                self.state = ExposureState.FEED_ME
                self.doWait(self.low_resin)

                # Force user to close the cover
                self._wait_cover_close()

                # Stir resin before resuming print
                if self.hw_config.tilt:
                    self.state = ExposureState.STIRRING
                    self.hw.setTiltProfile("homingFast")
                    self.hw.tiltDownWait()
                    self.hw.stirResin()
                was_stirring = True

                # Resume print
                self.hw.powerLed("normal")
                self.state = ExposureState.PRINTING

            if (
                self.hw_config.upAndDownEveryLayer
                and self.actual_layer
                and not self.actual_layer % self.hw_config.upAndDownEveryLayer
            ):
                self.doUpAndDown()
                was_stirring = True
                exposure_compensation = self.hw_config.upAndDownExpoComp * 100

            layer = project.layers[self.actual_layer]

            self.tower_position_nm += layer.height_nm

            self.logger.info(
                "Layer started » {"
                " 'layer': '%04d/%04d (%s)',"
                " 'exposure [ms]': %s,"
                " 'slow_layers_done': %d,"
                " 'height [mm]': '%.3f/%.3f',"
                " 'elapsed [min]': %d,"
                " 'remain [min]': %d,"
                " 'used [ml]': %d,"
                " 'remaining [ml]': %d,"
                " 'RAM': '%.1f%%',"
                " 'CPU': '%.1f%%'"
                " }",
                self.actual_layer + 1,
                project.total_layers,
                layer.image.replace(project.name, project_hash),
                str(layer.times_ms),
                self.slow_layers_done,
                self.tower_position_nm / 1e6,
                project.total_height_nm / 1e6,
                int(round((datetime.now(tz=timezone.utc) - self.printStartTime).total_seconds() / 60)),
                self.countRemainTime(),
                self.resin_count,
                self.remain_resin_ml if self.remain_resin_ml else -1,
                psutil.virtual_memory().percent,
                psutil.cpu_percent(),
            )

            times_ms = layer.times_ms.copy()
            times_ms[0] += exposure_compensation

            success, white_pixels = self._do_frame(times_ms, prev_white_pixels, was_stirring, False)
            if not success:
                self.doStuckRelease()
                self.hw.powerLed("normal")

            # exposure of the second part
            if project.per_partes and white_pixels > self.screen.white_pixels_threshold:
                success, dummy = self._do_frame(times_ms, white_pixels, was_stirring, True)
                if not success:
                    self.doStuckRelease()

            prev_white_pixels = white_pixels
            was_stirring = False
            exposure_compensation = 0

            # /1e21 (1e7 ** 3) - we want cm3 (=ml) not nm3
            self.resin_count += (
                white_pixels * self.screen.printer_model.exposure_screen.pixel_size_nm ** 2 * layer.height_nm / 1e21
            )
            self.logger.debug("resin_count: %f", self.resin_count)

            seconds = (datetime.now(tz=timezone.utc) - self.printStartTime).total_seconds()

            if self.hw_config.trigger:
                self.hw.cameraLed(True)
                sleep(self.hw_config.trigger / 10.0)
                self.hw.cameraLed(False)

            self.actual_layer += 1

        self.hw.saveUvStatistics()
        self.hw.uvLed(False)

        self._final_go_up()

        self.hw.stopFans()
        self.hw.motorsRelease()

        self.printEndTime = datetime.now(tz=timezone.utc)

        is_finished = not self.canceled
        if is_finished:
            statistics["finished_projects"] += 1
        statistics["layers"] += self.actual_layer
        statistics["total_seconds"] += seconds
        statistics["total_resin"] += self.resin_count
        statistics.save_raw()
        exposure_times = "{0:d}/{1:d}/{2:d} s".format(
            project.exposure_time_first_ms, project.exposure_time_ms, project.exposure_time_calibrate_ms
        )
        self.logger.info(
            "Job finished » { 'job': %d, 'project': '%s', 'finished': %s, "
            "'autoOff': %s, 'Layers': '%d/%d', 'printTime [s]': %d, "
            "'used [ml]': %g, 'remaining [ml]': %g, 'exposure [s]': '%s', 'height [mm]': %g, }",
            statistics["started_projects"],
            project_hash[:-1],
            is_finished,
            self.hw_config.autoOff,
            self.actual_layer,
            project.total_layers,
            seconds,
            self.resin_count,
            self.remain_resin_ml if self.remain_resin_ml else -1,
            exposure_times,
            self.tower_position_nm / 1e6,
        )

        self.screen.save_display_usage()

        if self.canceled:
            self.state = ExposureState.CANCELED
        else:
            self.state = ExposureState.FINISHED

        self.write_last_exposure()

        if not self.canceled:
            if self.hw_config.autoOff:
                shut_down(self.hw)

        self.logger.debug("Exposure ended")

    def _wait_cover_close(self) -> bool:
        """
        Waits for cover close

        :return: True if was waiting false otherwise
        """
        if not self.hw_config.coverCheck:
            return False

        if self.hw.isCoverClosed():
            self.logger.info("Cover already closed skipping close wait")
            return False

        self.logger.info("Waiting for user to close the cover")
        old_state = self.state
        while not self.hw.isCoverClosed():
            self.state = ExposureState.COVER_OPEN
            sleep(0.1)
        self.state = old_state
        self.logger.info("Cover closed now")
        return True

    def _final_go_up(self):
        self.state = ExposureState.GOING_UP
        self.hw.setTowerProfile("homingFast")
        self.hw.towerToTop()
        while not self.hw.isTowerOnTop():
            sleep(0.25)
