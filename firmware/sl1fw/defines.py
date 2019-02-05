# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import glob

swVersion = "Gen3-190-215"
reqMcVersion = "SLA-control 0.9.8-359"

home = "/home/root"

swPath = "/usr/lib/python2.7/site-packages/sl1fw"
dataPath = os.path.join(swPath, "data")
ramdiskPath = "/run/sl1fw"
mediaRootPath = "/run/media/root"
jobCounter = os.path.join(home, "jobs.log")
configDir = "/etc/sl1fw"
hwConfigFileName = "hardware.cfg"
hwConfigFile = os.path.join(configDir, hwConfigFileName)
livePreviewImage = os.path.join(ramdiskPath, "live.png")

perPartesMask = os.path.join(dataPath, "perpartes_mask.png")

configFile = "config.ini"
maskFilename = "mask.png"
projectExtensions = set((".dwz", ".sl1"))

cpuSNFile = "/sys/bus/nvmem/devices/sunxi-sid0/nvmem"
cpuTempFile = "/sys/devices/virtual/thermal/thermal_zone0/temp"

scriptDir = "/usr/share/sl1fw/scripts"
usbUpdatePath = "/mnt/rootfs"
netUpdateCommand = os.path.join(scriptDir, "net_update.sh")
flashMcCommand = os.path.join(scriptDir, "flashMC.sh")
Mc2NetCommand = os.path.join(scriptDir, "MC2Net.sh")
WiFiCommand = os.path.join(scriptDir, "wifi.sh")

webDisplayPort = 16384
qtDisplayPort = 32768
debugPort = 49152
templates = '/srv/http/intranet/templates'

motionControlDevice = "/dev/ttyS2"
socatPort = 8192

wifiSetupURI = ":8080"
wifiSetupFile = "/etc/hostapd.secrets.json"

octoprintURI = ":8000"
octoprintAuthFile = os.path.join(configDir, "slicer-upload-api.key")

resinMinVolume = 50
resinMaxVolume = 200
resinLowWarn = 40
resinFeedWait = 30
resinFilled = 350

towerHoldCurrent = 12
tiltHoldCurrent = 20
tiltCalibCurrent = 40

multimediaRootPath = "/usr/share/sl1fw/multimedia"