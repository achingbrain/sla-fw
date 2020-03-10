#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=wrong-import-position

import logging
import sys
from time import sleep
from dataclasses import asdict
sys.path.append("..")
from sl1fw.libUvLedMeterMulti import UvLedMeterMulti

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

uvmeterMulti = UvLedMeterMulti()

uvmeter = None
wait = 10
for i in range(0, wait):
    print("Waiting for UV meter (%d/%d)" % (i, wait))
    if uvmeterMulti.present:
        uvmeter = uvmeterMulti
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
    data = uvmeter.getData()
    data.uvFoundPwm = 256
    print("Arithmetic mean: %.1f" % data.uvMean)
    print("Standard deviation: %.1f" % data.uvStdDev)
    print("Teperature: %.1f" % data.uvTemperature)
    print("Values: %s" % data.uvSensorData)
    print("MinValue: %d" % data.uvMinValue)
    print("MaxValue: %d" % data.uvMaxValue)
    print("Differences: %s" % data.uvPercDiff)
    uvmeter.savePic(800, 400, "PWM: %d" % data.uvFoundPwm, "test.png", asdict(data))
#endif
