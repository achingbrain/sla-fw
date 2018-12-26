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

areas = list((
        ((0,0), (720,640)),
        ((0,640), (720,640)),
        ((0,1280), (720,640)),
        ((0,1920), (720,640)),
        ((720,0), (720,640)),
        ((720,640), (720,640)),
        ((720,1280), (720,640)),
        ((720,1920), (720,640))))

screen.createCalibrationOverlay(areas = areas, baseTime = 4, timeStep = 1.25)
screen.openZip(filename = "test.dwz")
screen.createMask()

screen.testBlit(filename = "zaba.png", overlayName = 'calibPad')

sleep(1)
for box in areas:
    sleep(1)
    screen.fillArea(area = box)
#endfor

screen.testBlit(filename = "zaba.png", overlayName = 'calib')
sleep(2)

screen.testBlit(filename = "white.png")
sleep(1)
screen.testBlit(filename = "white.png", overlayName = 'mask')
