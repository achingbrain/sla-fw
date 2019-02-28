#!/usr/bin/env python2

import os
from time import sleep

import logging
logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

from libUvLedMeter import UvLedMeter

uvmeter = UvLedMeter()

if uvmeter.connect():
    uvmeter.read()
    logging.info("Arithmetic mean: %.1f", uvmeter.getMean())
    logging.info("Standard deviation: %.1f", uvmeter.getStdDev())
    logging.info("Teperature: %.1f", uvmeter.getTemp())
    logging.info("Values: %s", ", ".join(map(lambda x: str(x), uvmeter.getValues())))
    logging.info("Differences: %s", ", ".join(map(lambda x: str(x) + " %", uvmeter.getPercDiff())))

    uvmeter.savePic(800, 400, "Test 128", "test.png")

else:
    logging.error("Connect to UV meter failed")
#endif
