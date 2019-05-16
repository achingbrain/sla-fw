# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import sys
import signal
import logging
from time import time
import multiprocessing
from Queue import Empty
from cStringIO import StringIO
import subprocess
import zipfile
import lazy_import

lazy_import.lazy_module("pygame")
import pygame
lazy_import.lazy_module("numpy")
import numpy

import defines


class ScreenServer(multiprocessing.Process):

    def __init__(self, commands, results, pixelSize, fbdev, fbset):
        super(ScreenServer, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.results = results
        self.pixelSize = pixelSize
        self.stoprequest = multiprocessing.Event()
        self.fbdev = fbdev
        self.fbset = fbset
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
        self.logger.debug("process started")
        signal.signal(signal.SIGTERM, self.signalHandler)
        os.environ['SDL_NOMOUSE'] = '1'
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        if self.fbset:
            subprocess.call(['/usr/sbin/fbset', '-fb', '/dev/fb0', '1440x2560-0'])
        #endif
        pygame.init()
        self.screen = pygame.display.set_mode((1440,2560), pygame.FULLSCREEN, 32)
        self.screen.set_alpha(None)
        pygame.mouse.set_visible(False)
        self.getImgBlack()
        self.font = pygame.font.SysFont(None, int(5 / self.pixelSize))
        di = pygame.display.Info()
        self.width = di.current_w
        self.height = di.current_h
        #self.logger.debug("screen size is %dx%d pixels", self.width, self.height)
        self.overlays = dict()
        self.zf = None
        self.perPartes = False
        self.nextImage1 = None
        self.nextImage2 = None
        self.resizeSurf = pygame.Surface(defines.livePreviewSize).convert()

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

        pygame.quit()
        self.logger.debug("process ended")
    #enddef


    def _writefb(self):
        with open(self.fbdev, 'wb') as fb:
            fb.write(self.screen.get_buffer())
        #endwith
    #enddef


    def getResolution(self):
        return (self.width, self.height)
    #enddef


    def getImgBlack(self):
        self.screen.fill((0,0,0))
        pygame.display.flip()
        self._writefb()
    #enddef


    def fillArea(self, area):
        pygame.display.update(self.screen.fill((0,0,0), area))
        self._writefb()
    #enddef


    def getImg(self, filename):
        self.logger.debug("view of %s started", filename)
        image = pygame.image.load(filename).convert()
        self.screen.blit(image, (0,0))
        pygame.display.flip()
        self._writefb()
        self.logger.debug("view of %s done", filename)
    #enddef


    def openZip(self, filename):
        self.nextImage1 = None
        self.nextImage2 = None
        try:
            self.zf = zipfile.ZipFile(filename, 'r')
            return True
        except Exception as e:
            self.logger.exception("zip read exception:")
            return False
        #endtry
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
            filedata_io = StringIO(filedata)
            self.nextImage1 = pygame.image.load(filedata_io, filename).convert()
            self.logger.debug("load time: %f secs", time() - startTimeFirst)

            startTime = time()
            pixels = pygame.surfarray.pixels3d(self.nextImage1)
            hist = numpy.histogram(pixels, [0, 51, 102, 153, 204, 255])
            del pixels
            self.whitePixels = (hist[0][1] * 0.25 + hist[0][2] * 0.5 + hist[0][3] * 0.75 + hist[0][4]) / 3
            self.logger.debug("pixelcount time: %f secs, whitePixels: %f", time() - startTime, self.whitePixels)

            overlay = self.overlays.get(overlayName, None)
            if overlay:
                self.nextImage1.blit(overlay, (0,0))
            #endif
            overlay = self.overlays.get('mask', None)
            if overlay:
                self.nextImage1.blit(overlay, (0,0))
            #endif
            if self.perPartes and self.whitePixels > whitePixelsThd:
                self.nextImage2 = self.nextImage1.copy()
                self.nextImage1.blit(self.overlays['ppm1'], (0,0))
                self.nextImage2.blit(self.overlays['ppm2'], (0,0))
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
            self.screen.blit(self.nextImage2, (0,0))
            self.nextImage2 = None
        else:
            self.screen.blit(self.nextImage1, (0,0))
            self.nextImage1 = None
        #endif
        pygame.display.flip()
        self._writefb()
        self.logger.debug("blit done in %f secs", time() - startTime)
        return self.whitePixels
    #enddef


    def screenshot(self, second):
        screen = self.nextImage2 if second else self.nextImage1
        if screen:
            try:
                startTime = time()
                pygame.transform.smoothscale(screen, defines.livePreviewSize, self.resizeSurf)
                self.logger.debug("resize time: %f secs", time() - startTime)
                startTime = time()
                pygame.image.save(self.resizeSurf, defines.livePreviewImage + "-tmp.png")
                self.logger.debug("screenshot time: %f secs", time() - startTime)
            except Exception as e:
                self.logger.exception("screenshot exception:")
            #endtry
        else:
            self.logger.warning("try to shot epmty screen %d", 2 if second else 1)
        #endif
    #enddef


    def screenshotRename(self):
        startTime = time()
        try:
            os.rename(defines.livePreviewImage + "-tmp.png", defines.livePreviewImage)
        except Exception as e:
            self.logger.exception("screenshotRename exception:")
        #endtry
        self.logger.debug("rename time: %f secs", time() - startTime)
    #enddef


    def inverse(self):
        pixels = pygame.surfarray.pixels3d(self.screen)
        pixels ^= 2 ** 32 - 1
        del pixels
        pygame.display.flip()
        self._writefb()
    #enddef


    def createMasks(self, perPartes):
        if perPartes:
            try:
                self.overlays['ppm1'] = pygame.image.load(defines.perPartesMask).convert()
                self.overlays['ppm2'] = self.overlays['ppm1'].copy()
                pixels = pygame.surfarray.pixels3d(self.overlays['ppm2'])
                pixels ^= 2 ** 32 - 1
                del pixels
                self.overlays['ppm1'].set_colorkey((255, 255, 255), pygame.RLEACCEL)
                self.overlays['ppm2'].set_colorkey((255, 255, 255), pygame.RLEACCEL)
                self.perPartes = True
            except Exception as e:
                self.logger.exception("createMasks exception")
            #endtry
        #endif

        try:
            filedata = self.zf.read(defines.maskFilename)
        except KeyError as e:
            self.logger.info("No mask picture in the project")
            return self.perPartes
        #endtry
        filedata_io = StringIO(filedata)
        self.overlays['mask'] = pygame.image.load(filedata_io, defines.maskFilename).convert_alpha()
        return self.perPartes
    #enddef


    def createCalibrationOverlay(self, areas, filename, penetration):
        self.overlays['calibPad'] = pygame.Surface((self.width, self.height), pygame.SRCALPHA).convert_alpha()
        self.overlays['calib'] = pygame.Surface((self.width, self.height), pygame.SRCALPHA).convert_alpha()
        spacingX = 1.5
        spacingY = 1.5

        filedata = self.zf.read(filename)
        filedata_io = StringIO(filedata)
        baseImage = pygame.image.load(filedata_io, filename).convert()
        pixels = pygame.surfarray.pixels3d(baseImage)

        for area in areas:
            text = "%.2f" % area[2]
            surf = pygame.transform.flip(self.font.render(text, True, (255,255,255)), True, False).convert_alpha()
            rect = surf.get_rect()
            #self.logger.debug("rectW:%d rectH:%d", rect.w, rect.h)
            padX = rect.w * spacingX
            padY = rect.h * spacingY
            #self.logger.debug("padX:%d padY:%d", padX, padY)
            ofsetX = int((padX - rect.w) / 2)
            ofsetY = int((padY - rect.h) / 2)
            #self.logger.debug("ofsetX:%d ofsetY:%d", ofsetX, ofsetY)
            lineX = int(area[0][0] + area[1][0] / 2)
            lineY = area[0][1]
            line2Y = area[0][1] + area[1][1] - 1
            #self.logger.debug("lineX:%d lineY:%d-%d", lineX, lineY, line2Y)
            line = pixels[lineX:lineX + 1][0][lineY:line2Y]
            startX = int(area[0][0] + ((area[1][0] - padX) / 2))
            pixpos = line.argmax(axis = 0)[0]
            if pixpos > (padY - penetration):
                startY = area[0][1] + pixpos + penetration - padY
            else:
                startY = area[0][1]
            #endif
            del line
            #self.logger.debug("startX:%d startY:%d", startX, startY)
            self.overlays['calibPad'].fill((255,255,255), ((startX, startY), (padX, padY)))
            self.overlays['calib'].blit(surf, (startX + ofsetX, startY + ofsetY))
        #endfor

        del pixels
    #enddef


    def testBlit(self, filename, overlayName = None):
        image = pygame.image.load(filename).convert()
        self.screen.blit(image, (0,0))
        overlay = self.overlays.get(overlayName, None)
        if overlay:
            self.screen.blit(overlay, (0,0))
        #endif
        pygame.display.flip()
        self._writefb()
    #enddef

#endclass


class Screen(object):

    def __init__(self, hwConfig, fbdev="/dev/fb0", fbset=True):
        self.logger = logging.getLogger(__name__)
        self.commands = multiprocessing.Queue()
        self.results = multiprocessing.Queue()
        self.server = ScreenServer(self.commands, self.results, hwConfig.pixelSize, fbdev, fbset)
        self.server.start()
    #enddef


    def __del__(self):
        self.exit()
    #enddef


    def exit(self):
        self.server.join()
    #enddef

    def getResolution(self):
        self.commands.put({ 'fce' : "getResolution" })
        return self.results.get()
    #enddef


    def getImgBlack(self):
        self.commands.put({ 'fce' : "getImgBlack" })
    #enddef


    def fillArea(self, **kwargs):
        kwargs['fce'] = 'fillArea'
        self.commands.put(kwargs)
    #enddef


    def getImg(self, **kwargs):
        kwargs['fce'] = 'getImg'
        self.commands.put(kwargs)
    #enddef


    def openZip(self, **kwargs):
        kwargs['fce'] = 'openZip'
        self.commands.put(kwargs)
        return self.results.get()
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


    def createMasks(self, **kwargs):
        kwargs['fce'] = 'createMasks'
        self.commands.put(kwargs)
        return self.results.get()
    #enddef


    def createCalibrationOverlay(self, **kwargs):
        kwargs['fce'] = 'createCalibrationOverlay'
        self.commands.put(kwargs)
    #enddef


    def testBlit(self, **kwargs):
        kwargs['fce'] = 'testBlit'
        self.commands.put(kwargs)
    #enddef

#endclass
