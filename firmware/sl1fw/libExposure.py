# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import queue
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from time import sleep, time, monotonic
from typing import Optional, Callable, Any, Set, List, Dict

from deprecated import deprecated

from sl1fw import defines
from sl1fw.exposure_state import ExposureState, TiltFailure, TempSensorFailure, AmbientTooCold, AmbientTooHot, \
    ModelMismatchWarning, ProjectFailure, PrintingDirectlyWarning, TowerFailure, FanFailure, ResinFailure, ResinTooLow, \
    ResinTooHigh, TowerMoveFailure, ExposureWarning, ExposureException, WarningEscalation, ExposureCheck, \
    ExposureCheckResult, ResinNotEnoughWarning
from sl1fw.libConfig import HwConfig, TomlConfigStats, RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen
from sl1fw.project.functions import ramdisk_cleanup
from sl1fw.project.project import Project, ProjectState


class ExposureThread(threading.Thread):

    def __init__(self, commands: queue.Queue, expo: Exposure):
        super(ExposureThread, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.expo = expo
        self._fanCheckStartTime: Optional[float] = None
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
        self.logger.debug("Exposure started: %d seconds, end: %s", etime, self.expo.exposure_end)

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
        self.logger.debug("exposure done")
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
            raise TiltFailure()
        #endif

        self.expo.hw.powerLed("warn")
        self.expo.state = ExposureState.STUCK_RECOVERY

        if not self.expo.hw.tiltSyncWait(retries = 1):
            self.logger.error("Stuck release failed")
            raise TiltFailure()
        #endif

        self.expo.state = ExposureState.STIRRING
        self.expo.hw.stirResin()
        self.expo.hw.powerLed("normal")
        self.expo.state = ExposureState.PRINTING
    #enddef


    def run(self):
        try:
            self.logger.debug("Started exposure thread")

            while not self.expo.done:
                command = self.commands.get()
                if command == "exit":
                    self.logger.debug("Exiting exposure thread on exit command")
                    break
                elif command == "checks":
                    asyncio.run(self._run_checks())
                elif command == "confirm_warnings":
                    self.run_exposure()
                else:
                    self.logger.error("Undefined command: \"%s\" ignored", command)
                #endif
            #endwhile

            self.logger.debug("Exiting exposure thread on state: %s", self.expo.state)
        except Exception as exception:
            self.logger.exception("Exposure thread exception")
            self.expo.exception = exception
            self.expo.state = ExposureState.FAILURE
        #endtry
    #enddef


    async def _run_checks(self):
        self.expo.state = ExposureState.CHECKS
        self.logger.debug("Running pre-print checks")

        loop = asyncio.get_running_loop()

        with concurrent.futures.ThreadPoolExecutor() as pool:
            fans = loop.run_in_executor(pool, self._check_fans)
            temps = loop.run_in_executor(pool, self._check_temps)
            project = loop.run_in_executor(pool, self._check_project_data)
            hw = loop.run_in_executor(pool, self._check_hw_related)
        #endwith

        await asyncio.gather(
            fans, temps, project, hw
        )

        if not self.expo.warnings:
            self.run_exposure()
        else:
            self.expo.state = ExposureState.CHECK_WARNING
        #endif
    #enddef


    def _check_hw_related(self):
        if not self.expo.hwConfig.resinSensor:
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.DISABLED
        #endif

        if not self.expo.hwConfig.tilt:
            self.expo.check_results[ExposureCheck.STIRRING] = ExposureCheckResult.DISABLED
        #endif

        self._check_cover_closed()
        self._check_hardware()

        if self.expo.hwConfig.resinSensor:
            self._check_resin()
        #endif

        self._check_start_positions()
        self._check_resin_stirring()
    #enddef


    def _check_cover_closed(self):
        self.expo.check_results[ExposureCheck.COVER] = ExposureCheckResult.RUNNING
        if not self.expo.hwConfig.coverCheck:
            self.expo.check_results[ExposureCheck.COVER] = ExposureCheckResult.DISABLED
            return

        while True:
            if self.expo.hw.isCoverClosed():
                self.expo.state = ExposureState.CHECKS
                self.expo.check_results[ExposureCheck.COVER] = ExposureCheckResult.SUCCESS
                return
            #endif

            self.expo.state = ExposureState.COVER_OPEN
            sleep(0.1)
        #endwhile
    #enddef


    def _check_temps(self):
        self.logger.debug("Running temperature checks")
        self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.RUNNING
        temperatures = self.expo.hw.getMcTemperatures()
        failed = [i for i in range(2) if temperatures[i] < 0]
        if failed:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.FAILURE
            raise TempSensorFailure(failed)
        #endif

        if temperatures[1] < defines.minAmbientTemp:
            self.expo.warnings.append(AmbientTooCold(temperatures[1]))
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.WARNING
        elif temperatures[1] > defines.maxAmbientTemp:
            self.expo.warnings.append(AmbientTooHot(temperatures[1]))
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.WARNING
        else:
            self.expo.check_results[ExposureCheck.TEMPERATURE] = ExposureCheckResult.SUCCESS
        #endif
    #enddef


    def _check_project_data(self):
        self.logger.debug("Running project checks")
        self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.RUNNING

        # Raise warning when model or variant does not match the printer
        if self.expo.project.printerModel != defines.slicerPrinterModel or\
                self.expo.project.printerVariant != defines.slicerPrinterVariant:
            self.expo.warnings.append(
                ModelMismatchWarning(defines.slicerPrinterModel, defines.slicerPrinterVariant,
                                     self.expo.project.printerModel, self.expo.project.printerVariant)
            )
        #endif

        # Remove old projects from ramdisk
        ramdisk_cleanup(self.logger)
        project_state = self.expo.project.copy_and_check()

        if project_state not in (ProjectState.OK, project_state.PRINT_DIRECTLY):
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.FAILURE
            raise ProjectFailure(project_state)
        #endif

        self.logger.info(str(self.expo.project))

        # start data preparation by libScreen
        self.expo.startProjectLoading()

        # collect results from libScreen
        if not self.expo.collectProjectData():
            self.logger.error("Collect project data failed")
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.WARNING
            raise ProjectFailure(self.expo.project.state)
        #endif

        if project_state == project_state.PRINT_DIRECTLY:
            self.expo.warnings.append(PrintingDirectlyWarning())
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.WARNING
        else:
            self.expo.check_results[ExposureCheck.PROJECT] = ExposureCheckResult.SUCCESS
        #endif
    #enddef


    def _check_hardware(self):
        self.logger.debug("Running start positions hardware checks")
        self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.RUNNING

        self.expo.hw.towerSyncWait()
        if not self.expo.hw.isTowerSynced():
            self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.FAILURE
            raise TowerFailure()
        #endif

        self.expo.hw.tiltSyncWait()

        if not self.expo.hw.isTiltSynced():
            self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.FAILURE
            raise TiltFailure()
        #endif

        self.expo.hw.setTiltProfile('homingFast')
        self.expo.hw.tiltUpWait()

        self.expo.check_results[ExposureCheck.HARDWARE] = ExposureCheckResult.SUCCESS
    #enddef


    def _check_fans(self):
        self.logger.debug("Running fan checks")
        self.expo.check_results[ExposureCheck.FAN] = ExposureCheckResult.RUNNING
        self._fanCheckStartTime = monotonic()
        self.expo.hw.startFans()

        # Wait for fans to finish warmup
        fansRunningTime = monotonic() - self._fanCheckStartTime
        if fansRunningTime < defines.fanStartStopTime:
            sleepTime = defines.fanStartStopTime - fansRunningTime
            self.logger.debug("Waiting %.2f secs for fans", sleepTime)
            sleep(sleepTime)
        #endif

        fansState = self.expo.hw.getFansError().values()
        failed_fans = []
        if any(fansState) and not defines.fan_check_override:
            for num, state in enumerate(fansState):
                if state:
                    failed_fans.append(num)
                #endif
            #endfor
            self.expo.check_results[ExposureCheck.FAN] = ExposureCheckResult.FAILURE
            raise FanFailure(failed_fans)
        #endif

        self.expo.runtime_config.fan_error_override = False
        self.expo.runtime_config.check_cooling_expo = True

        self.expo.check_results[ExposureCheck.FAN] = ExposureCheckResult.SUCCESS
    #enddef


    def _check_resin(self):
        self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.RUNNING

        self.logger.debug("Running resin measurement")

        volume = self.expo.hw.getResinVolume()
        self.expo.setResinVolume(volume)

        try:
            if not volume:
                raise ResinFailure(volume)
            #endif

            if volume < defines.resinMinVolume:
                raise ResinTooLow(volume)
            #endif

            if volume > defines.resinMaxVolume:
                raise ResinTooHigh(volume)
            #endif
        except ResinFailure:
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.FAILURE
            self.expo.hw.setTowerProfile('homingFast')
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)
            #endwhile
            raise
        #endtry

        self.logger.debug("requested: %d [ml], measured: %d [ml]", self.expo.project.usedMaterial, volume)

        if volume < self.expo.project.usedMaterial:
            self.expo.warnings.append(ResinNotEnoughWarning(volume, self.expo.project.usedMaterial))
            self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.WARNING
        #endif

        self.expo.check_results[ExposureCheck.RESIN] = ExposureCheckResult.SUCCESS
    #enddef


    def _check_start_positions(self):
        self.expo.check_results[ExposureCheck.START_POSITIONS] = ExposureCheckResult.RUNNING

        self.logger.debug("Prepare tank and resin")
        if self.expo.hwConfig.tilt:
            self.expo.hw.tiltDownWait()
        #endif

        self.expo.hw.setTowerProfile('homingFast')
        self.expo.hw.towerToPosition(0.25)
        while not self.expo.hw.isTowerOnPosition(retries=2):
            sleep(0.25)
        #endwhile

        if self.expo.hw.towerPositonFailed():
            self.expo.check_results[ExposureCheck.START_POSITIONS] = ExposureCheckResult.FAILURE
            exception = TowerMoveFailure()
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

        self.logger.debug("Running exposure")
        self.expo.state = ExposureState.PRINTING
        self.expo.printStartTime = time()
        statsFile = TomlConfigStats(defines.statsData, self.expo.hw)
        stats = statsFile.load()
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

                if self.expo.hwConfig.tilt:
                    self.expo.state = ExposureState.STIRRING
                    self.expo.hw.setTiltProfile('homingFast')
                    self.expo.hw.tiltDownWait()
                    self.expo.hw.stirResin()
                #endif
                wasStirring = True
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
                " elapsed [min]: %d, remain [min]: %d, used [ml]: %d, remaining [ml]: %d",
                self.expo.actualLayer,
                project.totalLayers,
                project.to_print[i],
                etime,
                self.expo.slowLayersDone,
                step,
                self.expo.hwConfig.calcMM(self.expo.position),
                self.expo.totalHeight,
                int(round((time() - self.expo.printStartTime) / 60)),
                self.expo.countRemainTime(),
                self.expo.resinCount,
                self.expo.remain_resin_ml if self.expo.remain_resin_ml else -1
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
            self.logger.debug("resinCount: %f" % self.expo.resinCount)

            seconds = time() - self.expo.printStartTime
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

        self.logger.info("Job finished - real printing time is %s minutes", self.expo.printTime)

        stats['projects'] += 1
        stats['layers'] += self.expo.actualLayer
        stats['total_seconds'] += seconds
        statsFile.save(data = stats)
        self.expo.screen.saveDisplayUsage()

        if self.expo.canceled:
            self.expo.state = ExposureState.CANCELED
        else:
            self.expo.state = ExposureState.FINISHED
        #endif
        self.logger.debug("Exposure ended")
    #enddef

#endclass


class Exposure:
    instance_counter = 0

    def __init__(self, hwConfig: HwConfig, hw: Hardware, screen: Screen, runtime_config: RuntimeConfig):
        self._change_handlers: Set[Callable[[str, Any], None]] = set()
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
        self.totalHeight = None
        self.printStartTime = 0
        self.printTime = 0
        self.state = ExposureState.INIT
        self.remaining_wait_sec = 0
        self.low_resin = False
        self.warn_resin = False
        self.remain_resin_ml = None
        self.exposure_end: Optional[datetime] = None
        self.instance_id = Exposure.instance_counter
        Exposure.instance_counter += 1
        self.check_results: Dict[ExposureCheck, ExposureCheckResult] = defaultdict(lambda: ExposureCheckResult.SCHEDULED)
        self.warnings: List[ExposureWarning] = []
        self.exception: Optional[ExposureException] = None
        self.canceled = False
        self.expoCommands = queue.Queue()
        self.expoThread = ExposureThread(self.expoCommands, self)
        self.logger.debug("Created new exposure object id: %s", self.instance_id)
    #enddef


    def setProject(self, project_filename):
        self.state = ExposureState.READING_DATA
        self.project = Project(self.hwConfig)
        result = self.project.read(project_filename)
        if result in [ProjectState.OK, ProjectState.PRINT_DIRECTLY]:
            self.state = ExposureState.CONFIRM
        else:
            raise ProjectFailure(result)
        #endif

        return result
    #enddef


    def confirm_print_start(self):
        self.expoThread.start()
        self.expoCommands.put("checks")
    #enddef


    def confirm_print_warnings(self):
        self.logger.debug("User confirmed print check warnings")
        self.doConfirmWarnings()
    #enddef


    def reject_print_warnings(self):
        self.logger.debug("User rejected print due to warnings")
        self.state = ExposureState.FAILURE
        self.exception = WarningEscalation()
        self.doExitPrint()
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
            self.state = ExposureState.INIT
        #endif
    #enddef


    def __setattr__(self, key: str, value: Any):
        object.__setattr__(self, key, value)
        if not key.startswith("_"):
            for handler in self._change_handlers:
                handler(key, value)
            #endfor
        #endif
    #enddef


    def add_onchange_handler(self, handler: Callable[[str, Any], None]):
        self._change_handlers.add(handler)
    #enddef


    def startProjectLoading(self):
        params = {
                'project' : self.project.source,
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

        # FIXME spatne se spocita pri zlomech (layerMicroSteps 2 a 3)
        self.totalHeight = (self.project.totalLayers - 1) * self.hwConfig.calcMM(
            self.project.layerMicroSteps) + self.hwConfig.calcMM(self.project.layerMicroStepsFirst)

        self.screen.getImgBlack()
        self.hw.uvLedPwm = self.hwConfig.uvPwm
        if not self.hwConfig.blinkExposure:
            self.hw.uvLed(True)
        #endif
    #enddef

    @deprecated(reason="Should be obolete, use confirm print start instead")
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
        return self.expoThread.is_alive()
    #enddef


    @property
    def done(self):
        return self.state in ExposureState.FINISHED_STATES()
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


    def doConfirmWarnings(self):
        self.expoCommands.put("confirm_warnings")
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
            self.logger.warning("No active project to get remainng time")
            return -1
        #endif
    #enddef

#endclass
