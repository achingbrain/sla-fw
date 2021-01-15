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

import os
import glob
import asyncio
import concurrent.futures
import logging
import pickle
import queue
import threading
from hashlib import md5
from logging import Logger
from pathlib import Path
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Optional, Any
from threading import Event

from zipfile import ZipFile
import psutil
from PySignal import Signal
from deprecation import deprecated

from sl1fw import defines, test_runtime
from sl1fw.errors.errors import ExposureError, TiltFailed, TowerFailed, TowerMoveFailed, \
    TempSensorFailed, FanFailed, ResinFailed, ResinTooLow, ResinTooHigh, WarningEscalation
from sl1fw.errors.warnings import AmbientTooHot, AmbientTooCold, ResinNotEnough
from sl1fw.errors.exceptions import NotAvailableInState
from sl1fw.functions.system import shut_down
from sl1fw.configs.hw import HwConfig
from sl1fw.configs.stats import TomlConfigStats
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.configs.project import ProjectConfig
from sl1fw.libHardware import Hardware
from sl1fw.screen.screen import Screen
from sl1fw.project.functions import check_ready_to_print
from sl1fw.project.project import Project
from sl1fw.states.exposure import ExposureState, ExposureCheck, ExposureCheckResult
from sl1fw.utils.traceable_collections import TraceableList, TraceableDict


class ExposurePickler(pickle.Pickler):

    def __init__(self, file):
        super().__init__(file)
        self.IGNORED_CLASSES = [Signal, Hardware, Screen, ExposureThread, TraceableDict, TraceableList, queue.Queue, ZipFile]

    def persistent_id(self, obj):
        # pylint: disable = unidiomatic-typecheck
        if type(obj) in self.IGNORED_CLASSES:
            return "ignore"
        if isinstance(obj, HwConfig):
            obj.write(Path(defines.lastProjectHwConfig))
            obj.write_factory(Path(defines.lastProjectFactoryFile))
            return "HwConfig"
        if isinstance(obj, ProjectConfig):
            obj.write(Path(defines.lastProjectConfigFile))
            return "ProjectConfig"
        return None


class ExposureUnpickler(pickle.Unpickler):

    def persistent_load(self, pid):
        if pid == "ignore":
            return None
        if pid == "HwConfig":
            hwConfig = HwConfig(file_path=Path(defines.lastProjectHwConfig),
                                  factory_file_path=Path(defines.lastProjectFactoryFile),
                                  is_master=False)
            hwConfig.read_file()
            return hwConfig
        if pid == "ProjectConfig":
            projectConfig = ProjectConfig()
            projectConfig.read_file(file_path= Path(defines.lastProjectConfigFile))
            return projectConfig
        raise pickle.UnpicklingError(f'unsupported persistent object {str(pid)}')


class ExposureThread(threading.Thread):

    def __init__(self, commands: queue.Queue, expo: Exposure):
        super(ExposureThread, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.expo = expo
        self.warning_dismissed = Event()
        self.warning_result: Optional[Exception] = None
        self._pending_warning = threading.Lock()

    def _do_frame(self, times_ms, prev_white_pixels, was_stirring, second):
        position_steps = self.expo.hwConfig.nm_to_tower_microsteps(self.expo.tower_position_nm) + self.expo.hwConfig.calibTowerOffset

        if self.expo.hwConfig.tilt:
            if self.expo.hwConfig.layerTowerHop and prev_white_pixels > self.expo.screen.white_pixels_threshold:
                self.expo.hw.towerMoveAbsoluteWait(position_steps + self.expo.hwConfig.layerTowerHop)
                self.expo.hw.tiltLayerUpWait()
                self.expo.hw.towerMoveAbsoluteWait(position_steps)
            else:
                self.expo.hw.towerMoveAbsoluteWait(position_steps)
                self.expo.hw.tiltLayerUpWait()
        else:
            self.expo.hw.towerMoveAbsoluteWait(position_steps + self.expo.hwConfig.layerTowerHop)
            self.expo.hw.towerMoveAbsoluteWait(position_steps)
        self.expo.hw.setTowerCurrent(defines.towerHoldCurrent)

        white_pixels = self.expo.screen.sync_preloader()
        self.expo.screen.screenshot_rename(second)

        if self.expo.hwConfig.delayBeforeExposure:
            self.logger.info("delayBeforeExposure [s]: %f", self.expo.hwConfig.delayBeforeExposure / 10.0)
            sleep(self.expo.hwConfig.delayBeforeExposure / 10.0)

        if was_stirring:
            self.logger.info("stirringDelay [s]: %f", self.expo.hwConfig.stirringDelay / 10.0)
            sleep(self.expo.hwConfig.stirringDelay / 10.0)

        # FIXME WTF?
        if self.expo.hwConfig.tilt:
            self.expo.hw.getMcTemperatures()

        self.expo.screen.blit_image(second)

        exp_time_ms = sum(times_ms)
        self.expo.exposure_end = datetime.now(tz=timezone.utc) + timedelta(seconds=exp_time_ms / 1e3)
        self.logger.info("Exposure started: %d ms, end: %s", exp_time_ms, self.expo.exposure_end)

        i = 0
        for time_ms in times_ms:
            uv_on_remain_ms = time_ms
            if self.expo.hwConfig.blinkExposure:
                uv_is_on = True
                self.logger.debug("uv on")
                self.expo.hw.uvLed(True, time_ms)
                while uv_is_on:
                    sleep(uv_on_remain_ms / 1100.0)
                    uv_is_on, uv_on_remain_ms = self.expo.hw.getUvLedState()
            else:
                sleep(time_ms / 1e3)
            self.expo.screen.fill_area(i)
            i += 1

        self.expo.screen.blank_screen()
        self.logger.info("exposure done")
        self.expo.screen.preload_image(self.expo.actual_layer + 1)

        temperatures = self.expo.hw.getMcTemperatures()
        self.logger.info("UV temperature [C]: %.1f  Ambient temperature [C]: %.1f", temperatures[0], temperatures[1])

        if self.expo.hwConfig.delayAfterExposure:
            self.logger.info("delayAfterExposure [s]: %f", self.expo.hwConfig.delayAfterExposure / 10.0)
            sleep(self.expo.hwConfig.delayAfterExposure / 10.0)

        if self.expo.hwConfig.tilt:
            slow_move = white_pixels > self.expo.screen.white_pixels_threshold
            if slow_move:
                self.expo.slow_layers_done += 1
            if not self.expo.hw.tiltLayerDownWait(slow_move):
                return False, white_pixels

        return True, white_pixels


    def doUpAndDown(self):
        self.expo.hw.powerLed("warn")
        if self.expo.hwConfig.blinkExposure and self.expo.hwConfig.upAndDownUvOn:
            self.expo.hw.uvLed(True)

        self.expo.state = ExposureState.GOING_UP
        self.expo.hw.setTowerProfile('homingFast')
        self.expo.hw.towerToTop()
        while not self.expo.hw.isTowerOnTop():
            sleep(0.25)

        self.expo.state = ExposureState.WAITING
        for sec in range(self.expo.hwConfig.upAndDownWait):
            cnt = self.expo.hwConfig.upAndDownWait - sec
            self.expo.remaining_wait_sec = cnt
            sleep(1)
            if self.expo.hwConfig.coverCheck and not self.expo.hw.isCoverClosed():
                self.expo.state = ExposureState.COVER_OPEN
                while not self.expo.hw.isCoverClosed():
                    sleep(1)
                self.expo.state = ExposureState.WAITING

        if self.expo.hwConfig.tilt:
            self.expo.state = ExposureState.STIRRING
            self.expo.hw.stirResin()

        self.expo.state = ExposureState.GOING_DOWN
        self.expo.position += self.expo.hwConfig.upAndDownZoffset
        if self.expo.position < 0:
            self.expo.position = 0
        self.expo.hw.towerMoveAbsolute(self.expo.position)
        while not self.expo.hw.isTowerOnPosition():
            sleep(0.25)
        self.expo.hw.setTowerProfile('layer')
        self.expo.hw.powerLed("normal")

        self.expo.state = ExposureState.PRINTING


    def doWait(self, beep = False):
        command = None
        breakFree = {"exit", "back", "continue"}
        while not command:
            if beep:
                self.expo.hw.beepAlarm(3)
            sleep(1)

            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                command = None
            except Exception:
                self.logger.exception("getCommand exception")
                command = None

            if command in breakFree:
                break

        return command


    def doStuckRelease(self):
        self.expo.state = ExposureState.STUCK
        self.expo.hw.powerLed("error")
        self.expo.hw.towerHoldTiltRelease()
        if self.doWait(True) == "back":
            raise TiltFailed()

        self.expo.hw.powerLed("warn")
        self.expo.state = ExposureState.STUCK_RECOVERY

        if not self.expo.hw.tiltSyncWait(retries = 1):
            self.logger.error("Stuck release failed")
            raise TiltFailed()

        self.expo.state = ExposureState.STIRRING
        self.expo.hw.stirResin()
        self.expo.hw.powerLed("normal")
        self.expo.state = ExposureState.PRINTING


    def run(self):
        try:
            self.logger.info("Started exposure thread")

            while not self.expo.done:
                command = self.commands.get()
                if command == "exit":
                    self.logger.info("Exiting exposure thread on exit command")
                    break

                if command == "checks":
                    asyncio.run(self._run_checks())
                    self.run_exposure()
                else:
                    self.logger.error("Undefined command: \"%s\" ignored", command)

            self.logger.info("Exiting exposure thread on state: %s", self.expo.state)
        except Exception as exception:
            self.logger.exception("Exposure thread exception")
            self.expo.exception = exception
            self.expo.state = ExposureState.FAILURE
            self.expo.hw.uvLed(False)
            self.expo.hw.stopFans()
            self.expo.hw.motorsRelease()
        if self.expo.project:
            self.expo.project.data_close()

    def _raise_preprint_warning(self, warning: Warning):
        self.logger.warning("Warning being raised in pre-print: %s", type(warning))
        with self._pending_warning:
            self.warning_result = None
            self.expo.warning = warning
            old_state = self.expo.state
            self.expo.state = ExposureState.CHECK_WARNING
            self.warning_dismissed.clear()
            self.logger.debug("Waiting for warning resolution")
            self.warning_dismissed.wait()
            self.logger.debug("Warnings resolved")
            self.expo.warning = None
            self.expo.state = old_state
            if self.warning_result:
                raise self.warning_result

    async def _run_checks(self):
        self.expo.state = ExposureState.CHECKS
        self.logger.info("Running pre-print checks")
        self.expo.check_results.update({check: ExposureCheckResult.SCHEDULED for check in ExposureCheck})

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            fans = loop.run_in_executor(pool, self._check_fans)
            temps = loop.run_in_executor(pool, self._check_temps)
            project = loop.run_in_executor(pool, self._check_project_data)
            hw = asyncio.create_task(self._check_hw_related())

            self.logger.debug("Waiting for pre-print checks to finish")
            await asyncio.gather(
                fans, temps, project, hw
            )

    async def _check_hw_related(self):
        if test_runtime.injected_preprint_warning:
            self._raise_preprint_warning(test_runtime.injected_preprint_warning)

        if not self.expo.hwConfig.resinSensor:
            self.logger.info("Disabling resin check")
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.DISABLED

        if not self.expo.hwConfig.tilt:
            self.logger.info("Disabling stirring")
            self.expo.check_results[ExposureCheck.STIRRING] = ExposureCheckResult.DISABLED

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, self._check_cover_closed)
            await loop.run_in_executor(pool, self._check_hardware)
            if self.expo.hwConfig.resinSensor:
                await loop.run_in_executor(pool, self._check_resin)
            await loop.run_in_executor(pool, self._check_start_positions)
            await loop.run_in_executor(pool, self._check_resin_stirring)


    def _check_cover_closed(self):
        self.expo.check_results[ExposureCheck.COVER] = ExposureCheckResult.RUNNING
        if not self.expo.hwConfig.coverCheck:
            self.logger.info("Disabling cover check")
            self.expo.check_results[ExposureCheck.COVER] = ExposureCheckResult.DISABLED
            return

        self.logger.info("Waiting for user to close the cover")
        with self._pending_warning:
            while True:
                if self.expo.hw.isCoverClosed():
                    self.expo.state = ExposureState.CHECKS
                    self.expo.check_results[ExposureCheck.COVER] = ExposureCheckResult.SUCCESS
                    self.logger.info("Cover closed")
                    return

                self.expo.state = ExposureState.COVER_OPEN
                sleep(0.1)


    def _check_temps(self):
        self.logger.info("Running temperature checks")
        self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.RUNNING
        temperatures = self.expo.hw.getMcTemperatures()
        failed = [i for i in range(2) if temperatures[i] < 0]
        if failed:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.FAILURE
            failed_names = [self.expo.hw.getSensorName(i) for i in failed]
            raise TempSensorFailed(failed, failed_names)

        if temperatures[1] < defines.minAmbientTemp:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.WARNING
            self._raise_preprint_warning(AmbientTooCold(temperatures[1]))
        elif temperatures[1] > defines.maxAmbientTemp:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.WARNING
            self._raise_preprint_warning(AmbientTooHot(temperatures[1]))
        else:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.SUCCESS


    def _check_project_data(self):
        self.logger.info("Running project checks")
        self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.RUNNING

        # Remove old projects
        self.logger.debug("Running disk cleanup")
        self.expo.check_and_clean_last_data()

        self.logger.debug("Running project copy and check")
        try:
            self.expo.project.copy_and_check()
        except Exception:
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.FAILURE
            raise

        self.logger.info("Project after copy and check: %s", str(self.expo.project))

        # start data preparation by Screen
        self.logger.debug("Initiating project in Screen")
        try:
            self.expo.startProject()
        except Exception:
            self.logger.error("Initiating project in Screen failed")
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.FAILURE
            raise

        # show all warnings
        if self.expo.project.warnings:
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.WARNING
            for warning in self.expo.project.warnings:
                self._raise_preprint_warning(warning)
        else:
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.SUCCESS


    def _check_hardware(self):
        self.logger.info("Running start positions hardware checks")
        self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.RUNNING

        self.logger.info("Syncing tower")
        self.expo.hw.towerSyncWait()
        if not self.expo.hw.isTowerSynced():
            self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.FAILURE
            raise TowerFailed()

        self.logger.info("Syncing tilt")
        self.expo.hw.tiltSyncWait()

        if not self.expo.hw.isTiltSynced():
            self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.FAILURE
            raise TiltFailed()

        self.logger.info("Tilting up")
        self.expo.hw.setTiltProfile('homingFast')
        self.expo.hw.tiltUp()
        while self.expo.hw.isTiltMoving():
            sleep(0.1)
        if not self.expo.hw.isTiltOnPosition():
            self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.FAILURE
            raise TiltFailed()

        self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.SUCCESS


    def _check_fans(self):
        self.logger.info("Running fan checks")
        self.expo.check_results[ExposureCheck.FAN] = ExposureCheckResult.RUNNING

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
        self.expo.check_results[ExposureCheck.FAN] = ExposureCheckResult.SUCCESS


    def _check_resin(self):
        self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.RUNNING

        self.logger.info("Running resin measurement")

        volume = self.expo.hw.getResinVolume()
        self.expo.setResinVolume(volume)

        try:
            if not volume:
                raise ResinFailed(volume)

            if volume < defines.resinMinVolume:
                raise ResinTooLow(volume, defines.resinMinVolume)

            if volume > defines.resinMaxVolume:
                raise ResinTooHigh(volume)
        except ResinFailed:
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.FAILURE
            self.expo.hw.setTowerProfile('homingFast')
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)
            raise

        self.logger.debug("min: %d [ml], requested: %d [ml], measured: %d [ml]",
                          defines.resinMinVolume, self.expo.project.used_material + defines.resinMinVolume, volume)

        if volume < self.expo.project.used_material + defines.resinMinVolume:
            self.logger.info("Raising resin not enough warning")
            self._raise_preprint_warning(
                ResinNotEnough(volume, self.expo.project.used_material + defines.resinMinVolume))
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.WARNING

        self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.SUCCESS


    def _check_start_positions(self):
        self.expo.check_results[ExposureCheck.START_POSITIONS] = ExposureCheckResult.RUNNING

        self.logger.info("Prepare tank and resin")
        if self.expo.hwConfig.tilt:
            self.logger.info("Tilting down")
            self.expo.hw.tiltDownWait()

        self.logger.info("Tower to print start position")
        self.expo.hw.setTowerProfile('homingFast')
        self.expo.hw.towerToPosition(0.25)  # TODO: Constant in code, seems important
        while not self.expo.hw.isTowerOnPosition(retries=2):
            sleep(0.25)

        if self.expo.hw.towerPositonFailed():
            self.expo.check_results[ExposureCheck.START_POSITIONS] = ExposureCheckResult.FAILURE
            exception = TowerMoveFailed()
            self.expo.exception = exception
            self.expo.hw.setTowerProfile('homingFast')
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)

            raise exception

        self.expo.check_results[ExposureCheck.START_POSITIONS] = ExposureCheckResult.SUCCESS


    def _check_resin_stirring(self):
        self.expo.check_results[ExposureCheck.STIRRING] = ExposureCheckResult.RUNNING
        if self.expo.hwConfig.tilt:
            self.expo.hw.stirResin()
            self.expo.check_results[ExposureCheck.STIRRING] = ExposureCheckResult.SUCCESS


    def run_exposure(self):
        # TODO: Where is this supposed to be called from?
        self.expo.prepare()

        self.logger.info("Running exposure")
        self.expo.state = ExposureState.PRINTING
        self.expo.printStartTime = datetime.now(tz=timezone.utc)
        statistics = TomlConfigStats(defines.statsData, self.expo.hw)
        statistics.load()
        statistics['started_projects'] += 1
        statistics.save_raw()
        seconds = 0

        project = self.expo.project
        project_hash = md5(project.name.encode()).hexdigest()[:8] + "_"
        prev_white_pixels = 0
        stuck = False
        was_stirring = True
        exposure_compensation = 0

        while self.expo.actual_layer < project.total_layers:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                command = None
            except Exception:
                self.logger.exception("getCommand exception")
                command = None

            if command == "updown":
                self.doUpAndDown()
                was_stirring = True
                exposure_compensation = self.expo.hwConfig.upAndDownExpoComp * 100

            if command == "exit":
                break

            if command == "pause":
                if not self.expo.hwConfig.blinkExposure:
                    self.expo.hw.uvLed(False)

                if self.doWait(False) == "exit":
                    break

                if not self.expo.hwConfig.blinkExposure:
                    self.expo.hw.uvLed(True)

            if self.expo.resin_volume:
                self.expo.remain_resin_ml = self.expo.resin_volume - int(self.expo.resin_count)
                self.expo.warn_resin = self.expo.remain_resin_ml < defines.resinLowWarn
                self.expo.low_resin = self.expo.remain_resin_ml < defines.resinFeedWait

            if command == "feedme" or self.expo.low_resin:
                self.expo.hw.powerLed("warn")
                if self.expo.hwConfig.tilt:
                    self.expo.hw.tiltLayerUpWait()
                self.expo.state = ExposureState.FEED_ME
                self.doWait(self.expo.low_resin)

                # Force user to close the cover
                self._wait_cover_close()

                # Stir resin before resuming print
                if self.expo.hwConfig.tilt:
                    self.expo.state = ExposureState.STIRRING
                    self.expo.hw.setTiltProfile('homingFast')
                    self.expo.hw.tiltDownWait()
                    self.expo.hw.stirResin()
                was_stirring = True

                # Resume print
                self.expo.hw.powerLed("normal")
                self.expo.state = ExposureState.PRINTING

            if self.expo.hwConfig.upAndDownEveryLayer and self.expo.actual_layer and not self.expo.actual_layer % self.expo.hwConfig.upAndDownEveryLayer:
                self.doUpAndDown()
                was_stirring = True
                exposure_compensation = self.expo.hwConfig.upAndDownExpoComp * 100

            layer = project.layers[self.expo.actual_layer]

            self.expo.tower_position_nm += layer.height_nm

            self.logger.info(
                "Layer started » { 'layer': '%04d/%04d (%s)', 'exposure [ms]': %s, 'slow_layers_done': %d, 'height [mm]': '%.3f/%.3f', "
                "'elapsed [min]': %d, 'remain [min]': %d, 'used [ml]': %d, 'remaining [ml]': %d, 'RAM': '%.1f%%', 'CPU': '%.1f%%' }",
                self.expo.actual_layer + 1,
                project.total_layers,
                layer.image.replace(project.name, project_hash),
                str(layer.times_ms),
                self.expo.slow_layers_done,
                self.expo.tower_position_nm / 1e6,
                project.total_height_nm / 1e6,
                int(round((datetime.now(tz=timezone.utc) - self.expo.printStartTime).total_seconds() / 60)),
                self.expo.countRemainTime(),
                self.expo.resin_count,
                self.expo.remain_resin_ml if self.expo.remain_resin_ml else -1,
                psutil.virtual_memory().percent,
                psutil.cpu_percent(),
            )

            times_ms = layer.times_ms.copy()
            times_ms[0] += exposure_compensation

            success, white_pixels = self._do_frame(times_ms, prev_white_pixels, was_stirring, False)
            if not success and not self.doStuckRelease():
                self.expo.hw.powerLed("normal")
                self.expo.cancel()
                stuck = True
                break

            # exposure of the second part
            if project.per_partes and white_pixels > self.expo.screen.white_pixels_threshold:
                success, dummy = self._do_frame(times_ms, white_pixels, was_stirring, True)
                if not success and not self.doStuckRelease():
                    stuck = True
                    break

            prev_white_pixels = white_pixels
            was_stirring = False
            exposure_compensation = 0

            # /1e21 (1e7 ** 3) - we want cm3 (=ml) not nm3
            self.expo.resin_count += white_pixels * self.expo.screen.printer_model.exposure_screen.pixel_size_nm ** 2 * layer.height_nm / 1e21
            self.logger.debug("resin_count: %f", self.expo.resin_count)

            seconds = (datetime.now(tz=timezone.utc) - self.expo.printStartTime).total_seconds()
            self.expo.printTime = int(seconds / 60) # TODO property

            if self.expo.hwConfig.trigger:
                self.expo.hw.cameraLed(True)
                sleep(self.expo.hwConfig.trigger / 10.0)
                self.expo.hw.cameraLed(False)

            self.expo.actual_layer += 1

        self.expo.hw.saveUvStatistics()
        self.expo.hw.uvLed(False)

        if not stuck:
            self.expo.state = ExposureState.GOING_UP
            self.expo.hw.setTowerProfile('homingFast')
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)

        self.expo.hw.stopFans()
        self.expo.hw.motorsRelease()

        self.expo.printEndTime = datetime.now(tz=timezone.utc)

        is_finished = not self.expo.canceled
        if is_finished:
            statistics['finished_projects'] += 1
        statistics['layers'] += self.expo.actual_layer
        statistics['total_seconds'] += seconds
        statistics['total_resin'] += self.expo.resin_count
        statistics.save_raw()
        exposure_times = "{0:d}/{1:d}/{2:d} s".format(
            project.exposure_time_first_ms,
            project.exposure_time_ms,
            project.exposure_time_calibrate_ms
        )
        self.logger.info(
            "Job finished » { 'job': %d, 'project': '%s', 'finished': %s, "
            "'autoOff': %s, 'Layers': '%d/%d', 'printTime [s]': %d, "
            "'used [ml]': %g, 'remaining [ml]': %g, 'exposure [s]': '%s', 'height [mm]': %g, }",
            statistics['started_projects'],
            project_hash[:-1],
            is_finished,
            self.expo.hwConfig.autoOff,
            self.expo.actual_layer,
            project.total_layers,
            seconds,
            self.expo.resin_count,
            self.expo.remain_resin_ml if self.expo.remain_resin_ml else -1,
            exposure_times,
            self.expo.tower_position_nm / 1e6
        )

        self.expo.screen.save_display_usage()

        if self.expo.canceled:
            self.expo.state = ExposureState.CANCELED
        else:
            self.expo.state = ExposureState.FINISHED

        self.expo.write_last_exposure()

        if not self.expo.canceled:
            if self.expo.hwConfig.autoOff:
                shut_down(self.expo.hw)

        self.logger.debug("Exposure ended")

    def _wait_cover_close(self) -> bool:
        """
        Waits for cover close

        :return: True if was waiting false otherwise
        """
        if not self.expo.hwConfig.coverCheck:
            return False

        if self.expo.hw.isCoverClosed():
            self.logger.info("Cover already closed skipping close wait")
            return False

        self.logger.info("Waiting for user to close the cover")
        old_state = self.expo.state
        while not self.expo.hw.isCoverClosed():
            self.expo.state = ExposureState.COVER_OPEN
            sleep(0.1)
        self.expo.state = old_state
        self.logger.info("Cover closed now")
        return True


class Exposure:
    def __init__(self, job_id: int, hwConfig: HwConfig, hw: Hardware, screen: Screen, runtime_config: RuntimeConfig,
                 project_file: str):
        check_ready_to_print(hwConfig, screen.printer_model.calibration(hw.is500khz))
        self.change = Signal()
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.runtime_config = runtime_config
        self.project: Optional[Project] = None
        self.hw = hw
        self.screen = screen
        self.resin_count = 0.0
        self.resin_volume = None
        self.expoThread: Optional[threading.Thread] = None
        self.zipName = None
        self.tower_position_nm = 0
        self.actual_layer = 0
        self.slow_layers_done = 0
        self.printStartTime = datetime.fromtimestamp(0, tz=timezone.utc)
        self.printEndTime = datetime.fromtimestamp(0, tz=timezone.utc)
        self.printTime = 0
        self.state = ExposureState.READING_DATA
        self.remaining_wait_sec = 0
        self.low_resin = False
        self.warn_resin = False
        self.remain_resin_ml: Optional[float] = None
        self.exposure_end: Optional[datetime] = None
        self.instance_id = job_id
        self.check_results = TraceableDict()
        self.check_results.changed.connect(lambda: self.change.emit("check_results", self.check_results))
        self.exception: Optional[ExposureError] = None
        self.warning: Optional[Warning] = None
        self.canceled = False
        self.expoCommands = queue.Queue()
        self.expoThread = ExposureThread(self.expoCommands, self)

        try:
            # Read project
            self.project = Project(self.hwConfig, self.screen.printer_model, project_file)
            self.state = ExposureState.CONFIRM
            # Signal project change on its parameter change. This lets Exposure0 emit
            # property changed on properties bound to project parameters.
            self.project.params_changed.connect(lambda: self.change.emit("project", None))
        except Exception as exception:
            # TODO: It is not nice to handle this in the constructor, but still better than let the constructor raise
            # TODO: an exception and kill the whole printer logic.
            # TODO: Solution would be to move this to exposure thread, but we rely on project being loaded right after
            # TODO: the Exposure object is created.
            # FIXME: this exception is not send to frontend !!!
            self.logger.exception("Exposure init exception")
            self.exception = exception
            self.state = ExposureState.FAILURE
            self.hw.uvLed(False)
            self.hw.stopFans()
            self.hw.motorsRelease()
        self.logger.info("Created new exposure object id: %s", self.instance_id)

    def confirm_print_start(self):
        self.expoThread.start()
        self.expoCommands.put("checks")


    def confirm_print_warning(self):
        self.logger.info("User confirmed print check warnings")
        self.expoThread.warning_dismissed.set()


    def reject_print_warning(self):
        self.logger.info("User rejected print due to warnings")
        self.expoThread.warning_result = WarningEscalation(self.warning)
        self.expoThread.warning_dismissed.set()


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
        self.hw.setTowerProfile('layer')
        self.hw.towerMoveAbsoluteWait(0)  # first layer will move up

        self.screen.blank_screen()
        self.hw.uvLedPwm = self.hwConfig.uvPwm
        if not self.hwConfig.blinkExposure:
            self.hw.uvLed(True)


    @deprecated("Should be obsolete, use confirm print start instead")
    def start(self):
        if self.expoThread:
            self.expoThread.start()
        else:
            self.logger.error("Can't start exposure thread")


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
        self.expoCommands.put("updown")


    def doExitPrint(self):
        self.expoCommands.put("exit")


    def doFeedMe(self):
        self.state = ExposureState.PENDING_ACTION
        self.expoCommands.put("feedme")


    def doPause(self):
        self.expoCommands.put("pause")


    def doContinue(self):
        self.expoCommands.put("continue")


    def doBack(self):
        self.expoCommands.put("back")


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
        self.save()
        if self.canceled or not self.hwConfig.autoOff:
            Exposure.cleanup_last_data(self.logger)

    def save(self):
        self.logger.debug("Storing Exposure data")
        with open(defines.lastProjectPickler, 'wb') as pickle_io:
            ExposurePickler(pickle_io).dump(self)

    @staticmethod
    def load(logger: Logger, hw: Hardware) -> Optional[Exposure]:
        try:
            with open(defines.lastProjectPickler, 'rb') as pickle_io:
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
        clear_all = self.project.path and \
            not str(self.project.path).startswith(defines.previousPrints)
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
                defines.lastProjectPickler
            ]
        for project_file in files:
            logger.debug("removing '%s'", project_file)
            try:
                os.remove(project_file)
            except Exception:
                logger.exception("cleanup_last_data() exception:")

    def stats_seen(self):
        self.state = ExposureState.DONE
