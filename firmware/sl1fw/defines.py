# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import os
import glob

swVersion = "Gen3-190-118"
reqMcVersion = "SLA-control 0.9.7-270"

home = "/home/root"

swPath = "/usr/lib/python2.7/site-packages/sl1fw"
dataPath = os.path.join(swPath, "data")
ramdiskPath = "/run/sl1fw"
mediaRootPath = "/run/media/root"
jobCounter = os.path.join(home, "jobs.log")
tiltLoad = os.path.join(home, "tiltLoad")
configDir = "/etc/sl1fw"
hwConfigFileName = "hardware.cfg"
hwConfigFile = os.path.join(configDir, hwConfigFileName)

configFile = "config.ini"
maskFilename = "mask.png"
projectExtension = ".dwz"

scriptDir = "/usr/share/sl1fw/scripts"
usbUpdatePath = "/mnt/rootfs"
usbUpdateCommand = ["/usr/bin/rauc", "install", "/mnt/usb/update.raucb"]
netUpdateCommand = os.path.join(scriptDir, "rsync_net.sh")
netUpdateVersionURL = "http://www.futur3d.net/sl1fw.txt"
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
