# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
import threading, Queue
import shutil
from datetime import datetime
from time import sleep

import defines

import libPages
import libDisplay

class ExposureThread(threading.Thread):

    def __init__(self, commands, expo, filename):
        super(ExposureThread, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.expo = expo

        config = expo.config
        self.calibAreas = None
        areaMap = {
                2 : (2,1),
                4 : (2,2),
                6 : (3,2),
                8 : (4,2),
                9 : (3,3),
                }
        if config.calibrateRegions:
            if config.calibrateRegions not in areaMap:
                self.logger.warning("bad value calibrateRegions (%d), calibrate mode disabled", config.calibrateRegions)
            else:
                divide = areaMap[config.calibrateRegions]

                width, height = self.expo.screen.getResolution()

                if width > height:
                    x = 0
                    y = 1
                else:
                    x = 1
                    y = 0
                #endif

                stepW = width / divide[x]
                stepH = height / divide[y]

                self.calibAreas = list()
                lw = 0
                time = config.expTime
                for i in xrange(divide[x]):
                    lh = 0
                    for j in xrange(divide[y]):
                        w = (i+1) * stepW
                        h = (j+1) * stepH
                        #self.logger.debug("%d,%d (%d,%d)", lw, lh, stepW, stepH)
                        self.calibAreas.append(((lw, lh), (stepW, stepH), time))
                        time += config.calibrateTime
                        lh = h
                    #endfor
                    lw = w
                #endfor

                self.expo.screen.createCalibrationOverlay(areas = self.calibAreas, filename = filename, penetration = config.calibratePenetration)
            #endif
        #endif
    #enddef


    def doFrame(self, picture, position, exposureTime, overlayName, prevWhitePixels, second):

        self.expo.screen.screenshot(second = second)

        if self.expo.hwConfig.tilt:
            if self.expo.hwConfig.layerTowerHop and prevWhitePixels > self.expo.hwConfig.whitePixelsThd:
                self.expo.hw.towerMoveAbsoluteWait(position + self.expo.hwConfig.layerTowerHop)
                self.expo.hw.setTowerProfile('layerMove')
                self.expo.hw.tiltLayerUpWait()
                self.expo.hw.towerMoveAbsoluteWait(position)
                self.expo.hw.setTowerProfile('layer')
            else:
                self.expo.hw.towerMoveAbsoluteWait(position)
                self.expo.hw.tiltLayerUpWait()
            #endif
        else:
            self.expo.hw.setTowerProfile('layer')
            self.expo.hw.towerMoveAbsoluteWait(position + self.expo.hwConfig.layerTowerHop)
            self.expo.hw.towerMoveAbsoluteWait(position)
        #endif
        self.expo.hw.setTowerCurrent(defines.towerHoldCurrent)

        self.expo.screen.screenshotRename()

        if self.expo.hwConfig.delayBeforeExposure:
            sleep(self.expo.hwConfig.delayBeforeExposure / 10.0)
        #endif

        self.logger.debug("exposure started")
        self.expo.display.actualPage.showItems(exposure = exposureTime)
        whitePixels = self.expo.screen.blitImg(second = second)

        if self.expo.hwConfig.blinkExposure:
            if self.calibAreas is not None:
                time = 1000 * (exposureTime + self.calibAreas[-1][2] - self.calibAreas[0][2])
                self.expo.hw.uvLed(True, time)

                for area in self.calibAreas:
                    while time > 1000 * (self.calibAreas[-1][2] - area[2]):
                        sleep(0.005)
                        UVIsOn, time = self.expo.hw.getUvLedState()
                        if not UVIsOn:
                            break
                        #endif
                    #endwhile

                    if not UVIsOn:
                        break
                    #endif

                    self.expo.screen.fillArea(area = (area[0], area[1]))
                    #self.logger.debug("blank area")
                #endfor
            else:
                self.expo.hw.uvLed(True, 1000 * exposureTime)
                UVIsOn = True
                while UVIsOn:
                    sleep(0.1)
                    UVIsOn, time = self.expo.hw.getUvLedState()
                #endwhile
            #endif
        else:
            sleep(exposureTime)
            if self.calibAreas is not None:
                lastArea = self.calibAreas[0]
                for area in self.calibAreas[1:]:
                    self.expo.screen.fillArea(area = (lastArea[0], lastArea[1]))
                    #self.logger.debug("blank area")
                    sleep(area[2] - lastArea[2])
                    lastArea = area
                #endfor
            #endif
        #endif

        self.expo.screen.getImgBlack()
        self.logger.debug("exposure done")

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
            self.expo.hw.setTowerProfile('layer')
            if not self.expo.hw.tiltLayerDownWait(whitePixels):
                self.expo.doPause()
            #endif
        #endif

        return whitePixels
    #enddef


    def doUpAndDown(self):
        actualPosition = self.expo.hw.getTowerPositionMicroSteps()
        self.expo.hw.powerLed("warn")
        if actualPosition is None:
            self.logger.warn("Wrong position from MC")
            pageWait = libPages.PageWait(self.expo.display, line2 = _("Can't get tower position."))
            pageWait.show()
            self.expo.hw.beepAlarm(3)
            sleep(5)
        else:
            pageWait = libPages.PageWait(self.expo.display, line2 = _("Going to top"))
            pageWait.show()
            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)
                pageWait.showItems(line3 = self.expo.hw.getTowerPosition())
            #endwhile
            pageWait.showItems(line3 = "")

            for sec in xrange(self.expo.hwConfig.upAndDownWait):
                pageWait.showItems(line2 = _("Waiting... (%d)") % (self.expo.hwConfig.upAndDownWait - sec))
                sleep(1)
                if self.expo.hwConfig.coverCheck and not self.expo.hw.isCoverClosed():
                    pageWait.showItems(line2 = _("Waiting... (cover is open)"))
                    while not self.expo.hw.isCoverClosed():
                        sleep(1)
                    #endwhile
                #endif
            #endfor

            if self.expo.hwConfig.tilt:
                pageWait.showItems(line2 = _("Resin stirring"), line3 = "")
                self.expo.hw.stirResin()
            #endif
            pageWait.showItems(line2 = _("Going back"), line3 = "")
            self.expo.hw.towerMoveAbsolute(actualPosition)
            while not self.expo.hw.isTowerOnPosition():
                sleep(0.25)
                pageWait.showItems(line3 = self.expo.hw.getTowerPosition())
            #endwhile
        #endif
        self.expo.hw.powerLed("normal")
    #endif


    def doWait(self):
        command = None
        breakFree = set(("exit", "continue"))
        while not command:
            self.expo.hw.beepAlarm(3)
            sleep(1)

            try:
                command = self.commands.get_nowait()
            except Queue.Empty:
                command = None
            except Exception:
                self.logger.exception("getCommand exception")
                command = None
            # endtry

            if command in breakFree:
                break
            # endif
        # endwhile

        return command


    def run(self):
        #self.logger.debug("thread started")
        try:
            config = self.expo.config
            prevWhitePixels = 0
            totalLayers = config.totalLayers

            for i in xrange(totalLayers):

                try:
                    command = self.commands.get_nowait()
                except Queue.Empty:
                    command = None
                except Exception:
                    self.logger.exception("getCommand exception")
                    command = None
                #endtry

                if command == "updown":
                    self.doUpAndDown()
                    self.expo.display.goBack()
                #endif

                if command == "exit":
                    break
                #endif

                if command == "feedme":
                    self.expo.hw.powerLed("warn")
                    self.expo.hw.tiltLayerUpWait()
                    if self.doWait() == "exit":
                        break
                    #endif

                    if self.expo.hwConfig.tilt:
                        pageWait = libPages.PageWait(self.expo.display, line2 = _("Resin stirring"))
                        pageWait.show()
                        self.expo.hw.tiltDownWait()
                        self.expo.hw.stirResin()
                    #endif
                    self.expo.hw.powerLed("normal")
                    self.expo.display.actualPage.show()
                #endif

                if command == "pause":
                    self.doWait()
                #endif

                if self.expo.hwConfig.upAndDownEveryLayer and self.expo.actualLayer and not self.expo.actualLayer % self.expo.hwConfig.upAndDownEveryLayer:
                    self.doUpAndDown()
                    self.expo.display.actualPage.show()
                #endif

                self.expo.hw.checkTemp(self.expo.checkPage, self.expo.display.actualPage)
                self.expo.hw.checkFanStatus(self.expo.checkPage, self.expo.display.actualPage)
                self.expo.hw.checkCoverStatus(self.expo.checkPage, self.expo.display.actualPage)

                # prvni tri vrstvy jsou vzdy s casem config.expTimeFirst
                if i < 3:
                    step = config.layerMicroSteps
                    time = config.expTimeFirst
                # dalsich config.fadeLayers je prechod config.expTimeFirst -> config.expTime
                elif i < config.fadeLayers + 3:
                    step = config.layerMicroSteps
                    # expTimes may be changed during print
                    timeLoss = (config.expTimeFirst - config.expTime) / float(config.fadeLayers)
                    self.logger.debug("timeLoss: %0.3f", timeLoss)
                    time = config.expTimeFirst - (i - 2) * timeLoss
                # do prvniho zlomu standardni parametry
                elif i + 1 < config.slice2:
                    step = config.layerMicroSteps
                    time = config.expTime
                # do druheho zlomu parametry2
                elif i + 1 < config.slice3:
                    step = config.layerMicroSteps2
                    time = config.expTime2
                # a pak uz parametry3
                else:
                    step = config.layerMicroSteps3
                    time = config.expTime3
                #endif

                self.expo.actualLayer = i + 1
                self.expo.position += step
                self.logger.debug("LAYER %04d/%04d (%s)  steps: %d  position: %d  time: %.3f",
                        self.expo.actualLayer, totalLayers, config.toPrint[i], step, self.expo.position, time)

                if i < 2:
                    overlayName = 'calibPad'
                elif i < config.calibrateInfoLayers + 2:
                    overlayName = 'calib'
                else:
                    overlayName = None
                #endif

                whitePixels = self.doFrame(config.toPrint[i+1] if i+1 < totalLayers else None,
                        self.expo.position + self.expo.hwConfig.calibTowerOffset,
                        time,
                        overlayName,
                        prevWhitePixels,
                        False)

                # exposure second part too
                if self.expo.perPartes and whitePixels > self.expo.hwConfig.whitePixelsThd:
                    self.doFrame(config.toPrint[i+1] if i+1 < totalLayers else None,
                            self.expo.position + self.expo.hwConfig.calibTowerOffset,
                            time,
                            overlayName,
                            whitePixels,
                            True)
                #endif

                prevWhitePixels = whitePixels

                # /1000 - we want cm3 (=ml) not mm3
                self.expo.resinCount += whitePixels * self.expo.pixelSize * self.expo.hwConfig.calcMM(step) / 1000
                self.logger.debug("resinCount: %f" % self.expo.resinCount)

                if self.expo.hwConfig.trigger:
                    self.expo.hw.cameraLed(True)
                    sleep(self.expo.hwConfig.trigger / 10.0)
                    self.expo.hw.cameraLed(False)
                #endif

            #endfor

            self.expo.hw.uvLed(False)
            self.expo.hw.beepRepeat(3)
            actualPage = self.expo.display.setPage("print")

            # TODO extra page finalPrint

            self.expo.hw.towerToTop()
            while not self.expo.hw.isTowerOnTop():
                sleep(0.25)
            #endwhile

            #self.logger.debug("thread ended")

        except Exception as e:
            self.logger.exception("run() exception:")
            self.expo.exception = e
        #endtry
    #enddef

#endclass


class Exposure(object):

    def __init__(self, hwConfig, config, display, hw, screen):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.config = config
        self.display = display
        self.hw = hw
        self.screen = screen
        # FIXME test return value!
        self.screen.openZip(filename = self.config.zipName)
        # here ^^^
        self.perPartes = self.screen.createMasks(perPartes = hwConfig.perPartes)
        self.position = 0
        self.actualLayer = 0
        self.checkPage = libPages.PageWait(display)
        self.expoCommands = Queue.Queue()
        self.expoThread = ExposureThread(self.expoCommands, self, self.config.toPrint[0])
        self.screen.preloadImg(
                filename = self.config.toPrint[0],
                overlayName = 'calibPad',
                whitePixelsThd = hwConfig.whitePixelsThd)
        self.exception = None
        self.resinCount = 0.0
        self.resinVolume = None
        self.pixelSize = self.hwConfig.pixelSize ** 2
        self.paused = False
        self.canceled = False
    #enddef


    def start(self):
        self.expoThread.start()
    #enddef


    def inProgress(self):
        return self.expoThread.isAlive()
    #enddef


    def waitDone(self):
        self.expoThread.join()
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


    def doPause(self):
        self.expoCommands.put("pause")
        self.paused = True


    def doContinue(self):
        self.expoCommands.put("continue")
        self.paused = False
    #enddef


    def setResinVolume(self, volume):
        self.resinCount = 0.0
        self.resinVolume = volume
    #enddef

#endclass

