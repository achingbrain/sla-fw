#!/usr/bin/env python2

import os
from time import sleep

import logging
logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

import defines

import libConfig
hwConfig = libConfig.HwConfig(defines.hwConfigFile)
config = libConfig.PrintConfig(hwConfig)

from libHardware import Hardware
hw = Hardware(hwConfig, config)

from libWeb import WebDisplay
webdisplay = WebDisplay(hwConfig, hw)
devices = list((webdisplay,))

from libDisplay import Display
display = Display(hwConfig, config, devices, None, None, None, None)

sleep(5)

actualPage = display.setPage("print")
actualPage.showItems({ "timeremain" : "99:60", "timeelaps" : "99:60", "line1" : "Layer: 9999/9999", "line2" : "Height: 150.050/151.000 mm", "percent" : "0%", "progress" : 0, })

sleep(5)

for i in xrange(101):
    actualPage.showItems({ "percent" : "%d%%" % i, "progress" : i })
    sleep(0.25)
#endfor

sleep(5)

lines = { "line1" : "FIRMWARE FAILURE - Something went wrong!", }
lines.update({
    "line2" : "Please send the contents of %s/log" % "255.255.255.255",
    "line3" : "to info@futur3d.net - Thank you",
    })
display.page_exception.setParams(**lines)
display.setPage("exception")

#sleep(100)

#display.doMenu("admin")
#display.doMenu("home")

#actualPage = display.setPage("controlhw")
#actualPage.showItems({ "signal1" : 1, "signal2" : 0, "signal3" : 1, "signal4" : 0, "signal5" : 1, "temp1" : "CPU temp: 22.5", "temp2" : "LED temp: 32.5", })


#actualPage = display.setPage("patterns")

sleep(10)

