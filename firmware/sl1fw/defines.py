# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os

swVersion = "Gen3-190-314"
reqMcVersion = "SLA-control 0.9.8-373i"

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
livePreviewSize = (288, 512)

perPartesMask = os.path.join(dataPath, "perpartes_mask.png")

configFile = "config.ini"
maskFilename = "mask.png"
projectExtensions = set((".dwz", ".sl1"))

cpuSNFile = "/sys/bus/nvmem/devices/sunxi-sid0/nvmem"
cpuTempFile = "/sys/devices/virtual/thermal/thermal_zone0/temp"

scriptDir = "/usr/share/sl1fw/scripts"
usbUpdatePath = "/mnt/rootfs"
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

resinMinVolume = 68.5
resinMaxVolume = 200.0
resinLowWarn = 60
resinFeedWait = 50
resinFilled = 200

defaultTowerHeight = 128    # mm
defaultTiltHeight = 4900    # usteps
towerHoldCurrent = 12
tiltHoldCurrent = 35
tiltCalibCurrent = 40

multimediaRootPath = "/usr/share/sl1fw/multimedia"
manualURL = "https://www.prusa3d.com/SL1handbook-ENG/"
videosURL = "https://www.prusa3d.com/SL1guide/"
aboutURL = "https://www.prusa3d.com/about-us/"
firmwareTempFile = os.path.join(ramdiskPath, "update.raucb")
def _(message): return message
netFirmwares = [
    {'name': _("current"), 'url': "https://www.prusa3d.com/SL1/current.raucb"},
    {'name': _("testing"), 'url': "https://www.prusa3d.com/SL1/testing.raucb"},
    {'name': _("nightly"), 'url': "http://10.24.10.12/images/buildserver-latest.raucb"}
]
del _
internalProjectPath = "/var/sl1fw/projects"
examplesURL = "https://www.prusa3d.com/SL1/examples.tar.gz"
examplesArchivePath = os.path.join(internalProjectPath, 'examples.tar.gz')
