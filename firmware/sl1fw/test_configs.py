#!/usr/bin/env python2

import os
from time import sleep

import logging
logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)

import defines

import libConfig

defines.hwConfigFile = "hardware.cfg"

from shutil import copyfile
copyfile(defines.hwConfigFile, "hwconfig.test")

hwConfig = libConfig.HwConfig(defines.hwConfigFile)
hwConfig.logAllItems()
hwConfig.logFile()
hwConfig.getHash()
towerHeight = "1024"
hwConfig.update(towerheight = towerHeight)
hwConfig.logAllItems()
hwConfig.logFile()
hwConfig.getHash()
logging.info(hwConfig.getSourceString())
if not hwConfig.writeFile("hwconfig.test"):
    print "Failed"
#endif

config = libConfig.PrintConfig(hwConfig)
config.logAllItems()
config.logFile()
config.parseFile(os.path.join("../../../../dwarf_projekty/opcik-zetony-1", defines.configFile))
config.logAllItems()
config.logFile()
config.getHash()
logging.info(config.getSourceString())
config.update(upAndDownWait = "5", wifiOn = "0")
#config.writeFile("printconfig.txt")

netConfig = libConfig.NetConfig()
netConfig.parseText("""image = RSL-180-318
firmware = Gen2-180-319""")
netConfig.logAllItems()
netConfig.logFile()

print defines.usbUpdatePath
print defines.swPath

fwConfig = libConfig.FwConfig(os.path.join(defines.usbUpdatePath + defines.swPath, "defines.py"))
fwConfig.logAllItems()
