#!/usr/bin/env python2

import os, sys
from time import sleep

import logging
logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

sys.path.append("..")
from libUvLedMeter import UvLedMeter

uvmeter = UvLedMeter()

if uvmeter.connect():
    uvmeter.read()
    data = uvmeter.getData()
    logging.info("Arithmetic mean: %.1f", data['uvMean'])
    logging.info("Standard deviation: %.1f", data['uvStdDev'])
    logging.info("Teperature: %.1f", data['uvTemperature'])
    logging.info("Values: %s", ", ".join(map(lambda x: str(x), data['uvSensorData'])))
    logging.info("MinValue: %d", data['uvMinValue'])
    logging.info("MaxValue: %d", data['uvMaxValue'])
    logging.info("Differences: %s", ", ".join(map(lambda x: str(x) + " %", data['uvPercDiff'])))

    uvmeter.savePic(800, 400, "Test 128", "test.png")

else:
    logging.error("Connect to UV meter failed")
#endif
