#!/usr/bin/env python2

from time import sleep

import logging
logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

import libConfig
hwConfig = libConfig.HwConfig()
config = libConfig.PrintConfig(hwConfig)

from libHardware import Hardware
hw = Hardware(hwConfig, config)

hw.tiltSyncWait()
hw.tiltMoveAbsolute(5300)
while hw.isTiltMoving():
    sleep(0.1)
#endwhile
profile = [1750, 1750, 0, 0, 58, 26, 2100]
result = dict()
for sgt in xrange(10, 30):
    profile[5] = sgt
    sgbd = list()
    hw.mcc.do("!tics", 4)
    hw.mcc.do("!ticf", ' '.join(str(num) for num in profile))
    hw.mcc.do("?ticf")
    hw.mcc.do("!sgbd")
    hw.tiltMoveAbsolute(0)
    while hw.isTiltMoving():
        sgbd.extend(hw.getStallguardBuffer())
        sleep(0.1)
    #endwhile
    if hw.getTiltPositionMicroSteps() == 0:
        avg = sum(sgbd) / float(len(sgbd))
        if 200 < avg < 250:
            result[avg] = ' '.join(str(num) for num in profile)
            
    hw.mcc.do("!tics", 0)
    hw.tiltMoveAbsolute(5300)
    while hw.isTiltMoving():
        sleep(0.1)
    #endwhile
    
print(result)
hw.mcc.do("!motr")
