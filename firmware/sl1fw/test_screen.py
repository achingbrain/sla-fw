#!/usr/bin/env python2

import os
from time import sleep

import logging
logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

import defines

import libConfig

hwConfig = libConfig.HwConfig(defines.hwConfigFile)

logging.debug("before import")

from libScreen import Screen

logging.debug("after import")

screen = Screen(hwConfig)

logging.debug("after init")

areaMap = {
        2 : (2,1),
        4 : (2,2),
        6 : (3,2),
        8 : (4,2),
        9 : (3,3),
        }

divide = areaMap[8]
width, height = screen.getResolution()

if width > height:
    x = 0
    y = 1
else:
    x = 1
    y = 0
#endif

stepW = width / divide[x]
stepH = height / divide[y]

calibAreas = list()
lw = 0
time = 4.0
timeStep = 1.0
for i in xrange(divide[x]):
    lh = 0
    for j in xrange(divide[y]):
        w = (i+1) * stepW
        h = (j+1) * stepH
        logging.debug("%d,%d (%d,%d)", lw, lh, stepW, stepH)
        calibAreas.append(((lw, lh), (stepW, stepH), time))
        time += timeStep
        lh = h
    #endfor
    lw = w
#endfor

screen.createCalibrationOverlay(areas = calibAreas)

screen.openZip(filename = "test.dwz")
screen.createMasks(perPartes = hwConfig.perPartes)

screen.testBlit(filename = "zaba.png", overlayName = 'calibPad')
sleep(5)

lastArea = calibAreas[0]
for area in calibAreas[1:]:
    screen.fillArea(area = (lastArea[0], lastArea[1]))
    logging.debug("blank area")
    sleep(area[2] - lastArea[2])
    lastArea = area
#endfor

screen.getImgBlack()
sleep(1)

screen.testBlit(filename = "zaba.png", overlayName = 'calib')
sleep(5)

screen.getImgBlack()
sleep(1)

screen.testBlit(filename = "zaba.png", overlayName = 'ppm1')
sleep(5)

screen.testBlit(filename = "zaba.png", overlayName = 'ppm2')
sleep(5)

screen.testBlit(filename = "white.png")
sleep(1)
screen.testBlit(filename = "white.png", overlayName = 'mask')
sleep(2)
