#!/usr/bin/env python2

from time import sleep
import logging

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

from sl1fw.libConfig import HwConfig
from sl1fw.libHardware import Hardware

hwConfig = HwConfig()
hw = Hardware(hwConfig)

hw.cameraLed(True)

hw.powerLed("normal")
hw.beepRepeat(1)
sleep(20)
hw.powerLed("warn")
hw.beepRepeat(1)
sleep(5)
hw.powerLed("error")
hw.beepRepeat(1)
sleep(5)
hw.shutdown()
hw.beepRepeat(1)

hw.cameraLed(False)
