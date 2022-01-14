# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import stat
from pathlib import Path

import sl1fw
from sl1fw import test_runtime

reqMcVersion = "1.1.5"

printerVariant = "default"

factoryMountPoint = Path("/usr/share/factory/defaults")
persistentStorage = "/var/sl1fw"

swPath = os.path.dirname(sl1fw.__file__)
dataPath = os.path.join(swPath, "data")
ramdiskPath = "/run/sl1fw"
mediaRootPath = "/run/media/system"
configDir = Path("/etc/sl1fw")
loggingConfig = configDir / "loggerConfig.json"
remoteConfig = configDir / "remoteConfig.toml"

wizardHistoryPath = Path(persistentStorage) / "wizard_history" / "user_data"
wizardHistoryPathFactory = Path(persistentStorage) / "wizard_history" / "factory_data"

hwConfigFileName = "hardware.cfg"
hwConfigPath = configDir / hwConfigFileName
hwConfigPathFactory = factoryMountPoint / "hardware.toml"
factoryConfigPath = factoryMountPoint / "factory.toml"
factory_enable = factoryMountPoint / "factory_mode_enabled"
serial_service_enabled = factoryMountPoint / "serial_enabled"
serial_service_service = "serial-getty@ttyS0.service"
ssh_service_enabled = factoryMountPoint / "ssh_enabled"
ssh_service_service = "sshd.socket"
printer_m1_enabled = factoryMountPoint / "printer_m1_enabled"

expoPanelLogFileName = "expo_panel_log.json"
expoPanelLogPath = factoryMountPoint / expoPanelLogFileName

tiltProfilesSuffix = "tilt"
tuneTiltProfilesSuffix = "tune_tilt"
towerProfilesSuffix = "tower"

# Deprecated. Used be calibration data show, but this does not respect new format used by API based wizards.
# TODO: This needs to be fixed in order to be able to display recent wizard data properly.
wizardDataFilename = "wizard_data.toml"  # deprecated
wizardDataPath = configDir / wizardDataFilename  # deprecated
wizardDataPathFactory = factoryMountPoint / wizardDataFilename  # deprecated
uvCalibDataFilename = "uvcalib_data.toml"  # deprecated
uvCalibDataPath = configDir / uvCalibDataFilename  # deprecated
uvCalibDataPathFactory = factoryMountPoint / uvCalibDataFilename  # deprecated

uvCalibDuration = 60 # 1 minute countdown

perPartesMask = "perpartes_mask.png"

configFile = "config.ini"
maskFilename = "mask.png"
previousPrints = os.path.join(persistentStorage, "previous-prints")
lastProjectHwConfig = os.path.join(previousPrints, hwConfigFileName)
lastProjectFactoryFile = os.path.join(previousPrints, os.path.basename(hwConfigPathFactory))
lastProjectConfigFile = os.path.join(previousPrints, configFile)
lastProjectPickler = os.path.join(previousPrints, "last_project.pck")
statsData = os.path.join(persistentStorage, "stats.toml")
serviceData = os.path.join(persistentStorage, "service.toml")
counterLogFilename = "counters-log.toml"
counterLog = factoryMountPoint / counterLogFilename
last_job = Path(persistentStorage) / "last_job"
last_log_token = Path(persistentStorage) / "last_log_token"
manual_uvc_filename = "manual_uv_calibration_data"

fontFile = os.path.join(dataPath, "FreeSansBold.otf")
livePreviewImage = os.path.join(ramdiskPath, "live.png")
displayUsageData = os.path.join(persistentStorage, "display_usage.npz")
displayUsagePalette = os.path.join(dataPath, "heatmap_palette.txt")
fullscreenImage = os.path.join(ramdiskPath, "fsimage.png")

profilesFile = "slicer_profiles.toml"
slicerProfilesFallback = Path(dataPath) / profilesFile
slicerProfilesFile = Path(persistentStorage) / profilesFile
slicerMinVersion = "2.2.0-alpha3"
slicerProfilesCheckProblem = 14400   # every four hours
slicerProfilesCheckOK = 86400   # once per day

cpuSNFile = "/sys/bus/nvmem/devices/sunxi-sid0/nvmem"
cpuTempFile = "/sys/devices/virtual/thermal/thermal_zone0/temp"

scriptDir = "/usr/share/sl1fw/scripts"
flashMcCommand = os.path.join(scriptDir, "flashMC.sh")
TruncLogsCommand = os.path.join(scriptDir, "truncate_logs.sh")

qtDisplayPort = 32768
templates = '/srv/http/intranet/templates'

motionControlDevice = "/dev/ttyS2"
mc_debug_port = 8192
uv_meter_device = "/dev/uvmeter"

wifiSetupFile = "/etc/hostapd.secrets.json"

octoprintURI = ":8000"
octoprintAuthFile = configDir / "slicer-upload-api.key"

# all resin* in ml
resinMinVolume = 68.5
resinMaxVolume = 200.0
resinLowWarn = 60
resinFeedWait = 50
resinFilled = 200

defaultTowerHeight = 120    # mm
defaultTowerOffset = 0.05   # mm
towerHoldCurrent = 12

tiltHomingTolerance = 96    # tilt axis check has this tolerance
tiltHoldCurrent = 35
tiltCalibCurrent = 40
defaultTiltHeight = 4928    # rounded to fullstep (phase 0) [ustep]
tiltMin = -12800            # whole turn [ustep]
tiltMax = 6016              # top deadlock [ustep]
tiltCalibrationStart = 4352 # bottom position where tilt calibration starts [ustep]

fanStartStopTime = 10       # in secs
fanWizardStabilizeTime = 30

fanMaxRPM = {0: 2700, 1: 3300, 2: 5000}
fanMinRPM = 800

minAmbientTemp = 16.0 # 18 C from manual. Capsule is not calibrated, add some tolerance
maxAmbientTemp = 34.0 # 32 C from manual. Capsule is not calibrated, add some tolerance
maxA64Temp = 80.0     # maximal temperature of A64 is 125 C according to datasheet
maxUVTemp = 55.0
uv_temp_hysteresis = 10  # 10 deg C hysteresis

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
examplesURL = "https://sl1.prusa3d.com/examples-{PRINTER_MODEL}.tar.gz"
admincheckURL = "https://sl1.prusa3d.com/check-admin"
admincheckTemp = os.path.join(ramdiskPath, "admincheck.json")
bootFailedStamp = os.path.join(persistentStorage, "failedboot")
apikeyFile = configDir / "api.key"
uvLedMeterMaxWait_s = 10

logsBase = "/var/log/journal"
traces = 30
printer_summary = Path(ramdiskPath) / "printer_summary"

exposure_time_min_ms = 1000
exposure_time_max_ms = 60000
exposure_time_first_min_ms = 10000
exposure_time_first_max_ms = 120000
exposure_time_calibrate_min_ms = 100
exposure_time_calibrate_max_ms = 5000
exposure_time_first_extra_layers = 2    # first layer always have exposure_time_first
exposure_safe_delay_before = 30         # [tenths of a second] applied when user selects ExposureUserProfile.SAFE
exposure_slow_move_delay_before = 10    # [tenths of a second] applied when slow move of ExposureUserProfile.DEFAULT

tank_surface_cleaning_exposure_time_s = 50 # seconds

fan_check_override = test_runtime.testing
default_hostname = "prusa-"
mqtt_prusa_host = "mqttstage.prusa"
set_update_channel_bin = "/usr/sbin/set-update-channel.sh"
update_channel = Path("/etc/update_channel")

log_url = "https://prusa3d.link/wp-json/p3d/v1/logserver"
log_url_dev = "http://cucek.prusa/api/upload"
emmc_serial_path = Path("/sys/block/mmcblk2/device/cid")
log_upload_token = "84U83mUQ"
local_time_path = Path("/etc/localtime")
exposure_panel_of_node = Path("/sys/bus/i2c/devices/1-000f/of_node")

nginx_http_digest = Path("/etc/nginx/http_digest_enabled")

printer_model = configDir / "model"
sl1_model_file = printer_model / "sl1"
sl1s_model_file = printer_model / "sl1s"
m1_model_file = printer_model / "m1"
detect_sla_model_file = Path("/tmp/detect-sla-model")
