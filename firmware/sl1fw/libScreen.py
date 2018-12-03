# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
import threading, Queue
import pygame.display
import pygame.image
import pygame.mouse
import pygame.surfarray
import pygame.font
import numpy
import zipfile
from cStringIO import StringIO

class ImagePreloader(threading.Thread):

    def __init__(self, source, overlays, workQueue, resultQueue):
        super(ImagePreloader, self).__init__()
        self.logger = logging.getLogger(__name__)
        try:
            self.zf = zipfile.ZipFile(source, 'r')
        except Exception as e:
            self.logger.exception("zip read exception:")
        #endif
        self.overlays = overlays
        self.workQueue = workQueue
        self.resultQueue = resultQueue
        self.stoprequest = threading.Event()
    #enddef

    def run(self):
        #self.logger.debug("thread started")
        while not self.stoprequest.isSet():
            try:
                (filename, overlay) = self.workQueue.get(timeout = 0.1)
                #self.logger.debug("preload of %s started", filename)
                filedata = self.zf.read(filename)
                filedata_io = StringIO(filedata)
                obr = pygame.image.load(filedata_io, filename).convert()
                if self.overlays is not None and overlay is not None:
                    obr.blit(self.overlays[overlay], (0,0))
                #endif
                #self.logger.debug("pixelcount of %s started", filename)
                pixels = pygame.surfarray.pixels3d(obr)
                hist = numpy.histogram(pixels, [0, 51, 102, 153, 204, 255])
                del pixels
                whitePixels = (hist[0][1] * 0.25 + hist[0][2] * 0.5 + hist[0][3] * 0.75 + hist[0][4]) / 3
                #self.logger.debug("pixelcount of %s done, whitePixels: %f", filename, whitePixels)
                self.resultQueue.put((obr, whitePixels))
                #self.logger.debug("preload of %s done", filename)
            except Queue.Empty:
                continue
            except Exception:
                self.logger.exception("ImagePreloader exception")
                self.resultQueue.put((None, None, None))
                break
            #endtry
        #endwhile
        self.zf.close()
        #self.logger.debug("thread ended")
    #enddef

    def join(self, timeout = None):
        self.stoprequest.set()
        super(ImagePreloader, self).join(timeout)
    #enddef

#endclass


class Screen(object):

    def __init__(self, hwConfig, source):
        #self.logger = logging.getLogger(__name__)
        os.environ['SDL_NOMOUSE'] = '1'
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
        self.screen.set_alpha(None)
        pygame.mouse.set_visible(False)
        self.getImgBlack()
        self.font = pygame.font.SysFont(None, int(5 / hwConfig.pixelSize))
        self.basepath = source
        di = pygame.display.Info()
        self.width = di.current_w
        self.height = di.current_h
        #self.logger.debug("screen size is %dx%d pixels", self.width, self.height)
        self.calibOverlays = None
        self.imagePreloaderStarted = False
    #enddef

    def __del__(self):
        self.exit()
    #enddef

    def exit(self):
        if self.imagePreloaderStarted:
            self.imagePreloader.join()
        #endif
        pygame.quit()
    #enddef

    def startPreloader(self):
        self.workQueue = Queue.Queue()
        self.resultQueue = Queue.Queue()
        self.imagePreloader = ImagePreloader(self.basepath, self.calibOverlays, self.workQueue, self.resultQueue)
        self.imagePreloader.start()
        self.imagePreloaderStarted = True
    #enddef

    def getImgBlack(self):
        self.screen.fill((0,0,0))
        pygame.display.flip()
    #enddef

    def fillArea(self, area, color = (0,0,0)):
        pygame.display.update(self.screen.fill(color, area))
    #enddef

    def getImg(self, filename, base = None):
        # obrazky jsou rozbalene nebo zkopirovane do ramdisku
        if base is None:
            base = self.basepath
        #endif
        #self.logger.debug("view of %s started", base + filename)
        obr = pygame.image.load(os.path.join(base, filename)).convert()
        self.screen.blit(obr, (0,0))
        pygame.display.flip()
        #self.logger.debug("view of %s done", base + filename)
    #enddef

    def preloadImg(self, filename, drawOverlay):
        self.workQueue.put((filename, drawOverlay))
    #enddef

    def blitImg(self):
        (obr, whitePixels) = self.resultQueue.get()
        if obr is None:
            raise Exception("ImagePreloader exception")
        #endif

        #self.logger.debug("blit started")
        self.screen.blit(obr, (0,0))
        pygame.display.flip()
        #self.logger.debug("blit done")
        return whitePixels
    #enddef

    def inverse(self):
        pixels = pygame.surfarray.pixels3d(self.screen)
        pixels ^= 2 ** 32 - 1
        del pixels
        pygame.display.flip()
    #enddef

    def createCalibrationOverlay(self, areas, baseTime, timeStep):
        self.calibOverlays = list()
        self.calibOverlays.append(pygame.Surface((self.width, self.height), pygame.SRCALPHA).convert_alpha())
        self.calibOverlays.append(pygame.Surface((self.width, self.height), pygame.SRCALPHA).convert_alpha())
        spacingX = 1.5
        spacingY = 1.5
        for area in areas:
            text = "%.2f" % baseTime
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
            self.calibOverlays[0].fill((255,255,255), ((startX, startY), (padX, padY)))
            self.calibOverlays[1].blit(surf, (startX + ofsetX, startY + ofsetY))
            baseTime += timeStep
        #endfor
    #enddef

    def testBlit(self):
        obr = pygame.image.load("zaba.png").convert()
        self.screen.blit(obr, (0,0))
        self.screen.blit(self.calibOverlays[0], (0,0))
        self.screen.blit(self.calibOverlays[1], (0,0))
        pygame.display.flip()
    #enddef

#endclass
