# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=no-else-return
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
from logging import Logger
from pathlib import Path
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Optional, Any
from threading import Event

import psutil
from PySignal import Signal
from deprecation import deprecated

from sl1fw import defines, test_runtime
from sl1fw.errors.errors import ExposureError, TiltFailed, TowerFailed, TowerMoveFailed, ProjectFailed, \
    TempSensorFailed, FanFailed, ResinFailed, ResinTooLow, ResinTooHigh, WarningEscalation
from sl1fw.errors.warnings import AmbientTooHot, AmbientTooCold, PrintingDirectlyFromMedia, \
    ModelMismatch, ResinNotEnough, ProjectSettingsModified
from sl1fw.errors.exceptions import NotAvailableInState
from sl1fw.functions.system import shut_down
from sl1fw.libConfig import HwConfig, TomlConfigStats, RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen
from sl1fw.project.functions import check_ready_to_print
from sl1fw.project.project import Project, ProjectState, ProjectConfig
from sl1fw.states.exposure import ExposureState, ExposureCheck, ExposureCheckResult
from sl1fw.utils.traceable_collections import TraceableList, TraceableDict

class ExposurePickler(pickle.Pickler):

    def __init__(self, file):
        super().__init__(file)
        self.IGNORED_CLASSES = [Signal, Hardware, Screen, ExposureThread, TraceableDict, TraceableList, queue.Queue]

    def persistent_id(self, obj):
        # pylint: disable = unidiomatic-typecheck
        if type(obj) in self.IGNORED_CLASSES:
            return "ignore"
        elif isinstance(obj, HwConfig):
            obj.write(Path(defines.lastProjectHwConfig))
            obj.write_factory(Path(defines.lastProjectFactoryFile))
            return "HwConfig"
        elif isinstance(obj, ProjectConfig):
            obj.write(Path(defines.lastProjectConfigFile))
            return "ProjectConfig"
        else:
            return None

class ExposureUnpickler(pickle.Unpickler):

    def persistent_load(self, pid):
        if pid == "ignore":
            return None
        elif pid == "HwConfig":
            hwConfig = HwConfig(file_path=Path(defines.lastProjectHwConfig),
                                  factory_file_path=Path(defines.lastProjectFactoryFile),
                                  is_master=False)
            hwConfig.read_file()
            return hwConfig
        elif pid == "ProjectConfig":
            projectConfig = ProjectConfig()
            projectConfig.read_file(file_path= Path(defines.lastProjectConfigFile))
            return projectConfig
        else:
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
    #enddef


    def doFrame(self, picture, position, exposureTime, overlayName, prevWhitePixels, wasStirring, second):

        self.expo.screen.screenshot(second = second)

        if self.expo.hwConfig.tilt:
            if self.expo.hwConfig.layerTowerHop and prevWhitePixels > self.expo.hwConfig.whitePixelsThd:
                self.expo.hw.towerMoveAbsoluteWait(position + self.expo.hwConfig.layerTowerHop)
                self.expo.hw.tiltLayerUpWait()
                self.expo.hw.towerMoveAbsoluteWait(position)
            else:
                self.expo.hw.towerMoveAbsoluteWait(position)
                self.expo.hw.tiltLayerUpWait()
            #endif
        else:
            self.expo.hw.towerMoveAbsoluteWait(position + self.expo.hwConfig.layerTowerHop)
            self.expo.hw.towerMoveAbsoluteWait(position)
        #endif
        self.expo.hw.setTowerCurrent(defines.towerHoldCurrent)

        self.expo.screen.screenshotRename()

        if self.expo.hwConfig.delayBeforeExposure:
            sleep(self.expo.hwConfig.delayBeforeExposure / 10.0)
        #endif

        if wasStirring:
            sleep(self.expo.hwConfig.stirringDelay / 10.0)
        #endif

        calibAreas = self.expo.project.calibrateAreas

        if calibAreas:
            etime = exposureTime + calibAreas[-1]['time'] - calibAreas[0]['time']
        else:
            etime = exposureTime
        #endif
        if self.expo.hwConfig.tilt:
            self.expo.hw.getMcTemperatures()
        #endif

        whitePixels = self.expo.screen.blitImg(second = second)

        self.expo.exposure_end = datetime.now(tz=timezone.utc) + timedelta(seconds=etime)
        self.logger.info("Exposure started: %d seconds, end: %s", etime, self.expo.exposure_end)

        if self.expo.hwConfig.blinkExposure:
            if calibAreas:
                exptime = 1000 * (exposureTime + calibAreas[-1]['time'] - calibAreas[0]['time'])
                self.expo.hw.uvLed(True, exptime)
                UVIsOn = True

                for area in calibAreas:
                    while exptime > 1000 * (calibAreas[-1]['time'] - area['time']):
                        sleep(0.005)
                        UVIsOn, exptime = self.expo.hw.getUvLedState()
                        if not UVIsOn:
                            break
                        #endif
                    #endwhile

                    if not UVIsOn:
                        break
                    #endif

                    self.expo.screen.fillArea(area = area['rect'])
                    #self.logger.debug("blank area")
                #endfor
            else:
                self.expo.hw.uvLed(True, 1000 * exposureTime)
                UVIsOn = True
                while UVIsOn:
                    sleep(0.1)
                    UVIsOn, exptime = self.expo.hw.getUvLedState()
                #endwhile
            #endif
        else:
            sleep(exposureTime)
            if calibAreas:
                lastArea = calibAreas[0]
                for area in calibAreas[1:]:
                    self.expo.screen.fillArea(area = lastArea['rect'])
                    #self.logger.debug("blank area")
                    sleep(area['time'] - lastArea['time'])
                    lastArea = area
                #endfor
            #endif
        #endif

        self.expo.screen.getImgBlack()
        self.logger.info("exposure done")
        temperatures = self.expo.hw.getMcTemperatures()

        if picture is not None:
            self.expo.screen.preloadImg(
                    filename = picture,
                    overlayName = overlayName,
                    whitePixelsThd = self.expo.hwConfig.whitePixelsThd)
        #endif

        if self.expo.hwConfig.delayAfterExposure:
            sleep(self.expo.hwConfig.delayAfterExposure / 10.0)
        #endif

        if self.expo.hwConfig.tilt:
            slowMove = whitePixels > self.expo.hwConfig.whitePixelsThd
            if slowMove:
                self.expo.slowLayersDone += 1
            #endif
            if not self.expo.hw.tiltLayerDownWait(slowMove):
                return False, whitePixels, temperatures[0], temperatures[1]
            #endif
        #endif

        return True, whitePixels, temperatures[0], temperatures[1]
    #enddef


    def doUpAndDown(self):
        self.expo.hw.powerLed("warn")
        if self.expo.hwConfig.blinkExposure and self.expo.hwConfig.upAndDownUvOn:
            self.expo.hw.uvLed(True)
        #endif

        self.expo.state = ExposureState.GOING_UP
        self.expo.hw.setTowerProfile('homingFast')
        self.expo.hw.towerToTop()
        while not self.expo.hw.isTowerOnTop():
            sleep(0.25)
        #endwhile

        self.expo.state = ExposureState.WAITING
        for sec in range(self.expo.hwConfig.upAndDownWait):
            cnt = self.expo.hwConfig.upAndDownWait - sec
            self.expo.remaining_wait_sec = cnt
            sleep(1)
            if self.expo.hwConfig.coverCheck and not self.expo.hw.isCoverClosed():
                self.expo.state = ExposureState.COVER_OPEN
                while not self.expo.hw.isCoverClosed():
                    sleep(1)
                #endwhile
                self.expo.state = ExposureState.WAITING
            #endif
        #endfor

        if self.expo.hwConfig.tilt:
            self.expo.state = ExposureState.STIRRING
            self.expo.hw.stirResin()
        #endif

        self.expo.state = ExposureState.GOING_DOWN
        self.expo.position += self.expo.hwConfig.upAndDownZoffset
        if self.expo.position < 0:
            self.expo.position = 0
        #endif
        self.expo.hw.towerMoveAbsolute(self.expo.position)
        while not self.expo.hw.isTowerOnPosition():
            sleep(0.25)
        #endwhile
        self.expo.hw.setTowerProfile('layer')
        self.expo.hw.powerLed("normal")

        self.expo.state = ExposureState.PRINTING
    #endif


    def doWait(self, beep = False):
        command = None
        breakFree = {"exit", "back", "continue"}
        while not command:
            if beep:
                self.expo.hw.beepAlarm(3)
            #endif
            sleep(1)

            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                command = None
            except Exception:
                self.logger.exception("getCommand exception")
                command = None
            #endtry

            if command in breakFree:
                break
            #endif
        #endwhile

        return command
    #enddef


    def doStuckRelease(self):
        self.expo.state = ExposureState.STUCK
        self.expo.hw.powerLed("error")
        self.expo.hw.towerHoldTiltRelease()
        if self.doWait(True) == "back":
            raise TiltFailed()
        #endif

        self.expo.hw.powerLed("warn")
        self.expo.state = ExposureState.STUCK_RECOVERY

        if not self.expo.hw.tiltSyncWait(retries = 1):
            self.logger.error("Stuck release failed")
            raise TiltFailed()
        #endif

        self.expo.state = ExposureState.STIRRING
        self.expo.hw.stirResin()
        self.expo.hw.powerLed("normal")
        self.expo.state = ExposureState.PRINTING
    #enddef


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
                else:
                    self.logger.error("Undefined command: \"%s\" ignored", command)
                #endif
            #endwhile

            self.logger.info("Exiting exposure thread on state: %s", self.expo.state)
        except Exception as exception:
            self.logger.exception("Exposure thread exception")
            self.expo.exception = exception
            self.expo.state = ExposureState.FAILURE
            self.expo.hw.uvLed(False)
            self.expo.hw.stopFans()
            self.expo.hw.motorsRelease()
        #endtry
    #enddef

    def _raise_preprint_warning(self, warning: Warning):
        self.logger.warning("Warning being raised in pre-print: %s", warning)
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
            #endif
        #endwith
    #enddef

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
        #endwith

        self.run_exposure()
    #enddef


    async def _check_hw_related(self):
        if test_runtime.injected_preprint_warning:
            self._raise_preprint_warning(test_runtime.injected_preprint_warning)
        #endif

        if not self.expo.hwConfig.resinSensor:
            self.logger.info("Disabling resin check")
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.DISABLED
        #endif

        if not self.expo.hwConfig.tilt:
            self.logger.info("Disabling stirring")
            self.expo.check_results[ExposureCheck.STIRRING] = ExposureCheckResult.DISABLED
        #endif

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, self._check_cover_closed)
            await loop.run_in_executor(pool, self._check_hardware)
            if self.expo.hwConfig.resinSensor:
                await loop.run_in_executor(pool, self._check_resin)
            #endif
            await loop.run_in_executor(pool, self._check_start_positions)
            await loop.run_in_executor(pool, self._check_resin_stirring)
        #endwith
    #enddef


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
                #endif

                self.expo.state = ExposureState.COVER_OPEN
                sleep(0.1)
            #endwhile
        #endwith
    #enddef


    def _check_temps(self):
        self.logger.info("Running temperature checks")
        self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.RUNNING
        temperatures = self.expo.hw.getMcTemperatures()
        failed = [i for i in range(2) if temperatures[i] < 0]
        if failed:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.FAILURE
            raise TempSensorFailed(failed)
        #endif

        if temperatures[1] < defines.minAmbientTemp:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.WARNING
            self._raise_preprint_warning(AmbientTooCold(temperatures[1]))
        elif temperatures[1] > defines.maxAmbientTemp:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.WARNING
            self._raise_preprint_warning(AmbientTooHot(temperatures[1]))
        else:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.SUCCESS
        #endif
    #enddef


    def _check_project_data(self):
        self.logger.info("Running project checks")
        self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.RUNNING

        # Raise warning when model or variant does not match the printer
        if self.expo.project.printerModel != defines.slicerPrinterModel or\
                self.expo.project.printerVariant != defines.slicerPrinterVariant:
            self._raise_preprint_warning(
                ModelMismatch(defines.slicerPrinterModel, defines.slicerPrinterVariant,
                              self.expo.project.printerModel, self.expo.project.printerVariant)
            )
        #endif

        # Remove old projects
        self.logger.debug("Running disk cleanup")
        self.expo.check_and_clean_last_data()

        self.logger.debug("Running project copy and check")
        project_state = self.expo.project.copy_and_check()

        if project_state not in (ProjectState.OK, project_state.PRINT_DIRECTLY):
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.FAILURE
            raise ProjectFailed(project_state)
        #endif

        self.logger.info("Project after copy and check: %s", str(self.expo.project))

        # start data preparation by libScreen
        self.logger.debug("Initiating project in libScreen")
        self.expo.startProjectLoading()

        # collect results from libScreen
        if not self.expo.collectProjectData():
            self.logger.error("Collect project data failed")
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.FAILURE
            raise ProjectFailed(self.expo.project.state)
        #endif

        # Warn if printing directly from USB
        if project_state == project_state.PRINT_DIRECTLY:
            self._raise_preprint_warning(PrintingDirectlyFromMedia())
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.WARNING
        #endif

        # Warn if project settings was changed due to config constraints
        alternated = self.expo.project.config.get_altered_values()
        if alternated:
            self._raise_preprint_warning(ProjectSettingsModified(alternated))
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.WARNING
        #endif

        if self.expo.check_results[ExposureCheck.PROJECT] != ExposureCheckResult.WARNING:
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.SUCCESS
        #endif

    #enddef


    def _check_hardware(self):
        self.logger.info("Running start positions hardware checks")
        self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.RUNNING

        self.logger.info("Syncing tower")
        self.expo.hw.towerSyncWait()
        if not self.expo.hw.isTowerSynced():
            self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.FAILURE
            raise TowerFailed()
        #endif

        self.logger.info("Syncing tilt")
        self.expo.hw.tiltSyncWait()

        if not self.expo.hw.isTiltSynced():
            self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.FAILURE
            raise TiltFailed()
        #endif

        self.logger.info("Tilting up")
        self.expo.hw.setTiltProfile('homingFast')
        self.expo.hw.tiltUp()
        while self.expo.hw.isTiltMoving():
            sleep(0.1)
        #endif
        if not self.expo.hw.isTiltOnPosition():
            self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.FAILURE
            raise TiltFailed()
        #endif

        self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.SUCCESS
    #enddef


    def _check_fans(self):
        self.logger.info("Running fan checks")
        self.expo.check_results[ExposureCheck.FAN] = ExposureCheckResult.RUNNING

        # Warm-up fans
        self.logger.info("Warning up fans")
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
            raise FanFailed(failed_fans)
        #endif
        self.logger.info("Fans OK")

        self.expo.runtime_config.fan_error_override = False
        self.expo.runtime_config.check_cooling_expo = True
        self.expo.check_results[ExposureCheck.FAN] = ExposureCheckResult.SUCCESS
    #enddef


    def _check_resin(self):
        self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.RUNNING

        self.logger.info("Running resin measurement")

        volume = self.expo.hw.getResinVolume()
        self.expo.setResinVolume(volume)

        try:
            if not volume:
                raise ResinFailed(volume)
            #endif

            if volume < defines.resinMinVolume:
                raise ResinTooLow(volume)
            #endif

            if volume > defines.resinMaxVolume:
                raise ResinTooHigh(volume)
            #endif
        except ResinFailed:
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.FAILURE
            self.expo.hw.setTowerProfile('homingFast')
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)
            #endwhile
            raise
        #endtry

        self.logger.debug("min: %d [ml], requested: %d [ml], measured: %d [ml]",
                          defines.resinMinVolume, self.expo.project.usedMaterial + defines.resinMinVolume, volume)

        if volume < self.expo.project.usedMaterial + defines.resinMinVolume:
            self.logger.info("Raising resin not enough warning")
            self._raise_preprint_warning(
                ResinNotEnough(volume, self.expo.project.usedMaterial + defines.resinMinVolume))
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.WARNING
        #endif

        self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.SUCCESS
    #enddef


    def _check_start_positions(self):
        self.expo.check_results[ExposureCheck.START_POSITIONS] = ExposureCheckResult.RUNNING

        self.logger.info("Prepare tank and resin")
        if self.expo.hwConfig.tilt:
            self.logger.info("Tilting down")
            self.expo.hw.tiltDownWait()
        #endif

        self.logger.info("Tower to print start position")
        self.expo.hw.setTowerProfile('homingFast')
        self.expo.hw.towerToPosition(0.25)  # TODO: Constant in code, seems important
        while not self.expo.hw.isTowerOnPosition(retries=2):
            sleep(0.25)
        #endwhile

        if self.expo.hw.towerPositonFailed():
            self.expo.check_results[ExposureCheck.START_POSITIONS] = ExposureCheckResult.FAILURE
            exception = TowerMoveFailed()
            self.expo.exception = exception
            self.expo.hw.setTowerProfile('homingFast')
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)
            #endwhile

            raise exception
        #endif

        self.expo.check_results[ExposureCheck.START_POSITIONS] = ExposureCheckResult.SUCCESS
    #enddef


    def _check_resin_stirring(self):
        self.expo.check_results[ExposureCheck.STIRRING] = ExposureCheckResult.RUNNING
        if self.expo.hwConfig.tilt:
            self.expo.hw.stirResin()
            self.expo.check_results[ExposureCheck.STIRRING] = ExposureCheckResult.SUCCESS
        #endif
    #enddef


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
        prevWhitePixels = 0
        totalLayers = project.totalLayers
        stuck = False
        wasStirring = True
        exposureCompensation = 0.0
        calibratePadThickness = project.calibratePadThickness
        calibrateTextThickness = project.calibrateTextThickness

        for i in range(totalLayers):
            ii = i + 1
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                command = None
            except Exception:
                self.logger.exception("getCommand exception")
                command = None
            #endtry

            if command == "updown":
                self.doUpAndDown()
                wasStirring = True
                exposureCompensation = self.expo.hwConfig.upAndDownExpoComp / 10.0
            #endif

            if command == "exit":
                break
            #endif

            if command == "pause":
                if not self.expo.hwConfig.blinkExposure:
                    self.expo.hw.uvLed(False)
                #endif

                if self.doWait(False) == "exit":
                    break
                #endif

                if not self.expo.hwConfig.blinkExposure:
                    self.expo.hw.uvLed(True)
                #endif
            #endif

            if self.expo.resinVolume:
                self.expo.remain_resin_ml = self.expo.resinVolume - int(self.expo.resinCount)
                self.expo.warn_resin = self.expo.remain_resin_ml < defines.resinLowWarn
                self.expo.low_resin = self.expo.remain_resin_ml < defines.resinFeedWait
            #endif

            if command == "feedme" or self.expo.low_resin:
                self.expo.hw.powerLed("warn")
                if self.expo.hwConfig.tilt:
                    self.expo.hw.tiltLayerUpWait()
                #endif
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
                #endif
                wasStirring = True

                # Resume print
                self.expo.hw.powerLed("normal")
                self.expo.state = ExposureState.PRINTING
            #endif

            if self.expo.hwConfig.upAndDownEveryLayer and self.expo.actualLayer and not self.expo.actualLayer % self.expo.hwConfig.upAndDownEveryLayer:
                self.doUpAndDown()
                wasStirring = True
                exposureCompensation = self.expo.hwConfig.upAndDownExpoComp / 10.0
            #endif

            # first layer - extra height + extra time
            if not i:
                step = project.layerMicroStepsFirst
                etime = project.expTimeFirst
            # second two layers - normal height + extra time
            elif i < 3:
                step = project.layerMicroSteps
                etime = project.expTimeFirst
            # next project.fadeLayers is fade between project.expTimeFirst and project.expTime
            elif i < project.fadeLayers + 3:
                step = project.layerMicroSteps
                # expTimes may be changed during print
                timeLoss = (project.expTimeFirst - project.expTime) / float(project.fadeLayers)
                self.logger.debug("timeLoss: %0.3f", timeLoss)
                etime = project.expTimeFirst - (i - 2) * timeLoss
            # standard parameters to first change
            elif ii < project.slice2:
                step = project.layerMicroSteps
                etime = project.expTime
            # parameters of second change
            elif ii < project.slice3:
                step = project.layerMicroSteps2
                etime = project.expTime2
            # parameters of third change
            else:
                step = project.layerMicroSteps3
                etime = project.expTime3
            #endif

            etime += exposureCompensation
            exposureCompensation = 0.0

            self.expo.actualLayer = ii
            self.expo.position += step

            self.logger.info(
                "Layer: %04d/%04d (%s), exposure [sec]: %.3f, slowLayersDone: %d, height [mm]: %.3f %.3f/%.3f,"
                " elapsed [min]: %d, remain [min]: %d, used [ml]: %d, remaining [ml]: %d, RAM: %.1f%%, CPU: %.1f%%",
                self.expo.actualLayer,
                project.totalLayers,
                project.to_print[i],
                etime,
                self.expo.slowLayersDone,
                step,
                self.expo.hwConfig.calcMM(self.expo.position),
                self.expo.totalHeight,
                int(round((datetime.now(tz=timezone.utc) - self.expo.printStartTime).total_seconds() / 60)),
                self.expo.countRemainTime(),
                self.expo.resinCount,
                self.expo.remain_resin_ml if self.expo.remain_resin_ml else -1,
                psutil.virtual_memory().percent,
                psutil.cpu_percent(),
            )

            if ii < calibratePadThickness:
                overlayName = 'calibPad'
            elif ii < calibratePadThickness + calibrateTextThickness:
                overlayName = 'calib'
            else:
                overlayName = None
            #endif

            success, whitePixels, uvTemp, AmbTemp = self.doFrame(project.to_print[ii] if ii < totalLayers else None,
                                                                 self.expo.position + self.expo.hwConfig.calibTowerOffset,
                                                                 etime,
                                                                 overlayName,
                                                                 prevWhitePixels,
                                                                 wasStirring,
                                                                 False)

            if not success and not self.doStuckRelease():
                self.expo.hw.powerLed("normal")
                self.expo.cancel()
                stuck = True
                break
            #endif

            # exposure second part too
            if self.expo.perPartes and whitePixels > self.expo.hwConfig.whitePixelsThd:
                success, dummy, uvTemp, AmbTemp = self.doFrame(project.to_print[ii] if ii < totalLayers else None,
                                                               self.expo.position + self.expo.hwConfig.calibTowerOffset,
                                                               etime,
                                                               overlayName,
                                                               whitePixels,
                                                               wasStirring,
                                                               True)

                if not success and not self.doStuckRelease():
                    stuck = True
                    break
                #endif
            #endif

            self.logger.info("UV temperature [C]: %.1f  Ambient temperature [C]: %.1f", uvTemp, AmbTemp)

            prevWhitePixels = whitePixels
            wasStirring = False

            # /1000.0 - we want cm3 (=ml) not mm3
            self.expo.resinCount += float(whitePixels * defines.screenPixelSize ** 2 * self.expo.hwConfig.calcMM(step) / 1000.0)
            self.logger.debug("resinCount: %f", self.expo.resinCount)

            seconds = (datetime.now(tz=timezone.utc) - self.expo.printStartTime).total_seconds()
            self.expo.printTime = int(seconds / 60)

            if self.expo.hwConfig.trigger:
                self.expo.hw.cameraLed(True)
                sleep(self.expo.hwConfig.trigger / 10.0)
                self.expo.hw.cameraLed(False)
            #endif

        #endfor

        self.expo.hw.saveUvStatistics()
        self.expo.hw.uvLed(False)

        if not stuck:
            self.expo.state = ExposureState.GOING_UP
            self.expo.hw.setTowerProfile('homingFast')
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)
            #endwhile
        #endif

        self.expo.hw.stopFans()
        self.expo.hw.motorsRelease()

        self.expo.printEndTime = datetime.now(tz=timezone.utc)
        self.logger.info("Job finished - real printing time is %s minutes", self.expo.printTime)

        if not self.expo.canceled:
            statistics['finished_projects'] += 1
        statistics['layers'] += self.expo.actualLayer
        statistics['total_seconds'] += seconds
        statistics['total_resin'] += self.expo.resinCount
        statistics.save_raw()
        self.expo.screen.saveDisplayUsage()

        if self.expo.canceled:
            self.expo.state = ExposureState.CANCELED
        else:
            self.expo.state = ExposureState.FINISHED
        #endif

        self.expo.write_last_exposure()

        if not self.expo.canceled:
            if self.expo.hwConfig.autoOff:
                shut_down(self.expo.hw)
            #endif
        #endif

        self.logger.debug("Exposure ended")
    #enddef

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
        #endwhile
        self.expo.state = old_state
        self.logger.info("Cover closed now")
        return True
    #enddef

#endclass


class Exposure:
    def __init__(self, job_id: int, hwConfig: HwConfig, hw: Hardware, screen: Screen, runtime_config: RuntimeConfig,
                 project: str):
        check_ready_to_print(hwConfig, hw)
        self.change = Signal()
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.runtime_config = runtime_config
        self.project: Optional[Project] = None
        self.hw = hw
        self.screen = screen
        self.resinCount = 0.0
        self.resinVolume = None
        self.expoThread: Optional[threading.Thread] = None
        self.zipName = None
        self.perPartes = None
        self.position = 0
        self.actualLayer = 0
        self.slowLayersDone = 0
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

        # Read project
        self.project = Project(self.hwConfig)
        result = self.project.read(project)
        if result in [ProjectState.OK, ProjectState.PRINT_DIRECTLY]:
            self.state = ExposureState.CONFIRM
        else:
            raise ProjectFailed(result)
        #endif

        # FIXME spatne se spocita pri zlomech (layerMicroSteps 2 a 3)
        self.totalHeight = (self.project.totalLayers - 1) * self.hwConfig.calcMM(
            self.project.layerMicroSteps) + self.hwConfig.calcMM(self.project.layerMicroStepsFirst)

        self.logger.info("Created new exposure object id: %s", self.instance_id)
    #enddef


    def confirm_print_start(self):
        self.expoThread.start()
        self.expoCommands.put("checks")
    #enddef


    def confirm_print_warning(self):
        self.logger.info("User confirmed print check warnings")
        self.expoThread.warning_dismissed.set()
    #enddef


    def reject_print_warning(self):
        self.logger.info("User rejected print due to warnings")
        self.expoThread.warning_result = WarningEscalation(self.warning)
        self.expoThread.warning_dismissed.set()
    #enddef


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
        #endif
    #enddef

    def try_cancel(self):
        self.logger.info("Trying cancel exposure")
        cancelable_states = ExposureState.cancelable_states()
        if self.state in cancelable_states:
            self.canceled = True
            self.state = ExposureState.DONE
        else:
            raise NotAvailableInState(self.state, cancelable_states)
        return True
        #endif
    #enddef

    def __setattr__(self, key: str, value: Any):
        # TODO: This is too generic
        # Would be better to have properties for all important attributes with separate signals
        # Or to separate important attributes to another object

        if key == "state" and hasattr(self, "state"):
            self.logger.info("State changed: %s -> %s", self.state, value)
        #endif

        object.__setattr__(self, key, value)
        if not key.startswith("_"):
            self.change.emit(key, value)
        #endif
    #enddef


    def startProjectLoading(self):
        params = {
                'project' : self.project.path,
                'expTime' : self.project.expTime,
                'expTimeFirst' : self.project.expTimeFirst,
                'calibrateTime' : self.project.calibrateTime,
                }
        self.screen.startProject(params = params)
    #enddef


    def collectProjectData(self):
        self.position = 0
        self.actualLayer = 0
        self.resinCount = 0.0
        self.slowLayersDone = 0
        retcode, self.perPartes = self.screen.projectStatus()
        return retcode
    #enddef


    def prepare(self):
        self.hw.setTowerProfile('layer')
        self.hw.towerMoveAbsoluteWait(0)  # first layer will move up

        self.screen.getImgBlack()
        self.hw.uvLedPwm = self.hwConfig.uvPwm
        if not self.hwConfig.blinkExposure:
            self.hw.uvLed(True)
        #endif
    #enddef

    @deprecated("Should be obsolete, use confirm print start instead")
    def start(self):
        if self.expoThread:
            self.screen.cleanup()
            self.expoThread.start()
        else:
            self.logger.error("Can't start exposure thread")
        #endif
    #enddef

    @property
    def in_progress(self):
        if not self.expoThread:
            return False

        return self.expoThread.is_alive()
    #enddef


    @property
    def done(self):
        return self.state in ExposureState.finished_states()
    #enddef


    @property
    def progress(self) -> float:
        if self.state == ExposureState.FINISHED:
            return 1

        completed_layers = self.actualLayer - 1 if self.actualLayer else 0
        return completed_layers / self.project.totalLayers
    #enddef


    def waitDone(self):
        if self.expoThread:
            self.expoThread.join()
        #endif
    #enddef


    def doUpAndDown(self):
        self.state = ExposureState.PENDING_ACTION
        self.expoCommands.put("updown")
    #enddef


    def doExitPrint(self):
        self.expoCommands.put("exit")
    #enddef


    def doFeedMe(self):
        self.state = ExposureState.PENDING_ACTION
        self.expoCommands.put("feedme")
    #enddef


    def doPause(self):
        self.expoCommands.put("pause")
    #enddef


    def doContinue(self):
        self.expoCommands.put("continue")
    #enddef


    def doBack(self):
        self.expoCommands.put("back")
    #enddef


    def setResinVolume(self, volume):
        if volume is None:
            self.resinVolume = None
        else:
            self.resinVolume = volume + int(self.resinCount)
        #endif
    #enddef

    def countRemainTime(self):
        if self.project:
            return self.project.count_remain_time(self.actualLayer, self.slowLayersDone)
        else:
            self.logger.warning("No active project to get remaining time")
            return -1
        #endif
    #enddef

    def last_project_data(self):
        return {
            'name': self.project.name,
            'print_time': self.printTime,
            'layers': self.actualLayer,
            'consumed_resin': self.resinCount,
            'project_file': self.project.path,
            'exp_time_ms': self.project.expTime * 1000,
            'exp_time_first_ms': self.project.expTimeFirst * 1000,
            'exp_time_calibrate_ms': self.project.calibrateTime * 1000,
        }
    #enddef

    def write_last_exposure(self):
        self.save()
        if self.canceled or not self.hwConfig.autoOff:
            Exposure.cleanup_last_data(self.logger)
    #enddef

    def save(self):
        self.logger.debug(
            "\nSaving Exposure \n- '%s'\n- '%s'\n- '%s'\n- '%s'",
            defines.lastProjectHwConfig,
            defines.lastProjectFactoryFile,
            defines.lastProjectConfigFile,
            defines.lastProjectPickler
        )
        with open(defines.lastProjectPickler, 'wb') as pickle_io:
            ExposurePickler(pickle_io).dump(self)
    #enddef

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
    #enddef

    def check_and_clean_last_data(self) -> None:
        clear_all = self.project.path and \
            not str(self.project.path).startswith(defines.previousPrints)
        Exposure.cleanup_last_data(self.logger, clear_all=clear_all)
    #enddef

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
    #enddef

    def stats_seen(self):
        self.state = ExposureState.DONE


#endclass
