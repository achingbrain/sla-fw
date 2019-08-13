#!/usr/bin/env python3

import os, sys
from time import sleep
import logging
from sl1fw import defines
from sl1fw import libConfig
from sl1fw.libScreen import Screen

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.INFO)
hwConfig = libConfig.HwConfig(defines.hwConfigFile)
screen = Screen(hwConfig)

screen.testBlit(filename = sys.argv[1])

sleep(2)
