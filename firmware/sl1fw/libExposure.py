# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime, timedelta, timezone
from time import sleep, time
from typing import Optional, Callable, Any, Set

from sl1fw.project.project import Project

from sl1fw import defines
from sl1fw.exposure_state import ExposureState
from sl1fw.libConfig import HwConfig, TomlConfigStats
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen


class ExposureThread(threading.Thread):

    def __init__(self, commands: queue.Queue, expo: Exposure):
        super(ExposureThread, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.expo = expo
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

        if self.expo.calibAreas:
            etime = exposureTime + self.expo.calibAreas[-1]['time'] - self.expo.calibAreas[0]['time']
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
            if self.expo.calibAreas:
                exptime = 1000 * (exposureTime + self.expo.calibAreas[-1]['time'] - self.expo.calibAreas[0]['time'])
                self.expo.hw.uvLed(True, etime)


                for area in self.expo.calibAreas:
                    while exptime > 1000 * (self.expo.calibAreas[-1]['time'] - area['time']):
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
                    UVIsOn, etime = self.expo.hw.getUvLedState()
                #endwhile
            #endif
        else:
            sleep(exposureTime)
            if self.expo.calibAreas:
                lastArea = self.expo.calibAreas[0]
                for area in self.expo.calibAreas[1:]:
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
            slowMove = bool(whitePixels > self.expo.hwConfig.whitePixelsThd)  # avoid passing numpy bool
            if slowMove and self.expo.slowLayers:
                self.expo.slowLayers -= 1
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
            return False
        #endif

        self.expo.hw.powerLed("warn")
        self.expo.state = ExposureState.STUCK_RECOVERY

        if not self.expo.hw.tiltSyncWait(retries = 1):
            self.logger.error("Stuck release failed")
            self.expo.state = ExposureState.TILT_FAILURE
            self.doWait(True)
            return False
        #endif

        self.expo.state = ExposureState.STIRRING
        self.expo.hw.stirResin()
        self.expo.hw.powerLed("normal")
        self.expo.state = ExposureState.PRINTING
        return True
    #enddef


    def run(self):
        self.logger.debug("Started exposure thread")
        self.expo.printStartTime = time()
        statsFile = TomlConfigStats(defines.statsData, self.expo.hw)
        stats = statsFile.load()
        seconds = 0
        try:
            project = self.expo.project
            prevWhitePixels = 0
            totalLayers = project.totalLayers
            stuck = False
            wasStirring = True
            exposureCompensation = 0.0

            for i in range(totalLayers):
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
                elif i + 1 < project.slice2:
                    step = project.layerMicroSteps
                    etime = project.expTime
                # parameters of second change
                elif i + 1 < project.slice3:
                    step = project.layerMicroSteps2
                    etime = project.expTime2
                # parameters of third change
                else:
                    step = project.layerMicroSteps3
                    etime = project.expTime3
                #endif

                etime += exposureCompensation
                exposureCompensation = 0.0

                self.expo.actualLayer = i + 1
                self.expo.position += step
                self.logger.debug("LAYER %04d (%s)  steps: %d  position: %d  time: %.3f  slowLayers: %d",
                                  self.expo.actualLayer, project.to_print[i], step, self.expo.position, etime, self.expo.slowLayers)

                if i < 2:
                    overlayName = 'calibPad'
                elif i < project.calibrateInfoLayers + 2:
                    overlayName = 'calib'
                else:
                    overlayName = None
                #endif

                success, whitePixels, uvTemp, AmbTemp = self.doFrame(project.to_print[i + 1] if i + 1 < totalLayers else None,
                                                                     self.expo.position + self.expo.hwConfig.calibTowerOffset,
                                                                     etime,
                                                                     overlayName,
                                                                     prevWhitePixels,
                                                                     wasStirring,
                                                                     False)

                if not success and not self.doStuckRelease():
                    self.expo.hw.powerLed("normal")
                    self.expo.canceled = True
                    stuck = True
                    break
                #endif

                # exposure second part too
                if self.expo.perPartes and whitePixels > self.expo.hwConfig.whitePixelsThd:
                    success, dummy, uvTemp, AmbTemp = self.doFrame(project.to_print[i + 1] if i + 1 < totalLayers else None,
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

                # /1000 - we want cm3 (=ml) not mm3
                self.expo.resinCount += float(whitePixels * defines.screenPixelSize ** 2 * self.expo.hwConfig.calcMM(step) / 1000)
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
            statsFile.save(stats)
            self.expo.screen.saveDisplayUsage()

            self.expo.state = ExposureState.FINISHED

        except Exception as e:
            self.logger.exception("Exposure thread exception")
            self.expo.state = ExposureState.FAILURE
        #endtry

        self.logger.debug("Exposure thread ended")
    #enddef

#endclass


class Exposure:
    instance_counter = 0

    def __init__(self, hwConfig: HwConfig, hw: Hardware, screen: Screen):
        self._change_handlers: Set[Callable[[str, Any], None]] = set()
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.project: Optional[Project] = None
        self.hw = hw
        self.screen = screen
        self.resinCount = 0.0
        self.resinVolume = None
        self.canceled = False
        self.expoThread = None
        self.zipName = None
        self.perPartes = None
        self.position = 0
        self.actualLayer = 0
        self.expoCommands = None
        self.slowLayers = 0
        self.totalHeight = None
        self.printStartTime = 0
        self.printTime = 0
        self.state = ExposureState.INIT
        self.remaining_wait_sec = 0
        self.low_resin = False
        self.warn_resin = False
        self.remain_resin_ml = None
        self.exposure_end: Optional[datetime] = None
        self.instance_id = self.instance_counter
        self.instance_counter += 1
    #enddef


    def setProject(self, project_filename):
        self.project = Project(self.hwConfig)
        return self.project.read(project_filename)


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
                'filename' : self.project.source,
                'toPrint' : self.project.to_print,
                'expTime' : self.project.expTime,
                'calibrateRegions' : self.project.calibrateRegions,
                'calibrateTime' : self.project.calibrateTime,
                'calibratePenetration' : self.project.calibratePenetration,
                'perPartes' : self.hwConfig.perPartes,
                'whitePixelsThd' : self.hwConfig.whitePixelsThd,
                'overlayName' : 'calibPad',
                }
        self.screen.startProject(params = params)
        self.expoCommands = queue.Queue()
        self.expoThread = ExposureThread(self.expoCommands, self)
    #enddef


    def collectProjectData(self):
        self.position = 0
        self.actualLayer = 0
        self.resinCount = 0.0
        self.slowLayers = self.project.layersSlow    # we need local copy for decrementing
        retcode, self.perPartes, self.calibAreas = self.screen.projectStatus()
        return retcode
    #enddef


    def prepare(self):
        # TODO: This must be a prepare method in exposure

        self.hw.setTowerProfile('layer')
        self.hw.towerMoveAbsoluteWait(0)  # first layer will move up
        self.canceled = False

        # FIXME spatne se spocita pri zlomech (layerMicroSteps 2 a 3)
        self.totalHeight = (self.project.totalLayers - 1) * self.hwConfig.calcMM(
            self.project.layerMicroSteps) + self.hwConfig.calcMM(self.project.layerMicroStepsFirst)

        self.screen.getImgBlack()
        self.hw.uvLedPwm = self.hwConfig.uvPwm
        if not self.hwConfig.blinkExposure:
            self.hw.uvLed(True)
        #endif
    #enddef


    def start(self):
        if self.expoThread:
            self.expoThread.start()
            self.state = ExposureState.PRINTING
        else:
            self.logger.error("Can't start exposure thread")
        #endif
    #enddef


    def inProgress(self):
        if self.expoThread:
            return self.expoThread.is_alive()
        else:
            return False
        #endif
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
        hwConfig = self.hwConfig
        timeRemain = 0
        fastLayers = self.project.totalLayers - self.actualLayer - self.slowLayers
        # first 3 layers with expTimeFirst
        long1 = 3 - self.actualLayer
        if long1 > 0:
            timeRemain += long1 * (self.project.expTimeFirst - self.project.expTime)
        #endif
        # fade layers (approx)
        long2 = self.project.fadeLayers + 3 - self.actualLayer
        if long2 > 0:
            timeRemain += long2 * ((self.project.expTimeFirst - self.project.expTime) / 2 - self.project.expTime)
        #endif
        timeRemain += fastLayers * hwConfig.tiltFastTime
        timeRemain += self.slowLayers * hwConfig.tiltSlowTime

        # FIXME slice2 and slice3
        timeRemain += (fastLayers + self.slowLayers) * (
                self.project.calibrateRegions * self.project.calibrateTime
                + self.hwConfig.calcMM(self.project.layerMicroSteps) * 5  # tower move
                + self.project.expTime
                + hwConfig.delayBeforeExposure
                + hwConfig.delayAfterExposure)
        self.logger.debug("timeRemain: %f", timeRemain)
        return int(round(timeRemain / 60))
    #enddef

#endclass
