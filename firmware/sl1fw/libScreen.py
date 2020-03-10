# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-branches
# pylint: disable=too-many-locals
# pylint: disable=too-many-statements

import logging
import multiprocessing
import os
import signal
import subprocess
from pathlib import Path
from queue import Empty
from time import time

import numpy
from PIL import Image, ImageDraw, ImageFont, ImageOps

from sl1fw import defines
from sl1fw.libConfig import HwConfig
from sl1fw.errors.exceptions import ConfigException
from sl1fw.project.project import Project, ProjectState
from sl1fw.project.functions import get_white_pixels


class ScreenServer(multiprocessing.Process):

    def __init__(self, commands, results):
        super(ScreenServer, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.results = results
        self.stoprequest = multiprocessing.Event()
        self.width = defines.screenWidth
        self.height = defines.screenHeight
        if not defines.testing:
            subprocess.call(['/usr/sbin/fbset', '-fb', defines.fbFile, '%dx%d-0' % (self.width, self.height)])
        #endif
        self.blackImage = Image.new("L", (self.width, self.height))
        self.whiteImage = Image.new("L", (self.width, self.height), 255)
        self.getImgBlack()
        self.overlays = dict()
        self.project = None
        self.perPartes = False
        self.nextImage1 = None
        self.nextImage2 = None
        self.pasteData = None
        self.usage = None
        self.screen = None
        self.whitePixels = None
    #enddef


    def signalHandler(self, _signum, _frame):
        self.logger.debug("signal received")
        self.stoprequest.set()
    #enddef


    def join(self, timeout = None):
        self.stoprequest.set()
        super(ScreenServer, self).join(timeout)
    #enddef


    def run(self):
        self.logger.debug("Screen server process started with PID: %d", os.getpid())
        signal.signal(signal.SIGTERM, self.signalHandler)

        while not self.stoprequest.is_set():
            result = False
            try:
                commandData = self.commands.get(timeout = 0.1)
                fce = commandData.pop("fce", None)
                if fce:
                    method = getattr(self, fce, None)
                    if method:
                        result = method(**commandData)
                    else:
                        self.logger.error("There is no fce '%s'", fce)
                    #endif
                else:
                    self.logger.error("Message with no 'fce' field")
                #endif
            except Empty:
                continue
            except Exception:
                self.logger.exception("ScreenServer exception")
                continue
            #endtry
            if result is not None:
                self.results.put(result)
            #enddef
        #endwhile

        self.logger.debug("process ended")
    #enddef


    def _writefb(self):
        with open(defines.fbFile, 'wb') as fb:
            fb.write(self.screen.convert("RGBX").tobytes())
        #endwith
#        self.screen.show()
    #enddef


    def _openImage(self, filename):
        self.logger.debug("loading '%s'", filename)
        img = Image.open(filename)
        if img.mode != "L":
            self.logger.warning("Image '%s' is in '%s' mode, should be 'L' (grayscale without alpha)."
                                " Losing time in conversion.",
                                filename, img.mode)
            img = img.convert("L")
        #endif
        return img
    #enddef


    def startProject(self, params):
        self.overlays = dict()
        self.perPartes = False
        self.nextImage1 = None
        self.nextImage2 = None
        self.pasteData = None
        self.usage = numpy.zeros((defines.displayUsageSize[0], defines.displayUsageSize[2]))
        hwConfig = HwConfig(file_path=Path(defines.hwConfigFile), factory_file_path=Path(defines.hwConfigFactoryDefaultsFile))
        try:
            hwConfig.read_file()
        except ConfigException:
            self.logger.warning("Failed to read configuration file", exc_info=True)
        #endtry
        self.project = Project(hwConfig)
        if self.project.read(params['project']) != ProjectState.OK:
            self.project = None
            return
        #endif

        # "patch" project with possibly changed values
        self.project.expTime = params['expTime']
        self.project.expTimeFirst = params['expTimeFirst']
        self.project.calibrateTime = params['calibrateTime']

        # for unitttests only
        overlay = params.get('overlayName', "calibPad")
        per_partes_forced = params.get('perPartes', False)

        if hwConfig.perPartes or per_partes_forced:
            try:
                self.overlays['ppm1'] = self._openImage(defines.perPartesMask)
                self.overlays['ppm2'] = ImageOps.invert(self.overlays['ppm1'])
                self.perPartes = True
            except Exception:
                self.logger.exception("per partes masks exception")
            #endtry
        #endif

        try:
            img = self.project.read_image(defines.maskFilename)
            self.overlays['mask'] = ImageOps.invert(img)
        except KeyError:
            self.logger.info("No mask picture in the project")
        except Exception:
            self.logger.exception("project mask exception")
        #endtry

        if self.project.calibrateAreas:
            self.createCalibrationOverlays()
        #endif

        self.preloadImg(self.project.to_print[0], overlay, hwConfig.whitePixelsThd)
    #enddef


    def projectStatus(self):
        return self.project is not None, self.perPartes
    #enddef


    def getImgBlack(self):
        self.screen = self.blackImage.copy()
        self._writefb()
    #enddef


    def fillArea(self, area, color = 0):
        surf = ImageDraw.Draw(self.screen)
        surf.rectangle((area['x'], area['y'], area['x'] + area['w'], area['y'] + area['h']), color)
        self._writefb()
    #enddef


    # FIXME not used, delete?
    def fillAreaPerc(self, area, color):
        self.logger.debug("area: %s", str(area))
        areaPixels = {}
        areaPixels['x'] = self._calcPixels(area['x'], self.width)
        areaPixels['y'] = self._calcPixels(area['y'], self.height)
        areaPixels['w'] = self._calcPixels(area['w'], self.width)
        areaPixels['h'] = self._calcPixels(area['h'], self.height)
        self.logger.debug("areaPixels: %s", str(areaPixels))
        self.fillArea(areaPixels, color)
    #enddef


    @staticmethod
    def _calcPixels(perc, whole):
        return int((perc * whole) / 100)
    #enddef


    def getImg(self, filename):
        self.logger.debug("view of %s started", filename)
        startTime = time()
        self.screen = self._openImage(filename)
        self._writefb()
        self.logger.debug("view of %s done in %f secs", filename, time() - startTime)
    #enddef


    def preloadImg(self, filename, overlayName, whitePixelsThd):
        if self.nextImage2:
            self.logger.debug("second part of image exist - no preloading")
            return
        #endif

        try:
            self.logger.debug("preload of %s started", filename)

            startTimeFirst = time()
            temp = self.project.read_image(filename)
            self.logger.debug("load of '%s' done in %f secs", filename, time() - startTimeFirst)

            if self.pasteData:
                startTime = time()
                crop = temp.crop(self.pasteData['src'])
                self.nextImage1 = self.blackImage.copy()
                for area in self.pasteData['dest']:
                    self.nextImage1.paste(crop, area)
                #endfor
                self.logger.debug("multiplying done in %f secs", time() - startTime)
            else:
                self.nextImage1 = temp
            #endif

            overlay = self.overlays.get(overlayName, None)
            if overlay:
                self.nextImage1.paste(self.whiteImage, overlay)
            #endif
            overlay = self.overlays.get('mask', None)
            if overlay:
                self.nextImage1.paste(self.blackImage, overlay)
            #endif

            startTime = time()
            pixels = numpy.array(self.nextImage1)
            # 1500 layers on 0.1 mm layer height <0:255> -> <0.0:1.0>
            self.usage += numpy.reshape(pixels, defines.displayUsageSize).mean(axis=3).mean(axis=1) / 382500
            self.whitePixels = get_white_pixels(self.nextImage1)
            self.logger.debug("pixels manipulations done in %f secs, whitePixels: %d", time() - startTime, self.whitePixels)

            if self.perPartes and self.whitePixels > whitePixelsThd:
                self.nextImage2 = self.nextImage1.copy()
                self.nextImage1.paste(self.blackImage, self.overlays['ppm1'])
                self.nextImage2.paste(self.blackImage, self.overlays['ppm2'])
            else:
                self.nextImage2 = None
            #endif

            self.logger.debug("preload of %s done in %f secs", filename, time() - startTimeFirst)
        except Exception:
            self.logger.exception("preload exception:")
        #endtry
    #enddef


    def blitImg(self, second = False):
        startTime = time()
        self.logger.debug("blit started")
        if second:
            self.screen = self.nextImage2
            self.nextImage2 = None
        else:
            self.screen = self.nextImage1
            self.nextImage1 = None
        #endif
        self._writefb()
        self.logger.debug("blit done in %f secs", time() - startTime)
        return self.whitePixels
    #enddef


    def screenshot(self, second):
        image = self.nextImage2 if second else self.nextImage1
        if image:
            try:
                startTime = time()
                preview = image.resize(defines.livePreviewSize, Image.BICUBIC)
                self.logger.debug("resize done in %f secs", time() - startTime)
                startTime = time()
                preview.save(defines.livePreviewImage + "-tmp.png")
                self.logger.debug("screenshot done in %f secs", time() - startTime)
            except Exception:
                self.logger.exception("screenshot exception:")
            #endtry
        else:
            self.logger.warning("try to shot epmty image %d", 2 if second else 1)
        #endif
    #enddef


    def screenshotRename(self):
        startTime = time()
        try:
            os.rename(defines.livePreviewImage + "-tmp.png", defines.livePreviewImage)
        except Exception:
            self.logger.exception("screenshotRename exception:")
        #endtry
        self.logger.debug("rename done in %f secs", time() - startTime)
    #enddef


    def inverse(self):
        self.logger.debug("inverse started")
        startTime = time()
        self.screen = ImageOps.invert(self.screen)
        self._writefb()
        self.logger.debug("inverse done in %f secs", time() - startTime)
    #enddef


    def createCalibrationOverlays(self):
        calib = Image.new("L", (self.width, self.height))
        calibPad = Image.new("L", (self.width, self.height))
        calibPadDraw = ImageDraw.Draw(calibPad)
        penetration = self.project.calibratePenetration
        calibAreas = self.project.calibrateAreas
        firstbbox = self.project.firsLayerBBox
        maxbbox = self.project.calibrateBBox
        spacing = 2 * self.project.calibratePadSpacing
        font = ImageFont.truetype(defines.fontFile, self.project.calibrateTextSize)
        projSize = list((maxbbox[2] - maxbbox[0], maxbbox[3] - maxbbox[1]))
        self.logger.debug("max bbox: %s  project size: %s", maxbbox, projSize)
        firstPadding = list((firstbbox[0] - maxbbox[0], firstbbox[1] - maxbbox[1], maxbbox[2] - firstbbox[2], maxbbox[3] - firstbbox[3]))
        self.logger.debug("first bbox: %s  padding: %s", firstbbox, firstPadding)
        areaSize = calibAreas[0]['rect']

        if areaSize['w'] < projSize[0]:
            shrink = (projSize[0] - areaSize['w']) // 2
            self.logger.debug("shrink l: %d", shrink)
            maxbbox[0] += shrink
            maxbbox[2] -= shrink
            firstPadding[0] -= shrink
            firstPadding[2] -= shrink
            if firstPadding[0] < 0:
                firstbbox[0] -= firstPadding[0]
                firstPadding[0] = 0
            #endif
            if firstPadding[2] < 0:
                firstbbox[2] += firstPadding[2]
                firstPadding[2] = 0
            #endif
        #endif

        if areaSize['h'] < projSize[1]:
            shrink = (projSize[1] - areaSize['h']) // 2
            self.logger.debug("shrink w: %d", shrink)
            maxbbox[1] += shrink
            maxbbox[3] -= shrink
            firstPadding[1] -= shrink
            firstPadding[3] -= shrink
            if firstPadding[1] < 0:
                firstbbox[1] -= firstPadding[1]
                firstPadding[1] = 0
            #endif
            if firstPadding[3] < 0:
                firstbbox[3] += firstPadding[3]
                firstPadding[3] = 0
            #endif
        #endif

        if projSize[0] != maxbbox[2] - maxbbox[0] or projSize[1] != maxbbox[3] - maxbbox[1]:
            self.logger.warning("project size %dx%d was reduced to %dx%d to fit area size %dx%d",
                    projSize[0], projSize[1],
                    maxbbox[2] - maxbbox[0], maxbbox[3] - maxbbox[1],
                    areaSize['w'], areaSize['h'])
            projSize = list((maxbbox[2] - maxbbox[0], maxbbox[3] - maxbbox[1]))
            self.logger.debug("max bbox: %s  project size: %s", maxbbox, projSize)
            self.logger.debug("first bbox: %s  padding: %s", firstbbox, firstPadding)
        #endif
        self.pasteData = { 'src' : maxbbox, 'dest' : list() }

        for area in calibAreas:
            text = "%.1f" % area['time']
            self.logger.debug("text: '%s'", text)
            textSize = font.getsize(text)
            textOffset = font.getoffset(text)
            self.logger.debug("textWidth: %d (offset %d)  textHeight: %d (offset %d)",
                    textSize[0], textOffset[0], textSize[1], textOffset[1])

            padX = textSize[0] + spacing - textOffset[0]
            padY = textSize[1] + spacing - textOffset[1]
            self.logger.debug("padX: %d  padY: %d", padX, padY)

            ofsetX = (padX - textSize[0] - textOffset[0]) // 2
            ofsetY = (padY - textSize[1] - textOffset[1]) // 2
            self.logger.debug("ofsetX: %d  ofsetY: %d", ofsetX, ofsetY)

            areaRect = area['rect']
            if area['stripe']:
                place = 0, areaRect['y'] + (areaRect['h'] - projSize[1]) // 2
            else:
                place = areaRect['x'] + (areaRect['w'] - projSize[0]) // 2, areaRect['y'] + (areaRect['h'] - projSize[1]) // 2
            #endif
            self.logger.debug("placeX: %d  placeY: %d", place[0], place[1])
            self.pasteData['dest'].append(list(place))

            firstSizeX = maxbbox[2] - firstPadding[2] - maxbbox[0] - firstPadding[0]
            if area['stripe']:
                firstSizeY = maxbbox[3] - firstPadding[3] - maxbbox[1] - firstPadding[1]
                startX = firstSizeX - penetration
                startY = areaRect['y'] + (firstSizeY - padX) // 2 + (areaRect['h'] - firstSizeY) // 2
                if startY < 0:
                    startY = 0
                #endif
            else:
                startX = areaRect['x'] + (firstSizeX - padX) // 2 + (areaRect['w'] - firstSizeX) // 2
                startY = place[1] + firstPadding[1] - padY + penetration
                if startY < areaRect['y']:
                    startY = areaRect['y']
                #endif
            #endif
            self.logger.debug("startX: %d  startY: %d", startX, startY)

            tmp = Image.new("L", (padX, padY))  # should be "LA"?
            tmpDraw = ImageDraw.Draw(tmp)
            tmpDraw.text((ofsetX, ofsetY), text, fill = 255, font = font, spacing = 0)
            if area['stripe']:
                tmp = tmp.transpose(Image.ROTATE_270)
                padX, padY = padY, padX
            #endif
            calib.paste(tmp.transpose(Image.FLIP_LEFT_RIGHT), (startX, startY))
            calibPadDraw.rectangle(((startX, startY, startX + padX, startY + padY)), 255)
        #endfor
        self.overlays['calib'] = calib
        self.overlays['calibPad'] = calibPad
    #enddef


    def saveDisplayUsage(self):
        try:
            with numpy.load(defines.displayUsageData) as npzfile:
                savedData = npzfile['display_usage']
                if savedData.shape != ((defines.displayUsageSize[0], defines.displayUsageSize[2])):
                    self.logger.warning("Wrong saved data shape: %s", savedData.shape)
                else:
                    self.usage += savedData
                #endif
            #endwith
        except FileNotFoundError:
            self.logger.warning("File '%s' not found", defines.displayUsageData)
        except Exception:
            self.logger.exception("Load display usage failed")
        #endtry
        numpy.savez_compressed(defines.displayUsageData, display_usage = self.usage)
    #enddef

    @staticmethod
    def ping():
        return "pong"
    #enddef

#endclass


class Screen:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.commands = multiprocessing.Queue()
        self.results = multiprocessing.Queue()
        self.server = ScreenServer(self.commands, self.results)
    #enddef


    def start(self):
        self.server.start()
    #enddef

    @staticmethod
    def cleanup():
        # Remove live preview from last run
        if os.path.exists(defines.livePreviewImage):
            os.remove(defines.livePreviewImage)
        #endif
    #enddef


    def exit(self):
        if self.server.is_alive():
            self.server.join()
        #endif
    #enddef


    def startProject(self, **kwargs):
        kwargs['fce'] = 'startProject'
        self.commands.put(kwargs)
    #enddef


    def projectStatus(self):
        self.commands.put({ 'fce' : "projectStatus" })
        return self.results.get()
    #enddef


    def getImgBlack(self):
        self.commands.put({ 'fce' : "getImgBlack" })
    #enddef


    def fillArea(self, **kwargs):
        kwargs['fce'] = 'fillArea'
        self.commands.put(kwargs)
    #enddef


    # FIXME not used, delete?
    def fillAreaPerc(self, **kwargs):
        kwargs['fce'] = 'fillAreaPerc'
        self.commands.put(kwargs)
    #enddef


    def getImg(self, **kwargs):
        kwargs['fce'] = 'getImg'
        self.commands.put(kwargs)
    #enddef


    def preloadImg(self, **kwargs):
        kwargs['fce'] = 'preloadImg'
        self.commands.put(kwargs)
    #enddef


    def blitImg(self, **kwargs):
        kwargs['fce'] = 'blitImg'
        self.commands.put(kwargs)
        return self.results.get()
    #enddef


    def screenshot(self, **kwargs):
        kwargs['fce'] = 'screenshot'
        self.commands.put(kwargs)
    #enddef


    def screenshotRename(self):
        self.commands.put({ 'fce' : "screenshotRename" })
    #enddef


    def inverse(self):
        self.commands.put({ 'fce' : "inverse" })
    #enddef


    def saveDisplayUsage(self):
        self.commands.put({ 'fce' : "saveDisplayUsage" })
    #enddef


    # for testing
    def ping(self, **kwargs):
        kwargs['fce'] = 'ping'
        self.commands.put(kwargs)
        return self.results.get()
    #enddef

#endclass
