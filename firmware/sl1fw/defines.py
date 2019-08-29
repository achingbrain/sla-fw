# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import sl1fw

reqMcVersion = "0.11.0"

factoryMountPoint = "/usr/share/factory/defaults"
persistentStorage = "/var/sl1fw"

swPath = os.path.dirname(sl1fw.__file__)
dataPath = os.path.join(swPath, "data")
ramdiskPath = "/run/sl1fw"
mediaRootPath = "/run/media/root"
configDir = "/etc/sl1fw"
hwConfigFileName = "hardware.cfg"
hwConfigFile = os.path.join(configDir, hwConfigFileName)
hwConfigFactoryDefaultsFile = os.path.join(factoryMountPoint, "hardware.toml")
wizardDataFile = os.path.join(factoryMountPoint, "wizardData.cfg")  # TODO cfg->toml
livePreviewImage = os.path.join(ramdiskPath, "live.png")
livePreviewSize = (288, 512)

perPartesMask = os.path.join(dataPath, "perpartes_mask.png")

configFile = "config.ini"
maskFilename = "mask.png"
projectExtensions = set((".dwz", ".sl1"))
lastProjectData = os.path.join(persistentStorage, "last_project.toml")
statsData = os.path.join(persistentStorage, "stats.toml")
serviceData = os.path.join(persistentStorage, "service.toml")

displayUsageSize = (288, 5, 512, 5) # 288 * 5 = 1440; 512 * 5 = 2560
displayUsageData = os.path.join(persistentStorage, "display_usage.npz")
displayUsagePalette = os.path.join(dataPath, "heatmap_palette.txt")

cpuSNFile = "/sys/bus/nvmem/devices/sunxi-sid0/nvmem"
cpuTempFile = "/sys/devices/virtual/thermal/thermal_zone0/temp"

scriptDir = "/usr/share/sl1fw/scripts"
flashMcCommand = os.path.join(scriptDir, "flashMC.sh")
Mc2NetCommand = os.path.join(scriptDir, "MC2Net.sh")

webDisplayPort = 16384
qtDisplayPort = 32768
debugPort = 49152
templates = '/srv/http/intranet/templates'

motionControlDevice = "/dev/ttyS2"
socatPort = 8192

wifiSetupFile = "/etc/hostapd.secrets.json"

octoprintURI = ":8000"
octoprintAuthFile = os.path.join(configDir, "slicer-upload-api.key")

fbFile = "/dev/fb0"
doFBSet = True
truePoweroff = True

resinMinVolume = 68.5
resinMaxVolume = 200.0
resinWizardMinVolume = 50.0
resinWizardMaxVolume = 130.0
resinLowWarn = 60
resinFeedWait = 50
resinFilled = 200

defaultTowerHeight = 120    # mm
defaultTiltHeight = 4928    # usteps rounded to fullstep (phase 0)
defaultTowerOffset = 0.05   # mm
tiltHomingTolerance = 32    # tilt axis check has this tolerance
towerHoldCurrent = 12
tiltHoldCurrent = 35
tiltCalibCurrent = 40
fanStartStopTime = 6       # in secs
fanMeasCycles = 10
fanMinRPM = 500

minAmbientTemp = 16.0 # 18 C from manual. Capsule is not calibrated, add some tolerance
maxAmbientTemp = 34.0 # 32 C from manual. Capsule is not calibrated, add some tolerance
maxA64Temp = 70.0
maxUVTemp = 55.0

localedir = os.path.join(swPath, "locales")
multimediaRootPath = "/usr/share/sl1fw/multimedia"
manualURL = "https://www.prusa3d.com/SL1handbook-ENG/"
videosURL = "https://www.prusa3d.com/SL1guide/"
aboutURL = "https://www.prusa3d.com/about-us/"
firmwareTempFile = os.path.join(ramdiskPath, "update.raucb")
firmwareListURL = "https://sl1.prusa3d.com/check-update"
firmwareListTemp = os.path.join(ramdiskPath, "updates.json")
internalProjectPath = os.path.join(persistentStorage, "projects")
examplesURL = "https://www.prusa3d.com/SL1/examples.tar.gz"
admincheckURL = "https://sl1.prusa3d.com/check-admin"
admincheckTemp = os.path.join(ramdiskPath, "admincheck.json")
bootFailedStamp = os.path.join(persistentStorage, "failedboot")
apikeyFile = os.path.join(configDir, "api.key")
uvLedMeterDevice = "/dev/uvmeter"
uvLedMeasMinPwm = 125
uvLedMeasMaxPwm = 188
uvLedMeasMinPwm500k = 157
uvLedMeasMaxPwm500k = 243
factoryConfigFile = os.path.join(factoryMountPoint, "factory.toml")
logsBase = "/var/log/journal"
