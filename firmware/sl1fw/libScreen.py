# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import signal
import logging
from time import time
import multiprocessing
from queue import Empty
from io import BytesIO
import subprocess
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps
import numpy

from sl1fw import defines


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
        self.font = ImageFont.truetype(defines.fontFile, int(5 / defines.screenPixelSize))
        self.overlays = dict()
        self.calibAreas = list()
        self.zf = None
        self.perPartes = False
        self.nextImage1 = None
        self.nextImage2 = None
        self.pasteData = None
        self.mute_warning = False
    #enddef


    def signalHandler(self, signum, frame):
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
            except Exception as e:
                self.logger.exception("ScreenServer exception")
                continue
            #endtry
            if result is not None:
                self.results.put(result)
            #enddef
        #endwhile

        if self.zf:
            self.zf.close()
        #endif

        self.logger.debug("process ended")
    #enddef


    def _writefb(self):
        with open(defines.fbFile, 'wb') as fb:
            fb.write(self.screen.convert("RGBX").tobytes())
        #endwith
#        self.screen.show()
    #enddef


    def _openImage(self, source, filename):
        self.logger.debug("loading '%s'", filename)
        img = Image.open(source)
        if img.mode != "L":
            if not self.mute_warning:
                self.logger.warning("Image '%s' is in '%s' mode, should be 'L' (grayscale without alpha)."
                                    " Losing time in conversion. This is reported only once per project.",
                                    filename, img.mode)
                self.mute_warning = True
            #endif
            img = img.convert("L")
        #endif
        return img
    #enddef


    def startProject(self, params):
        self.overlays = dict()
        self.calibAreas = list()
        self.zf = None
        self.perPartes = False
        self.nextImage1 = None
        self.nextImage2 = None
        self.pasteData = None
        self.mute_warning = False
        self.usage = numpy.zeros((defines.displayUsageSize[0], defines.displayUsageSize[2]))
        try:
            self.zf = zipfile.ZipFile(params['filename'], "r")
        except Exception as e:
            self.logger.exception("zip read exception:")
            return
        #endtry
        self.createMasks(params['perPartes'])
        self.createCalibrationAreas(params['calibrateRegions'], params['expTime'], params['calibrateTime'])
        if self.calibAreas:
            self.createCalibrationOverlays(params['toPrint'], params['calibratePenetration'])
        #endif
        self.preloadImg(params['toPrint'][0], params['overlayName'], params['whitePixelsThd'])
    #enddef


    def projectStatus(self):
        return self.zf is not None, self.perPartes, self.calibAreas
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


    def _calcPixels(self, perc, whole):
        return int((perc * whole) / 100)
    #enddef


    def getImg(self, filename):
        self.logger.debug("view of %s started", filename)
        startTime = time()
        self.screen = self._openImage(filename, filename)
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
            filedata = self.zf.read(filename)
            filedata_io = BytesIO(filedata)
            temp = self._openImage(filedata_io, filename)
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
            hist = numpy.histogram(pixels, [0, 51, 102, 153, 204, 255])
            # 1500 layers on 0.1 mm layer height <0:255> -> <0.0:1.0>
            self.usage += numpy.reshape(pixels, defines.displayUsageSize).mean(axis=3).mean(axis=1) / 382500
            del pixels
            self.whitePixels = (hist[0][1] * 0.25 + hist[0][2] * 0.5 + hist[0][3] * 0.75 + hist[0][4])
            self.logger.debug("pixels manipulations done in %f secs, whitePixels: %f", time() - startTime, self.whitePixels)

            if self.perPartes and self.whitePixels > whitePixelsThd:
                self.nextImage2 = self.nextImage1.copy()
                self.nextImage1.paste(self.blackImage, self.overlays['ppm1'])
                self.nextImage2.paste(self.blackImage, self.overlays['ppm2'])
            else:
                self.nextImage2 = None
            #endif

            self.logger.debug("preload of %s done in %f secs", filename, time() - startTimeFirst)
        except Exception as e:
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
            except Exception as e:
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
        except Exception as e:
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


    def createMasks(self, perPartes):
        if perPartes:
            try:
                self.overlays['ppm1'] = self._openImage(defines.perPartesMask, defines.perPartesMask)
                self.overlays['ppm2'] = ImageOps.invert(self.overlays['ppm1'])
                self.perPartes = True
            except Exception as e:
                self.logger.exception("createMasks exception")
            #endtry
        #endif

        try:
            filedata = self.zf.read(defines.maskFilename)
        except KeyError as e:
            self.logger.info("No mask picture in the project")
            return
        #endtry
        filedata_io = BytesIO(filedata)
        self.overlays['mask'] = ImageOps.invert(self._openImage(filedata_io, defines.maskFilename))
    #enddef


    def createCalibrationAreas(self, regions, baseTime, calibrateTime):
        areaMap = {
                2 : (2, 1),
                4 : (2, 2),
                6 : (3, 2),
                8 : (4, 2),
                9 : (3, 3),
                #10 : (10, 1),  # TODO
                }
        if regions:
            if regions not in areaMap:
                self.logger.warning("bad value regions (%d), calibrate mode disabled", regions)
            else:
                divide = areaMap[regions]

                if self.width > self.height:
                    x = 0
                    y = 1
                else:
                    x = 1
                    y = 0
                #endif

                stepW = self.width // divide[x]
                stepH = self.height // divide[y]

                lw = 0
                etime = baseTime
                for i in range(divide[x]):
                    lh = 0
                    for j in range(divide[y]):
                        w = (i+1) * stepW
                        h = (j+1) * stepH
                        rect = {'x': lw, 'y': lh, 'w': stepW, 'h': stepH}
                        self.logger.debug("%.1f - %s", etime, str(rect))
                        self.calibAreas.append({ 'time' : etime, 'rect' : rect })
                        etime += calibrateTime
                        lh = h
                    #endfor
                    lw = w
                #endfor
            #endif
        #endif
    #enddef


    def createCalibrationOverlays(self, toPrint, penetration):
        calib = Image.new("L", (self.width, self.height))
        calibPad = Image.new("L", (self.width, self.height))
        calibPadDraw = ImageDraw.Draw(calibPad)
        spacingX = 1.5
        spacingY = 1.5

        self.logger.debug("project analyze started")
        startTime = time()
        npArray = numpy.array([], numpy.int32)
        firstbbox = None
        # every second image (it's faster and it should be enough)
        for filename in toPrint[::2]:
            filedata = self.zf.read(filename)
            filedata_io = BytesIO(filedata)
            baseImage = self._openImage(filedata_io, filename)
            bbox = baseImage.getbbox()
            #self.logger.debug("picture bbox: %s", bbox)
            npArray = numpy.append(npArray, bbox)
            if not firstbbox:
                firstbbox = list(bbox)
            #endif
        #endfor
        npArray = numpy.reshape(npArray, (npArray.size//4, 2, 2))
        minval = npArray.min(axis = 0)
        maxval = npArray.max(axis = 0)
        maxbbox = [minval[0][0], minval[0][1], maxval[1][0], maxval[1][1]]
        self.logger.debug("project analyze done in %f secs", time() - startTime)

        projSize = list((maxbbox[2] - maxbbox[0], maxbbox[3] - maxbbox[1]))
        self.logger.debug("max bbox: %s  project size: %s", maxbbox, projSize)
        firstPadding = list((firstbbox[0] - maxbbox[0], firstbbox[1] - maxbbox[1], maxbbox[2] - firstbbox[2], maxbbox[3] - firstbbox[3]))
        self.logger.debug("first bbox: %s  padding: %s", firstbbox, firstPadding)
        areaSize = self.calibAreas[0]['rect']

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

        for area in self.calibAreas:
            text = "%.2f" % area['time']
            self.logger.debug("text: '%s'", text)
            textSize = self.font.getsize(text)
            self.logger.debug("textWidth: %d  textHeight: %d", textSize[0], textSize[1])

            padX = int(textSize[0] * spacingX)
            padY = int(textSize[1] * spacingY)
            self.logger.debug("padX: %d  padY: %d", padX, padY)

            ofsetX = (padX - textSize[0]) // 2
            ofsetY = (padY - textSize[1]) // 2
            self.logger.debug("ofsetX: %d  ofsetY: %d", ofsetX, ofsetY)

            areaRect = area['rect']
            place = areaRect['x'] + (areaRect['w'] - projSize[0]) // 2, areaRect['y'] + (areaRect['h'] - projSize[1]) // 2
            self.logger.debug("placeX: %d  placeY: %d", place[0], place[1])
            self.pasteData['dest'].append(list(place))

            firstSizeX = maxbbox[2] - firstPadding[2] - maxbbox[0] - firstPadding[0]
            startX = areaRect['x'] + (firstSizeX - padX) // 2 + (areaRect['w'] - firstSizeX) // 2
            startY = place[1] + firstPadding[1] - padY + penetration
            if startY < areaRect['y']:
                startY = areaRect['y']
            #endif
            self.logger.debug("startX: %d  startY: %d", startX, startY)

            tmp = Image.new("L", (padX, padY))  # should be "LA"?
            tmpDraw = ImageDraw.Draw(tmp)
            tmpDraw.text((ofsetX, ofsetY), text, fill = 255, font = self.font)
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


    def ping(self):
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


    def cleanup(self):
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
