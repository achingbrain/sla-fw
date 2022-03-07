# This file is part of the SLA firmware
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
import glob
import logging
import os
from abc import abstractmethod
from asyncio import CancelledError, Task
from datetime import datetime, timedelta, timezone
from hashlib import md5
from logging import Logger
from queue import Queue, Empty
from threading import Thread, Event, Lock
from time import sleep, monotonic_ns
from typing import Optional, Any, List, Dict

import psutil
from PySignal import Signal

from slafw import defines, test_runtime
from slafw.configs.runtime import RuntimeConfig
from slafw.configs.stats import TomlConfigStats
from slafw.errors import tests
from slafw.errors.errors import (
    TiltFailed,
    TowerFailed,
    TowerMoveFailed,
    TowerHomeFailed,
    TempSensorFailed,
    FanFailed,
    ResinMeasureFailed,
    ResinTooLow,
    ResinTooHigh,
    WarningEscalation,
    NotAvailableInState,
    ExposureCheckDisabled, ExposureError,
)
from slafw.errors.warnings import AmbientTooHot, AmbientTooCold, ResinNotEnough, PrinterWarning, ExpectOverheating
from slafw.exposure.persistance import ExposurePickler, ExposureUnpickler
from slafw.functions.system import shut_down
from slafw.libHardware import Hardware
from slafw.project.functions import check_ready_to_print
from slafw.project.project import Project, ExposureUserProfile
from slafw.image.exposure_image import ExposureImage
from slafw.states.exposure import ExposureState, ExposureCheck, ExposureCheckResult
from slafw.utils.traceable_collections import TraceableDict
from slafw.hardware.tilt import TiltSpeed

class ExposureCheckRunner:
    def __init__(self, check: ExposureCheck, expo: Exposure):
        self.logger = logging.getLogger(__name__)
        self.check_type = check
        self.expo = expo
        self.warnings: List[PrinterWarning] = []

    async def start(self):
        self.logger.info("Running: %s", self.check_type)
        self.expo.check_results[self.check_type] = ExposureCheckResult.RUNNING
        try:
            await self.run()
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
    async def run(self):
        ...


class TempsCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.TEMPERATURE, *args, **kwargs)

    async def run(self):
        if test_runtime.injected_preprint_warning:
            self.raise_warning(test_runtime.injected_preprint_warning)
        temperatures = self.expo.hw.getMcTemperatures()
        failed = [i for i in (self.expo.hw.led_temp_idx, self.expo.hw.ambient_temp_idx) if temperatures[i] < 0]
        if failed:
            failed_names = [self.expo.hw.getSensorName(i) for i in failed]
            failed_names = ", ".join(failed_names)
            raise TempSensorFailed(failed_names)

        if temperatures[1] < defines.minAmbientTemp:
            self.raise_warning(AmbientTooCold(temperatures[1]))
        elif temperatures[1] > defines.maxAmbientTemp:
            self.raise_warning(AmbientTooHot(temperatures[1]))


class CoverCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.COVER, *args, **kwargs)

    async def run(self):
        if not self.expo.hw.config.coverCheck:
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
                await asyncio.sleep(0.1)


class ProjectDataCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.PROJECT, *args, **kwargs)

    async def run(self):
        await asyncio.sleep(0)
        self.logger.debug("Running disk cleanup")
        self.expo.check_and_clean_last_data()
        await asyncio.sleep(0)
        self.logger.debug("Running project copy and check")
        self.expo.project.copy_and_check()
        self.logger.info("Project after copy and check: %s", str(self.expo.project))
        await asyncio.sleep(0)
        self.logger.debug("Initiating project in ExposureImage")
        self.expo.startProject()
        await asyncio.sleep(0)
        # show all warnings
        if self.expo.project.warnings:
            for warning in self.expo.project.warnings:
                self.raise_warning(warning)
        await asyncio.sleep(0)


class FansCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.FAN, *args, **kwargs)

    async def run(self):
        # Warm-up fans
        self.logger.info("Warming up fans")
        self.expo.hw.startFans()
        if not test_runtime.testing:
            self.logger.debug("Waiting %.2f secs for fans", defines.fanStartStopTime)
            await asyncio.sleep(defines.fanStartStopTime)
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


class ResinCheck(ExposureCheckRunner):
    RETRIES = 2

    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.RESIN, *args, **kwargs)

    async def measure_resin_retries(self, retries: int) -> int:
        try:
            return await self.do_measure_resin()
        except (ResinMeasureFailed, ResinTooLow, ResinTooHigh):
            if retries:
                return await self.measure_resin_retries(retries - 1)
            raise

    async def do_measure_resin(self) -> int:
        volume_ml = await self.expo.hw.get_resin_volume_async()
        self.expo.setResinVolume(volume_ml)

        try:
            if not volume_ml:
                raise ResinMeasureFailed(volume_ml)

            if volume_ml < defines.resinMinVolume:
                raise ResinTooLow(volume_ml, defines.resinMinVolume)

            if volume_ml > defines.resinMaxVolume:
                raise ResinTooHigh(volume_ml)
        except ResinMeasureFailed:
            await self.expo.hw.tower_to_resin_measurement_start_position()
            raise
        return volume_ml

    async def run(self):
        if not self.expo.hw.config.resinSensor:
            raise ExposureCheckDisabled()

        volume_ml = await self.measure_resin_retries(self.RETRIES)

        required_volume_ml = self.expo.project.used_material + defines.resinMinVolume
        self.logger.debug(
            "min: %d [ml], requested: %d [ml], measured: %d [ml]", defines.resinMinVolume, required_volume_ml, volume_ml
        )

        # User is already informed about required refill during print if project has volume over 100 %
        if volume_ml < required_volume_ml <= defines.resinMaxVolume:
            self.logger.info("Raising resin not enough warning")
            self.raise_warning(ResinNotEnough(volume_ml, required_volume_ml))


class StartPositionsCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.START_POSITIONS, *args, **kwargs)

    async def run(self):
        # tilt is handled by StirringCheck

        self.logger.info("Tower to print start position, tilt_speed=%s",
                         self.expo.project._exposure_user_profile.name)  # pylint: disable=protected-access

        # Go almost down, then go slowly the rest of the way
        if self.expo.project._exposure_user_profile == ExposureUserProfile.HIGH_VISCOSITY:  # pylint: disable=protected-access
            slow_movement_start_position_nm = 35_000_000
            # Only move to the slow_movement_start_position_nm if too high
            if self.expo.hw.tower_position_nm > slow_movement_start_position_nm:
                self.logger.info("HIGH_VISCOSITY tilt speed, going fast down, will slow down %d mm above the bottom",
                                 slow_movement_start_position_nm/1_000_000)
                self.expo.hw.setTowerProfile("homingFast")
                self.expo.hw.tower_position_nm = slow_movement_start_position_nm
                while self.expo.hw.isTowerMoving():
                    await asyncio.sleep(0.25)
                if abs(slow_movement_start_position_nm - self.expo.hw.tower_position_nm) > 10:
                    raise TowerMoveFailed()
            self.logger.info("HIGH_VISCOSITY tilt speed, setting tower to superSlow profile")
            self.expo.hw.setTowerProfile("superSlow")
        else:
            self.expo.hw.setTowerProfile("homingFast")
        self.expo.hw.towerToPosition(0.25)  # TODO: Constant in code, seems important
        while not await self.expo.hw.isTowerOnPositionAsync(retries=2):
            await asyncio.sleep(0.25)

        if self.expo.hw.towerPositonFailed():
            exception = TowerMoveFailed()
            self.expo.fatal_error = exception
            self.expo.hw.setTowerProfile("homingFast")
            self.expo.hw.towerToTop()
            while not await self.expo.hw.isTowerOnPositionAsync():
                await asyncio.sleep(0.25)

            raise exception
        while self.expo.hw.tilt.moving:
            await asyncio.sleep(0.25)


class StirringCheck(ExposureCheckRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(ExposureCheck.STIRRING, *args, **kwargs)

    async def run(self):
        if not self.expo.hw.config.tilt:
            raise ExposureCheckDisabled()
        # Stirring is run at the start, when the correct tilt_speed is not yet set
        stirring_tilt_speed = TiltSpeed.SUPERSLOW if self.expo.project.exposure_user_profile == ExposureUserProfile.HIGH_VISCOSITY else TiltSpeed.DEFAULT
        await self.expo.hw.tilt.stir_resin_async(stirring_tilt_speed)


class Exposure:
    def __init__(
        self,
        job_id: int,
        hw: Hardware,
        exposure_image: ExposureImage,
        runtime_config: RuntimeConfig,
    ):
        self.change = Signal()
        self.logger = logging.getLogger(__name__)
        self.runtime_config = runtime_config
        self.project: Optional[Project] = None
        self.hw = hw
        self.exposure_image = exposure_image
        self.resin_count = 0.0
        self.resin_volume = None
        self._thread: Optional[Thread] = None
        self.tower_position_nm = 0
        self.actual_layer = 0
        self.slow_layers_done = 0
        self.super_slow_layers_done = 0
        self.printStartTime = datetime.now(tz=timezone.utc)
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
        self.fatal_error: Optional[Exception] = None
        self.warning_occurred = Signal()  # Generic warning has been issued
        self.warning: Optional[Warning] = None  # Current preprint warning
        self.canceled = False
        self.commands: Queue[str] = Queue()  # pylint: disable=unsubscriptable-object
        self.warning_dismissed = Event()
        self.warning_result: Optional[Exception] = None
        self.pending_warning = Lock()
        self.estimated_total_time_ms = -1
        self._thread = Thread(target=self.run)
        self._tilt_speed: TiltSpeed = TiltSpeed.SLOW
        self._force_slow_remain_nm: int = 0
        self.hw.fans_error_changed.connect(self._on_fans_error)
        self._checks_task: Task = None


    def read_project(self, project_file: str):
        check_ready_to_print(self.hw.config, self.hw.printer_model.calibration_parameters(self.hw.is500khz))
        try:
            # Read project
            self.project = Project(self.hw, project_file)
            self.estimated_total_time_ms = self.estimate_total_time_ms()
            self.state = ExposureState.CONFIRM
            # Signal project change on its parameter change. This lets Exposure0 emit
            # property changed on properties bound to project parameters.
            self.project.params_changed.connect(self._on_project_changed)
        except ExposureError as exception:
            self.logger.exception("Exposure init exception")
            self.fatal_error = exception
            self.state = ExposureState.FAILURE
            self.hw.uvLed(False)
            self.hw.stopFans()
            self.hw.motorsRelease()
            raise
        self.logger.info("Created new exposure object id: %s", self.instance_id)

    def _on_check_result_change(self):
        self.change.emit("check_results", self.check_results)

    def _on_project_changed(self):
        self.estimated_total_time_ms = self.estimate_total_time_ms()
        self.change.emit("project", None)

    def confirm_print_start(self):
        self._thread.start()
        self.commands.put("pour_resin_in")

    def confirm_resin_in(self):
        self.commands.put("checks")

    def confirm_print_warning(self):
        self.logger.info("User confirmed print check warnings")
        self.warning_dismissed.set()

    def reject_print_warning(self):
        self.logger.info("User rejected print due to warnings")
        self.warning_result = WarningEscalation(self.warning)
        self.warning_dismissed.set()

    def cancel(self):
        self.canceled = True
        if self.in_progress:
            # Will be terminated by after layer finished
            if self.state == ExposureState.CHECKS and self._checks_task:
                self.logger.info("Canceling preprint checks")
                self.state = ExposureState.PENDING_ACTION
                self._checks_task.cancel()
            else:
                self.logger.info("Canceling exposure")
                self.state = ExposureState.PENDING_ACTION
                self.doExitPrint()
        else:
            # Exposure thread not yet running (cancel before start)
            self.logger.info("Canceling not started exposure")
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
        self.super_slow_layers_done = 0
        self.exposure_image.new_project(self.project)

    def prepare(self):
        self.exposure_image.preload_image(0)
        if self.project.exposure_user_profile == ExposureUserProfile.HIGH_VISCOSITY:
            self.hw.setTowerProfile("superSlow")
            self.logger.info("%s now going slowly rest of the way", "HIGH_VISCOSITY")
        else:
            self.hw.setTowerProfile("layer")

        self.hw.towerMoveAbsoluteWait(0)  # first layer will move up

        self.exposure_image.blank_screen()
        self.hw.uvLedPwm = self.hw.config.uvPwmPrint
        self.hw.uvDisplayCounter(True)

    @property
    def in_progress(self):
        if not self._thread:
            return False

        return self._thread.is_alive()

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
        if self._thread:
            self._thread.join()

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
            self.remain_resin_ml = volume

    def estimate_total_time_ms(self):
        if self.project:
            return self.project.count_remain_time(0, 0)
        self.logger.warning("No active project to get estimated print time")
        return -1

    def estimate_remain_time_ms(self) -> int:
        if self.project:
            return self.project.count_remain_time(self.actual_layer, self.slow_layers_done, self.super_slow_layers_done)
        self.logger.warning("No active project to get remaining time")
        return -1

    def expected_finish_timestamp(self) -> float:
        """
        Get timestamp of expected print end

        :return: Timestamp as float
        """
        end = datetime.now(tz=timezone.utc) + timedelta(milliseconds=self.estimate_remain_time_ms())
        return end.timestamp()

    def write_last_exposure(self):
        if self.hw.config.autoOff and not self.canceled:
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
            except IsADirectoryError:
                logger.debug("Is a directory '%s'", project_file)
            except FileNotFoundError:
                logger.debug("No such file '%s'", project_file)
            except Exception:
                logger.exception("cleanup_last_data() exception:")

    def stats_seen(self):
        self.state = ExposureState.DONE

    def _exposure_simple(self, times_ms):
        uv_on_remain_ms = times_ms[0]
        uv_is_on = True
        self.logger.debug("uv on")
        self.hw.uvLed(True, uv_on_remain_ms + 1)    # FIXME workaround for MC FW (1 ms shorted UV LED time)
        while uv_is_on:
            sleep(uv_on_remain_ms / 1100.0)
            uv_is_on, uv_on_remain_ms = self.hw.getUvLedState()
        self.exposure_image.blank_screen()

    def _exposure_calibration(self, times_ms):
        end = monotonic_ns()
        ends = []
        for time_ms in times_ms:
            end += time_ms * 1e6
            ends.append(end)
        i = 0
        last = len(ends) - 1
        self.logger.debug("uv on")
        self.hw.uvLed(True)
        for end in ends:
            diff = 0
            while diff >= 0:
                sleep(diff / 1e9 / 1.1)
                diff = end - monotonic_ns()
            self.exposure_image.blank_area(i, i == last)
            i += 1
            if abs(diff) > 1e7:
                self.logger.warning("Exposure end delayed %f ms", abs(diff) / 1e6)
        self.hw.uvLed(False)

    def _do_frame(self, times_ms, was_stirring, second, layer_height_nm):
        position_steps = self.hw.config.nm_to_tower_microsteps(self.tower_position_nm) + self.hw.config.calibTowerOffset

        if self.hw.config.tilt:
            if self.project.exposure_user_profile == ExposureUserProfile.HIGH_VISCOSITY:
                self._tilt_speed = TiltSpeed.SUPERSLOW
            minimal_tower_hop_steps = self.hw.config.calcMicroSteps(self.hw.config.superSlowTowerHopHeight_mm)
            self.logger.info("%s tilt up", self._tilt_speed.name)
            if self.hw.config.layerTowerHop or self._tilt_speed == TiltSpeed.SUPERSLOW:
                hop_position = position_steps + self.hw.config.layerTowerHop
                if self._tilt_speed == TiltSpeed.SUPERSLOW:
                    if self.hw.getTowerProfile() != "superSlow":
                        self.hw.setTowerProfile("superSlow")
                    if self._tilt_speed == TiltSpeed.SUPERSLOW and self.hw.config.layerTowerHop < minimal_tower_hop_steps:
                        self.logger.info("%s forcing layerTowerHop = %s", self._tilt_speed.name, minimal_tower_hop_steps)
                        hop_position = position_steps + minimal_tower_hop_steps
                elif self.hw.getTowerProfile() != "layer":
                    self.hw.setTowerProfile("layer")
                self.hw.towerMoveAbsoluteWait(hop_position)
                self.hw.tilt.layer_up_wait(tilt_speed=self._tilt_speed)
                self.hw.towerMoveAbsoluteWait(position_steps)
                self.logger.info("layerTowerHop finished.")
            else:
                self.hw.towerMoveAbsoluteWait(position_steps)
                self.hw.tilt.layer_up_wait(tilt_speed=self._tilt_speed)
        else:
            self.hw.towerMoveAbsoluteWait(position_steps + self.hw.config.layerTowerHop)
            self.hw.towerMoveAbsoluteWait(position_steps)
        self.hw.setTowerCurrent(defines.towerHoldCurrent)

        self._tilt_speed = TiltSpeed(self.project.exposure_user_profile)
        white_pixels = self.exposure_image.sync_preloader()
        self.exposure_image.screenshot_rename(second)

        if self.project.exposure_user_profile == ExposureUserProfile.SAFE:
            delay_before = defines.exposure_safe_delay_before
        elif self.project.exposure_user_profile == ExposureUserProfile.HIGH_VISCOSITY:
            delay_before = defines.exposure_superslow_delay_before
        elif self._tilt_speed == TiltSpeed.SLOW:
            delay_before = defines.exposure_slow_move_delay_before
        elif self._tilt_speed == TiltSpeed.SUPERSLOW:
            delay_before = defines.exposure_superslow_delay_before
        else:
            delay_before = self.hw.config.delayBeforeExposure

        if delay_before:
            self.logger.info("delayBeforeExposure [s]: %f", delay_before / 10.0)
            sleep(delay_before / 10.0)

        if was_stirring:
            self.logger.info("stirringDelay [s]: %f", self.hw.config.stirringDelay / 10.0)
            sleep(self.hw.config.stirringDelay / 10.0)

        # FIXME WTF? :)
        if self.hw.config.tilt:
            self.hw.getMcTemperatures()

        self.exposure_image.blit_image(second)

        exp_time_ms = sum(times_ms)
        self.exposure_end = datetime.now(tz=timezone.utc) + timedelta(seconds=exp_time_ms / 1e3)
        self.logger.info("Exposure started: %d ms, end: %s", exp_time_ms, self.exposure_end)

        if len(times_ms) == 1:
            self._exposure_simple(times_ms)
        else:
            self._exposure_calibration(times_ms)

        self.logger.info("exposure done")
        self.exposure_image.preload_image(self.actual_layer + 1)

        temperatures = self.hw.getMcTemperatures()
        self.logger.info(
            "UV temperature [C]: %.1f  Ambient temperature [C]: %.1f",
            temperatures[self.hw.led_temp_idx],
            temperatures[self.hw.ambient_temp_idx],
        )

        if self.hw.config.delayAfterExposure:
            self.logger.info("delayAfterExposure [s]: %f", self.hw.config.delayAfterExposure / 10.0)
            sleep(self.hw.config.delayAfterExposure / 10.0)

        if self.hw.config.tilt:
            # Slow down if white_pixels > self.hw.white_pixels_threshold  # current layer
            if self._tilt_speed in {TiltSpeed.DEFAULT} and white_pixels > self.hw.white_pixels_threshold:
                self._tilt_speed = TiltSpeed.SLOW
            # Force slow tilt for forceSlowTiltHeight if current layer area > limit4fast
            if self._tilt_speed in {TiltSpeed.SLOW}:
                self._force_slow_remain_nm = self.hw.config.forceSlowTiltHeight
            elif self._tilt_speed in {TiltSpeed.DEFAULT} and self._force_slow_remain_nm > 0:
                self._force_slow_remain_nm -= layer_height_nm
                self._tilt_speed = TiltSpeed.SLOW

            # Force slow tilt on first layers or if user selected safe print profile
            if (
                self.actual_layer < self.project.first_slow_layers and self._tilt_speed == TiltSpeed.DEFAULT
                or self.project.exposure_user_profile == ExposureUserProfile.SAFE
            ):
                self._tilt_speed = TiltSpeed.SLOW

            if self._tilt_speed == TiltSpeed.SLOW:
                self.slow_layers_done += 1
            elif self._tilt_speed == TiltSpeed.SUPERSLOW:
                self.super_slow_layers_done += 1
            try:
                self.logger.info("%s tilt down", self._tilt_speed.name)
                self.hw.tilt.layer_down_wait(self._tilt_speed)
            except Exception:
                return False, white_pixels

        return True, white_pixels

    def upAndDown(self):
        self.hw.powerLed("warn")
        if self.hw.config.upAndDownUvOn:
            self.hw.uvLed(True)

        self.state = ExposureState.GOING_UP
        self.hw.setTowerProfile("homingFast")
        self.hw.towerToTop()
        while not self.hw.isTowerOnPosition():
            sleep(0.25)

        self.state = ExposureState.WAITING
        for sec in range(self.hw.config.upAndDownWait):
            cnt = self.hw.config.upAndDownWait - sec
            self.remaining_wait_sec = cnt
            sleep(1)
            if self.hw.config.coverCheck and not self.hw.isCoverClosed():
                self.state = ExposureState.COVER_OPEN
                while not self.hw.isCoverClosed():
                    sleep(1)
                self.state = ExposureState.WAITING

        if self.hw.config.tilt:
            self.state = ExposureState.STIRRING
            self.hw.tilt.stir_resin(self._tilt_speed)

        self.state = ExposureState.GOING_DOWN
        position = self.hw.config.upAndDownZoffset
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

    def _wait_uv_cool_down(self) -> Optional[str]:
        if not self.hw.uv_led_overheat:
            return None

        self.logger.error("UV LED overheat - waiting for cooldown")
        state = self.state
        self.state = ExposureState.COOLING_DOWN
        while True:
            try:
                if self.commands.get_nowait() == "exit":
                    return "exit"
            except Empty:
                pass
            if not self.hw.uv_led_overheat:
                break
            self.hw.beepAlarm(3)
            sleep(3)
        self.state = state
        return None

    def doStuckRelease(self):
        self.state = ExposureState.STUCK
        self.hw.powerLed("error")
        self.hw.towerHoldTiltRelease()
        if self.doWait(True) == "back":
            raise TiltFailed()

        self.hw.powerLed("warn")
        self.state = ExposureState.STUCK_RECOVERY
        self.hw.tilt.sync_wait()
        self.state = ExposureState.STIRRING
        self.hw.tilt.stir_resin(self._tilt_speed)
        self.hw.powerLed("normal")
        self.state = ExposureState.PRINTING

    def run(self):
        try:
            self.logger.info("Started exposure thread")
            self.logger.info("Motion controller tilt profiles: %s", self.hw.tilt.profiles)
            self.logger.info("Printer tune tilt profiles: %s", self.hw.config.tuneTilt)

            while not self.done:
                command = self.commands.get()
                if command == "exit":
                    self.hw.check_cover_override = False
                    self.logger.info("Exiting exposure thread on exit command")
                    if self.canceled:
                        self.state = ExposureState.CANCELED
                    break

                if command == "pour_resin_in":
                    self.hw.check_cover_override = True
                    asyncio.run(self._home_axis())
                    self.state = ExposureState.POUR_IN_RESIN
                    continue

                if command == "checks":
                    self.hw.check_cover_override = False
                    asyncio.run(self._run_checks())
                    self.run_exposure()
                    continue

                self.logger.error('Undefined command: "%s" ignored', command)

            self.logger.info("Exiting exposure thread on state: %s", self.state)
        except (Exception, CancelledError) as exception:
            self.logger.exception("Exposure thread exception")
            if not isinstance(exception, CancelledError):
                self.fatal_error = exception
            if not isinstance(exception, (TiltFailed, TowerFailed)):
                try:
                    self._final_go_up()
                except TowerHomeFailed:
                    self.logger.warning("Suppressing exception TowerHomeFailed cauth while processing another exception: %s", exception.__class__.__name__)
            if isinstance(exception, (WarningEscalation, CancelledError)):
                self.state = ExposureState.CANCELED
            else:
                self.state = ExposureState.FAILURE

        if self.project:
            self.project.data_close()
        self._print_end_hw_off()

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

    async def _home_axis(self):
        if not self.hw.towerSynced or not self.hw.tilt.synced:
            self.state = ExposureState.HOMING_AXIS
            self.logger.info("Homing axis to pour resin")
            await asyncio.gather(self.hw.verify_tower(), self.hw.verify_tilt())

    async def _run_checks(self):
        self._checks_task = asyncio.create_task(self._run_checks_task())
        await self._checks_task

    async def _run_checks_task(self):
        self.state = ExposureState.CHECKS
        self.logger.info("Running pre-print checks")
        for check in ExposureCheck:
            self.check_results.update({check: ExposureCheckResult.SCHEDULED})

        await asyncio.gather(
            FansCheck(self).start(),
            TempsCheck(self).start(),
            ProjectDataCheck(self).start()
            )
        await CoverCheck(self).start()
        await ResinCheck(self).start()
        await StartPositionsCheck(self).start()
        await StirringCheck(self).start()

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
                exposure_compensation = self.hw.config.upAndDownExpoComp * 100

            if command == "exit":
                break

            if command == "inject_tower_fail":
                self.logger.error("Injecting fatal tower fail")
                raise TowerFailed()

            if command == "pause":
                if self.doWait(False) == "exit":
                    break

            if self._wait_uv_cool_down() == "exit":
                break

            if self.resin_volume:
                self._update_resin()

            if command == "feedme" or self.low_resin:
                self.hw.powerLed("warn")
                if self.hw.config.tilt:
                    self.hw.tilt.layer_up_wait(self._tilt_speed)
                self.state = ExposureState.FEED_ME
                sub_command = self.doWait(self.low_resin)

                if sub_command == "continue":
                    # update resin volume
                    self.setResinVolume(defines.resinMaxVolume)

                # Force user to close the cover
                self._wait_cover_close()

                # Stir resin before resuming print
                if self.hw.config.tilt:
                    self.state = ExposureState.STIRRING
                    self.hw.tilt.sync_wait()
                    self.hw.tilt.stir_resin(self._tilt_speed)
                was_stirring = True

                # Resume print
                self.hw.powerLed("normal")
                self.state = ExposureState.PRINTING

            if (
                self.hw.config.upAndDownEveryLayer
                and self.actual_layer
                and not self.actual_layer % self.hw.config.upAndDownEveryLayer
            ):
                self.doUpAndDown()
                was_stirring = True
                exposure_compensation = self.hw.config.upAndDownExpoComp * 100

            layer = project.layers[self.actual_layer]

            self.tower_position_nm += layer.height_nm

            self.logger.info(
                "Layer started » {"
                " 'layer': '%04d/%04d (%s)',"
                " 'exposure [ms]': %s,"
                " 'slow_layers_done': %d,"
                " 'super_slow_layers_done': %d,"
                " 'height [mm]': '%.3f/%.3f',"
                " 'elapsed [min]': %d,"
                " 'remain [ms]': %d,"
                " 'used [ml]': %d,"
                " 'remaining [ml]': %d,"
                " 'RAM': '%.1f%%',"
                " 'CPU': '%.1f%%'"
                " 'tilt_speed: %s'"
                " }",
                self.actual_layer + 1,
                project.total_layers,
                layer.image.replace(project.name, project_hash),
                str(layer.times_ms),
                self.slow_layers_done,
                self.super_slow_layers_done,
                self.tower_position_nm / 1e6,
                project.total_height_nm / 1e6,
                int(round((datetime.now(tz=timezone.utc) - self.printStartTime).total_seconds() / 60)),
                self.estimate_remain_time_ms(),
                self.resin_count,
                self.remain_resin_ml if self.remain_resin_ml else -1,
                psutil.virtual_memory().percent,
                psutil.cpu_percent(),
                self._tilt_speed.name
            )

            times_ms = list(layer.times_ms)
            times_ms[0] += exposure_compensation

            success, white_pixels = self._do_frame(times_ms, was_stirring, False, layer.height_nm)
            if not success:
                self.doStuckRelease()
                self.hw.powerLed("normal")

            # exposure of the second part
            if project.per_partes and white_pixels > self.hw.white_pixels_threshold:
                success, dummy = self._do_frame(times_ms, was_stirring, True, layer.height_nm)
                if not success:
                    self.doStuckRelease()

            was_stirring = False
            exposure_compensation = 0

            # /1e21 (1e7 ** 3) - we want cm3 (=ml) not nm3
            self.resin_count += (
                white_pixels * self.hw.exposure_screen.parameters.pixel_size_nm ** 2 * layer.height_nm / 1e21
            )
            self.logger.debug("resin_count: %f", self.resin_count)

            seconds = (datetime.now(tz=timezone.utc) - self.printStartTime).total_seconds()

            if self.hw.config.trigger:
                self.logger.error("Trigger not implemented")
                # sleep(self.hw.config.trigger / 10.0)

            self.actual_layer += 1

        self._final_go_up()

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
            self.hw.config.autoOff,
            self.actual_layer,
            project.total_layers,
            seconds,
            self.resin_count,
            self.remain_resin_ml if self.remain_resin_ml else -1,
            exposure_times,
            self.tower_position_nm / 1e6,
        )

        self.exposure_image.save_display_usage()

        if self.canceled:
            self.state = ExposureState.CANCELED
        else:
            self.state = ExposureState.FINISHED

        self._print_end_hw_off()
        self.write_last_exposure()

        if not self.canceled:
            if self.hw.config.autoOff:
                shut_down(self.hw)

        self.logger.debug("Exposure ended")

    def _update_resin(self):
        self.remain_resin_ml = self.resin_volume - int(self.resin_count)
        self.warn_resin = self.remain_resin_ml < defines.resinLowWarn
        self.low_resin = self.remain_resin_ml < defines.resinFeedWait

    def _wait_cover_close(self) -> bool:
        """
        Waits for cover close

        :return: True if was waiting false otherwise
        """
        if not self.hw.config.coverCheck:
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
        self.hw.motorsStop()
        self.hw.setTowerProfile("homingFast")
        self.hw.towerToTop()
        while not self.hw.isTowerOnPosition():
            sleep(0.25)

    def _print_end_hw_off(self):
        self.hw.uvLed(False)
        self.hw.stopFans()
        self.hw.motorsRelease()
        self.hw.uvDisplayCounter(False)
        self.hw.saveUvStatistics()
        self.printEndTime = datetime.now(tz=timezone.utc)

    def _on_fans_error(self, fans_error: Dict[str, bool]):
        if any(fans_error.values()):
            self.warning_occurred.emit(ExpectOverheating(failed_fans_text=self.hw.getFansErrorText()))

    def inject_fatal_error(self):
        self.logger.info("Scheduling exception inject")
        self.commands.put("inject_tower_fail")

    def inject_exception(self, code: str):
        exception = tests.get_instance_by_code(code)
        self.logger.info("Injecting exception %s", exception)
        self.warning_occurred.emit(exception)
