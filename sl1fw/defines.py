# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import stat
from pathlib import Path

import sl1fw
from sl1fw import test_runtime

reqMcVersion = "1.0.0"

factoryMountPoint = Path("/usr/share/factory/defaults")
persistentStorage = "/var/sl1fw"

swPath = os.path.dirname(sl1fw.__file__)
dataPath = os.path.join(swPath, "data")
ramdiskPath = "/run/sl1fw"
mediaRootPath = "/run/media/root"
configDir = Path("/etc/sl1fw")
loggingConfig = configDir / "loggerConfig.json"
remoteConfig = configDir / "remoteConfig.toml"

hwConfigFileName = "hardware.cfg"
hwConfigPath = configDir / hwConfigFileName
hwConfigPathFactory = factoryMountPoint / "hardware.toml"
factoryConfigPath = factoryMountPoint / "factory.toml"

wizardDataFilename = "wizard_data.toml"
wizardDataPath = configDir / wizardDataFilename
wizardDataPathFactory = factoryMountPoint / wizardDataFilename

uvCalibDataFilename = "uvcalib_data.toml"
uvCalibDataPath = configDir / uvCalibDataFilename
uvCalibDataPathFactory = factoryMountPoint / uvCalibDataFilename

uvCalibDuration = 60 # 1 minute countdown

perPartesMask = os.path.join(dataPath, "perpartes_mask.png")

configFile = "config.ini"
maskFilename = "mask.png"
projectExtensions = {".dwz", ".sl1"}
previousPrints = os.path.join(persistentStorage, "previous-prints")
lastProjectHwConfig = os.path.join(previousPrints, hwConfigFileName)
lastProjectFactoryFile = os.path.join(previousPrints, os.path.basename(hwConfigPathFactory))
lastProjectConfigFile = os.path.join(previousPrints, configFile)
lastProjectPickler = os.path.join(previousPrints, "last_project.pck")
statsData = os.path.join(persistentStorage, "stats.toml")
serviceData = os.path.join(persistentStorage, "service.toml")
counterLog = os.path.join(factoryMountPoint, "counters-log.toml")
last_job = Path(persistentStorage) / "last_job"

screenWidth = 1440
screenHeight = 2560
screen_size = (screenWidth, screenHeight)
screen_pixel_size_nm = 46875
thumbnailFactor = 5
thumbnailWidth = screenWidth // thumbnailFactor
thumbnailHeight = screenHeight // thumbnailFactor
fontFile = os.path.join(dataPath, "FreeSansBold.otf")

livePreviewSize = (thumbnailWidth, thumbnailHeight)
livePreviewImage = os.path.join(ramdiskPath, "live.png")

# numpy uses reversed axis indexing
display_usage_size = (thumbnailHeight, thumbnailWidth)
display_usage_shape = (thumbnailHeight, thumbnailFactor, thumbnailWidth, thumbnailFactor)
displayUsageData = os.path.join(persistentStorage, "display_usage.npz")
displayUsagePalette = os.path.join(dataPath, "heatmap_palette.txt")

profilesFile = "slicer_profiles.toml"
slicerProfilesFallback = Path(dataPath) / profilesFile
slicerProfilesFile = Path(persistentStorage) / profilesFile
slicerPrinterModel = "SL1"
slicerPrinterVariant = "default"
slicerMinVersion = "2.2.0-alpha3"
slicerProfilesCheckProblem = 14400   # every four hours
slicerProfilesCheckOK = 86400   # once per day

cpuSNFile = "/sys/bus/nvmem/devices/sunxi-sid0/nvmem"
cpuTempFile = "/sys/devices/virtual/thermal/thermal_zone0/temp"

scriptDir = "/usr/share/sl1fw/scripts"
flashMcCommand = os.path.join(scriptDir, "flashMC.sh")
htDigestCommand = os.path.join(scriptDir, "http_digest.sh")

qtDisplayPort = 32768
templates = '/srv/http/intranet/templates'

motionControlDevice = "/dev/ttyS2"
mc_debug_port = 8192
uv_meter_device = "/dev/uvmeter"

wifiSetupFile = "/etc/hostapd.secrets.json"

octoprintURI = ":8000"
octoprintAuthFile = configDir / "slicer-upload-api.key"

fbFile = "/dev/shm/fb"

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
tiltHomingTolerance = 96    # tilt axis check has this tolerance
towerHoldCurrent = 12
tiltHoldCurrent = 35
tiltCalibCurrent = 40

fanStartStopTime = 10       # in secs
fanWizardStabilizeTime = 30

fanMaxRPM = {0: 2700, 1: 3300, 2: 5000}
fanMinRPM = 800

minAmbientTemp = 16.0 # 18 C from manual. Capsule is not calibrated, add some tolerance
maxAmbientTemp = 34.0 # 32 C from manual. Capsule is not calibrated, add some tolerance
maxA64Temp = 80.0     # maximal temperature of A64 is 125 C according to datasheet
maxUVTemp = 55.0

# keep at least 110 MB of free space when copying project to internal storage or extracting examples
internalReservedSpace = 110 * 1024 * 1024

localedir = os.path.join(swPath, "locales")
multimediaRootPath = "/usr/share/sl1fw/multimedia"
manualURL = "https://www.prusa3d.com/SL1handbook-ENG/"
videosURL = "https://www.prusa3d.com/SL1guide/"
aboutURL = "https://www.prusa3d.com/about-us/"
firmwareTempFile = os.path.join(ramdiskPath, "update.raucb")
firmwareListURL = "https://sl1.prusa3d.com/check-update"
firmwareListTemp = os.path.join(ramdiskPath, "updates.json")
internalProjectPath = os.path.join(persistentStorage, "projects")
internalProjectGroup = "projects"
internalProjectMode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
internalProjectDirMode = stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH
examplesURL = "https://sl1.prusa3d.com/examples.tar.gz"
admincheckURL = "https://sl1.prusa3d.com/check-admin"
admincheckTemp = os.path.join(ramdiskPath, "admincheck.json")
bootFailedStamp = os.path.join(persistentStorage, "failedboot")
apikeyFile = configDir / "api.key"
uvLedMeterMaxWait_s = 10
uvLedMeasMinPwm = 125
uvLedMeasMaxPwm = 218
uvLedMeasMinPwm500k = 150
uvLedMeasMaxPwm500k = 250
logsBase = "/var/log/journal"
traces = 30
printer_summary = Path(ramdiskPath) / "printer_summary"

exposure_time_min_ms = 1000
exposure_time_max_ms = 60000
exposure_time_first_min_ms = 10000
exposure_time_first_max_ms = 120000
exposure_time_calibrate_min_ms = 500
exposure_time_calibrate_max_ms = 5000
exposure_time_first_extra_layers = 2    # first layer always have exposure_time_first

fan_check_override = test_runtime.testing
default_hostname = "prusa64-sl1"
mqtt_prusa_host = "mqttstage.prusa"
set_update_channel_bin = "/usr/sbin/set-update-channel.sh"
update_channel = Path("/etc/update_channel")

log_url = "http://logserver.etrimon.cz/wp-json/p3d/v1/logserver" # TODO: THIS IS TEMPORARY USE REAL LOG SERVER