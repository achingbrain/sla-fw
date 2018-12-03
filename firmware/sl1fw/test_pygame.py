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

screen = Screen(hwConfig, defines.ramdiskPath)

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

x = 64
for box in areas:
    screen.fillArea(box, x)
    x += 32
#endfor

screen.createCalibrationOverlay(areas, 4, 1.25)
screen.testBlit()
sleep(2)

