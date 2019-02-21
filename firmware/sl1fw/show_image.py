#!/usr/bin/env python2

import os, sys
from time import sleep
import logging
import defines
import libConfig
from libScreen import Screen

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.INFO)
hwConfig = libConfig.HwConfig(defines.hwConfigFile)
screen = Screen(hwConfig)

screen.testBlit(filename = sys.argv[1])

sleep(2)
