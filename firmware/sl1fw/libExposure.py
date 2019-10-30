# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import queue
import threading
from time import sleep, time
from typing import TYPE_CHECKING, Optional

from sl1fw import defines
from sl1fw.libConfig import HwConfig, TomlConfigStats
from sl1fw.project.project import Project
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen
from sl1fw.pages.wait import PageWait

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


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
        self.logger.debug("exposure started")
        self.expo.display.actualPage.showItems(exposure = etime)
        whitePixels = self.expo.screen.blitImg(second = second)

        if self.expo.hwConfig.blinkExposure:
            if self.expo.calibAreas:
                etime = 1000 * (exposureTime + self.expo.calibAreas[-1]['time'] - self.expo.calibAreas[0]['time'])
                self.expo.hw.uvLed(True, etime)

                for area in self.expo.calibAreas:
                    while etime > 1000 * (self.expo.calibAreas[-1]['time'] - area['time']):
                        sleep(0.005)
                        UVIsOn, etime = self.expo.hw.getUvLedState()
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
        pageWait = PageWait(self.expo.display, line1 = _("Going to the top position"))
        pageWait.show()
        self.expo.hw.setTowerProfile('homingFast')
        self.expo.hw.towerToTop()
        while not self.expo.hw.isTowerOnTop():
            sleep(0.25)
            pageWait.showItems(line2 = self.expo.hw.getTowerPosition())
        #endwhile
        pageWait.showItems(line2 = "")

        for sec in range(self.expo.hwConfig.upAndDownWait):
            cnt = self.expo.hwConfig.upAndDownWait - sec
            pageWait.showItems(line1 = ngettext("Printing will continue in %d second",
                "Printing will continue in %d seconds", cnt) % cnt, line2 = "")
            sleep(1)
            if self.expo.hwConfig.coverCheck and not self.expo.hw.isCoverClosed():
                pageWait.showItems(line1 = _("Paused"),
                    line2 = _("Close the cover to continue"))
                while not self.expo.hw.isCoverClosed():
                    sleep(1)
                #endwhile
            #endif
        #endfor

        if self.expo.hwConfig.tilt:
            pageWait.showItems(line1 = _("Stirring the resin"), line2 = "")
            self.expo.hw.stirResin()
        #endif
        pageWait.showItems(line1 = _("Going back"), line2 = "")
        self.expo.position += self.expo.hwConfig.upAndDownZoffset
        if self.expo.position < 0:
            self.expo.position = 0
        #endif
        self.expo.hw.towerMoveAbsolute(self.expo.position)
        while not self.expo.hw.isTowerOnPosition():
            sleep(0.25)
            pageWait.showItems(line2 = self.expo.hw.getTowerPosition())
        #endwhile
        self.expo.hw.setTowerProfile('layer')
        self.expo.hw.powerLed("normal")
        self.expo.display.forcePage("print")
    #endif


    def doWait(self, beep = False):
        command = None
        breakFree = set(("exit", "back", "continue"))
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
        self.expo.hw.powerLed("error")
        self.expo.hw.towerHoldTiltRelease()
        self.expo.display.pages['confirm'].setParams(
            continueFce = self.expo.doContinue,
            backFce = self.expo.doBack,
            beep = True,
            text = _("The printer got stuck and needs user assistance.\n\n"
                "Release the tank mechanism and press Continue.\n\n"
                "If you don't want to continue, press the Back button on top of the screen and the current job will be canceled."))
        self.expo.display.forcePage("confirm")
        if self.doWait(True) == "back":
            return False
        #endif

        self.expo.hw.powerLed("warn")
        pageWait = PageWait(self.expo.display, line1 = _("Setting start positions"))
        pageWait.show()

        if not self.expo.hw.tiltSyncWait(retries = 1):
            self.logger.error("Stuck release failed")
            self.expo.display.pages['error'].setParams(
                    backFce = self.expo.doBack,
                    text = _("Tilt homing failed!\n\n"
                        "Check the printer's hardware.\n\n"
                        "The print job was canceled."))
            self.expo.display.forcePage("error")
            self.doWait(True)
            return False
        #endif

        pageWait.showItems(line1 = _("Stirring the resin"))
        self.expo.hw.stirResin()
        self.expo.hw.powerLed("normal")
        self.expo.display.forcePage("print")
        return True
    #enddef


    def run(self):
        #self.logger.debug("thread started")
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

                if command in ("feedme", "feedmeByButton"):
                    self.expo.hw.powerLed("warn")
                    if self.expo.hwConfig.tilt:
                        self.expo.hw.tiltLayerUpWait()
                    #endif
                    if command == "feedme":
                        reason = _("Resin level low!")
                        beep = True
                    else:
                        reason = _("Manual resin refill")
                        beep = False
                    #endif
                    self.expo.display.pages['feedme'].showItems(text = _("%s\n\n"
                        "Please refill the tank up to the 100 %% mark and press Done.\n\n"
                        "If you don't want to refill, please press the Back button on top of the screen.""") % reason)
                    self.expo.display.forcePage("feedme")
                    self.doWait(beep)

                    if self.expo.hwConfig.tilt:
                        pageWait = PageWait(self.expo.display, line1 = _("Stirring the resin"))
                        pageWait.show()
                        self.expo.hw.setTiltProfile('homingFast')
                        self.expo.hw.tiltDownWait()
                        self.expo.hw.stirResin()
                    #endif
                    wasStirring = True
                    self.expo.hw.powerLed("normal")
                    self.expo.display.forcePage("print")
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
                pageWait = PageWait(self.expo.display, line1 = _("Moving platform to the top"))
                pageWait.show()

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

            self.expo.display.forcePage("finished")

        except Exception as e:
            self.logger.exception("run() exception:")

            self.expo.display.pages['error'].setParams(
                backFce=lambda: "home",
                text=_(
                    "Print failed due to an unexpected error\n"
                    "\n"
                    "Please follow the instructions in Chapter 3.1 in the handbook to learn how "
                    "to save a log file. Please send the log to us and help us improve the  printer.\n"
                    "\n"
                    "Thank you!"
                ))
            self.expo.display.forcePage("error")
        #endtry

        #self.logger.debug("thread ended")
    #enddef

#endclass


class Exposure:

    def __init__(self, hwConfig: HwConfig, display: Display, hw: Hardware, screen: Screen):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.project: Optional[Project] = None
        self.display = display
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
        self.expoThread = None
        self.slowLayers = 0
        self.totalHeight = None
        self.printStartTime = 0
        self.printTime = 0
    #enddef


    def setProject(self, project_filename):
        self.project = Project(self.hwConfig)
        return self.project.read(project_filename)
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
        self.expoCommands.put("updown")
    #enddef


    def doExitPrint(self):
        self.expoCommands.put("exit")
    #enddef


    def doFeedMe(self):
        self.expoCommands.put("feedme")
    #enddef


    def doFeedMeByButton(self):
        self.expoCommands.put("feedmeByButton")
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
