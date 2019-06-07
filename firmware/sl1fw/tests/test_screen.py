#!/usr/bin/env python2

import os
from time import sleep
import gettext
import unittest

gettext.install('sl1fw', 'locales')

import logging
logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)


from sl1fw import defines
from sl1fw import libConfig


class TestScreen(unittest.TestCase):
    PROJECT = os.path.join(os.path.dirname(__file__), "samples/empty-sample.sl1")
    FBDEV = "test.fbdev"

    def setUp(self):
        self.hwConfig = libConfig.HwConfig(defines.hwConfigFile)
        logging.debug("before import")
        from sl1fw.libScreen import Screen
        logging.debug("after import")

        self.screen = Screen(self.hwConfig, fbdev=TestScreen.FBDEV, fbset=False)
        logging.debug("after init")

    def tearDown(self):
        try:
            os.remove(TestScreen.FBDEV)
        except:
            pass

    def test_screen(self):
        areaMap = {
                2 : (2,1),
                4 : (2,2),
                6 : (3,2),
                8 : (4,2),
                9 : (3,3),
                }

        divide = areaMap[9]
        width, height = self.screen.getResolution()

        if width > height:
            x = 0
            y = 1
        else:
            x = 1
            y = 0
        #endif

        stepW = width // divide[x]
        stepH = height // divide[y]

        calibAreas = list()
        lw = 0
        time = 4.0
        timeStep = 1.0
        for i in range(divide[x]):
            lh = 0
            for j in range(divide[y]):
                w = (i+1) * stepW
                h = (j+1) * stepH
                logging.debug("%d,%d (%d,%d)", lw, lh, stepW, stepH)
                calibAreas.append(((lw, lh), (stepW, stepH), time))
                time += timeStep
                lh = h
            #endfor
            lw = w
        #endfor

        file = "empty-sample00000.png"

        self.screen.openZip(filename = TestScreen.PROJECT)
        self.screen.createMasks(perPartes = self.hwConfig.perPartes)
        self.screen.createCalibrationOverlay(areas = calibAreas, filename = file, penetration = 0.5 / self.hwConfig.pixelSize)
        self.screen.preloadImg(filename = file, overlayName = 'calibPad', whitePixelsThd = 50)
        self.screen.blitImg()

        #screen.testBlit(filename = file, overlayName = 'calibPad')
        #sleep(5)
        #
        #lastArea = calibAreas[0]
        #for area in calibAreas[1:]:
        #    screen.fillArea(area = (lastArea[0], lastArea[1]))
        #    logging.debug("blank area")
        #    sleep(area[2] - lastArea[2])
        #    lastArea = area
        ##endfor
        #
        #screen.getImgBlack()
        #sleep(1)
        #
        #screen.testBlit(filename = "zaba.png", overlayName = 'calib')
        #sleep(5)
        #
        #screen.getImgBlack()
        #sleep(1)
        #
        #screen.testBlit(filename = "zaba.png", overlayName = 'ppm1')
        #sleep(5)
        #
        #screen.testBlit(filename = "zaba.png", overlayName = 'ppm2')
        #sleep(5)
        #
        #screen.testBlit(filename = "white.png")
        #sleep(1)
        #screen.testBlit(filename = "white.png", overlayName = 'mask')
        #sleep(2)

if __name__ == '__main__':
    unittest.main()
