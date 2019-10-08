#!/usr/bin/env python2

import logging
import sys

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

sys.path.append("..")
from sl1fw.libUvLedMeter import UvLedMeter

uvmeter = UvLedMeter()

if uvmeter.connect():
    uvmeter.read()
    data = uvmeter.getData()
    logging.info("Arithmetic mean: %.1f", data['uvMean'])
    logging.info("Standard deviation: %.1f", data['uvStdDev'])
    logging.info("Teperature: %.1f", data['uvTemperature'])
    logging.info("Values: %s", ", ".join([str(x) for x in data['uvSensorData']]))
    logging.info("MinValue: %d", data['uvMinValue'])
    logging.info("MaxValue: %d", data['uvMaxValue'])
    logging.info("Differences: %s", ", ".join([str(x) + " %" for x in data['uvPercDiff']]))

    uvmeter.savePic(800, 400, "Test 128", "test.png")

else:
    logging.error("Connect to UV meter failed")
#endif
