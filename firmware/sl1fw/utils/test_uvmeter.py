#!/usr/bin/env python3

import logging
import sys
from time import sleep
sys.path.append("..")
from sl1fw.libUvLedMeterMulti import UvLedMeterMulti
from sl1fw.libUvLedMeterSingle import UvLedMeterSingle
from sl1fw.pages.uvcalibration import UvCalibrationData

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

uvmeterMulti = UvLedMeterMulti()
uvmeterSingle = UvLedMeterSingle()

uvmeter = None
wait = 10
for i in range(0, wait):
    print("Waiting for UV meter (%d/%d)" % (i, wait))
    if uvmeterMulti.present:
        uvmeter = uvmeterMulti
        break
    elif uvmeterSingle.present:
        uvmeter = uvmeterSingle
        break
    #endif
    sleep(1)
#endfor

if not uvmeter:
    print("UV meter not detected")
elif not uvmeter.connect():
    print("Connect to UV meter failed")
elif not uvmeter.read():
    print("Read data from UV meter failed")
else:
    data = uvmeter.getData(True, UvCalibrationData())
    print("Arithmetic mean: %.1f" % data.uvMean)
    print("Standard deviation: %.1f" % data.uvStdDev)
    print("Teperature: %.1f" % data.uvTemperature)
    print("Values: %s" % data.uvSensorData)
    print("MinValue: %d" % data.uvMinValue)
    print("MaxValue: %d" % data.uvMaxValue)
    print("Differences: %s" % data.uvPercDiff)
#endif
