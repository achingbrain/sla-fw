# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import sys
import signal
import logging
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

    def __init__(self, hwConfig, commands, results):
        super(ScreenServer, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.commands = commands
        self.results = results
        self.stoprequest = multiprocessing.Event()
        self.perPartes = False
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
        subprocess.call(['/usr/sbin/fbset', '-fb', '/dev/fb0', '1440x2560-0'])
        pygame.init()
        self.screen = pygame.display.set_mode((1440,2560), pygame.FULLSCREEN, 32)
        self.screen.set_alpha(None)
        pygame.mouse.set_visible(False)
        self.getImgBlack()
        self.font = pygame.font.SysFont(None, int(5 / self.hwConfig.pixelSize))
        di = pygame.display.Info()
        self.width = di.current_w
        self.height = di.current_h
        #self.logger.debug("screen size is %dx%d pixels", self.width, self.height)
        self.overlays = dict()
        self.zf = None

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
        with open('/dev/fb0', 'wb') as fb:
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
        try:
            self.zf = zipfile.ZipFile(filename, 'r')
            return True
        except Exception as e:
            self.logger.exception("zip read exception:")
            return False
        #endtry
    #enddef


    def preloadImg(self, filename, overlayName):
        self.logger.debug("preload of %s started", filename)
        filedata = self.zf.read(filename)
        try:
            with open(defines.livePreviewImage, "w") as f:
                f.write(filedata)
            #endwith
        except Exception as e:
            self.logger.exception("live preview exception:")
        #endtry

        filedata_io = StringIO(filedata)
        self.nextImage1 = pygame.image.load(filedata_io, filename).convert()

        self.logger.debug("pixelcount of %s started", filename)
        pixels = pygame.surfarray.pixels3d(self.nextImage1)
        hist = numpy.histogram(pixels, [0, 51, 102, 153, 204, 255])
        del pixels
        self.whitePixels = (hist[0][1] * 0.25 + hist[0][2] * 0.5 + hist[0][3] * 0.75 + hist[0][4]) / 3
        self.logger.debug("pixelcount of %s done, whitePixels: %f", filename, self.whitePixels)

        overlay = self.overlays.get(overlayName, None)
        if overlay:
            self.nextImage1.blit(overlay, (0,0))
        #endif
        overlay = self.overlays.get('mask', None)
        if overlay:
            self.nextImage1.blit(overlay, (0,0))
        #endif
        if self.perPartes and self.whitePixels > self.hwConfig.whitePixelsThd:
            self.nextImage2 = self.nextImage1.copy()
            self.nextImage1.blit(self.overlays['ppm1'], (0,0))
            self.nextImage2.blit(self.overlays['ppm2'], (0,0))
        #endif
        self.logger.debug("preload of %s done", filename)
    #enddef


    def blitImg(self, second = False):
        self.logger.debug("blit started")
        if second:
            self.screen.blit(self.nextImage2, (0,0))
        else:
            self.screen.blit(self.nextImage1, (0,0))
        #endif
        pygame.display.flip()
        self._writefb()
        self.logger.debug("blit done")
        return self.whitePixels
    #enddef


    def inverse(self):
        pixels = pygame.surfarray.pixels3d(self.screen)
        pixels ^= 2 ** 32 - 1
        del pixels
        pygame.display.flip()
        self._writefb()
    #enddef


    def createMasks(self):
        if self.hwConfig.perPartes:
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


    def createCalibrationOverlay(self, areas):
        self.overlays['calibPad'] = pygame.Surface((self.width, self.height), pygame.SRCALPHA).convert_alpha()
        self.overlays['calib'] = pygame.Surface((self.width, self.height), pygame.SRCALPHA).convert_alpha()
        spacingX = 1.5
        spacingY = 1.5
        for area in areas:
            text = "%.2f" % area[2]
            surf = pygame.transform.flip(self.font.render(text, True, (255,255,255)), True, False).convert_alpha()
            rect = surf.get_rect()
            padX = rect.w * spacingX
            padY = rect.h * spacingY
            ofsetX = int((padX - rect.w) / 2)
            ofsetY = int((padY - rect.h) / 2)
            #self.logger.debug("rectW:%d rectH:%d", rect.w, rect.h)
            #self.logger.debug("padX:%d padY:%d", padX, padY)
            #self.logger.debug("ofsetX:%d ofsetY:%d", ofsetX, ofsetY)
            startX = int(area[0][0] + ((area[1][0] - padX) / 2))
            startY = area[0][1]
            #self.logger.debug("startX:%d startY:%d", startX, startY)
            self.overlays['calibPad'].fill((255,255,255), ((startX, startY), (padX, padY)))
            self.overlays['calib'].blit(surf, (startX + ofsetX, startY + ofsetY))
        #endfor
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

    def __init__(self, hwConfig):
        self.logger = logging.getLogger(__name__)
        self.commands = multiprocessing.Queue()
        self.results = multiprocessing.Queue()
        self.server = ScreenServer(hwConfig, self.commands, self.results)
        self.server.start()
    #enddef


    def __del__(self):
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


    def inverse(self):
        self.commands.put({ 'fce' : "inverse" })
    #enddef


    def createMasks(self):
        self.commands.put({ 'fce' : "createMasks" })
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
