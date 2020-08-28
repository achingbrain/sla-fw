# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import functools
import glob
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import psutil
import toml
from pydbus import SystemBus
import requests

from sl1fw import defines
from sl1fw.functions.system import get_update_channel
from sl1fw.libHardware import Hardware
from sl1fw.libConfig import TomlConfig, TomlConfigStats


def get_save_path() -> Optional[Path]:
    """
    Dynamic USB path, first usb device or None

    :return: First usb device path or None
    """
    usbs = [p for p in Path(defines.mediaRootPath).glob("*") if p.is_mount()]
    if not usbs:
        return None
    return usbs[0]


def last_traceback(error) -> str:
    exc_traceback = sys.exc_info()[2]
    return [error.__class__.__name__, "".join(traceback.format_tb(exc_traceback))]


def upload_logs(hw: Hardware) -> (str, str):
    """
    Upload logs to log server

    :param hw: Hardware instance used to obtain additional data
    :return: Log URL, Log identifier
    """
    logger = logging.getLogger(__name__)
    logger.info("Uploading logs to server")
    log_file_name = get_log_file_name(hw)
    with TemporaryDirectory() as temp:
        path = Path(temp) / log_file_name
        save_logs_to_file(hw, path)
        with path.open("rb") as file:
            response = requests.post(
                defines.log_url,
                data={"token": 12345, "serial": hw.cpuSerialNo},
                files={"logfile": (log_file_name, file, "application/x-xz")},
            )
    logger.debug("Log upload response: %s", response)
    logger.debug("Log upload response text: %s", response.text)
    response_data = json.loads(response.text)
    logger.info("Log upload response data: %s", response_data)
    log_url = response_data["url"]
    log_id = response_data["id"] if "id" in response_data else log_url
    return log_url, log_id


def save_logs_to_usb(hw: Hardware) -> None:
    """
    Save logs to USB Flash drive
    """
    save_path = get_save_path()
    if save_path is None or not save_path.parent.exists():
        raise FileNotFoundError(save_path)

    return save_logs_to_file(hw, save_path / get_log_file_name(hw))


def get_log_file_name(hw: Hardware) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    serial = re.sub("[^a-zA-Z0-9]", "_", hw.cpuSerialNo)
    return f"log.{serial}.{timestamp}.txt.xz"


def save_logs_to_file(hw: Hardware, log_file) -> None:
    logger = logging.getLogger(__name__)

    data_template = {
        "hardware" : functools.partial(log_hw, hw),
        "system" : log_system,
        "network" : log_network,
        "configs" : log_configs,
        "statistics": functools.partial(log_statistics, hw),
        "counters": log_counters
    }

    data = {}
    for name, function in data_template.items():
        try:
            data[name] = function()
        except Exception as exception:
            data[name] = {"exception": repr(exception)}

    bash_call = ["export_logs.bash", log_file]
    try:
        with open(defines.ramdiskPath + "/printer_summary", "w") as summary_file:
            summary_file.write(json.dumps(data, indent=2, sort_keys=True))
            bash_call.append(summary_file.name)
    except Exception:
        logger.exception("Printer summary failed to assemble")

    subprocess.check_call(bash_call)


def log_hw(hw: Hardware) -> None:
    fans_rpm = hw.getFansRpm()
    voltages = hw.getVoltages()
    try:
        locales = SystemBus().get('org.freedesktop.locale1').Locale[0]
    except Exception:
        locales = "No info"

    data = {
            "Resin Sensor State" : hw.getResinSensorState(),
            "Cover State" : hw.isCoverClosed(),
            "Power Switch State" : hw.getPowerswitchState(),
            "UV LED Temperature" : hw.getUvLedTemperature(),
            "Ambient Temperature" : hw.getAmbientTemperature(),
            "CPU Temperature" : hw.getCpuTemperature(),
            "UV LED fan [rpm]" : fans_rpm[0],
            "Blower fan [rpm]" : fans_rpm[1],
            "Rear fan [rpm]" : fans_rpm[2],
            "A64 Controller SN" : hw.cpuSerialNo,
            "MC FW version" : hw.mcFwVersion,
            "MC HW Reversion" : hw.mcBoardRevision,
            "MC Serial number" : hw.mcSerialNo,
            "UV LED Line 1 Voltage" : voltages[0],
            "UV LED Line 2 Voltage" : voltages[1],
            "UV LED Line 3 Voltage" : voltages[2],
            "Power Supply Voltage" : voltages[3],
            "Free Space in eMMC" : psutil.disk_usage('/'),
            "RAM statistics" : psutil.virtual_memory(),
            "CPU usage per core" : psutil.cpu_percent(percpu=True),
            "CPU times" : psutil.cpu_times(),
            "Language" : locales
    }
    return data


def log_system():
    data = {
        "time settings": {},
        "update channel": {},
        "slots info": {},
        "raucb updates": {},
    }
    time = SystemBus().get("org.freedesktop.timedate1")
    time_data = time.GetAll("org.freedesktop.timedate1")
    time_data["UniversalTime"] = str(datetime.fromtimestamp(time_data["TimeUSec"] // 1000000))
    time_data["RtcTime"] = str(datetime.fromtimestamp(time_data["RTCTimeUSec"] // 1000000))
    data["time settings"] = time_data

    hash_md5 = hashlib.md5()
    with open("/etc/rauc/ca.cert.pem", "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
        data["update channel"] = {
            "channel" : get_update_channel(),
            "certificate_md5" : hash_md5.hexdigest()
        }

    data["slots info"] = json.loads(subprocess.check_output(
        ["rauc", "status", "--detailed", "--output-format=json"], universal_newlines=True))

    fw_files = glob.glob(os.path.join(defines.mediaRootPath, "**/*.raucb"))
    if os.path.exists(defines.firmwareTempFile):
        fw_files.append(defines.firmwareTempFile)

    for key, fw_file in enumerate(fw_files):
        data["raucb updates"][key] = {}
        try:
            data["raucb updates"][key] = json.loads(
                subprocess.check_output(["rauc", "info", "--output-format=json", fw_file], universal_newlines = True))
        except subprocess.CalledProcessError:
            data["raucb updates"][key] = "Error getting info from " + fw_file

    return data


def log_network():
    proxy = SystemBus().get('org.freedesktop.NetworkManager')
    data = {
        "wifi_enabled" : proxy.WirelessEnabled,
        "primary_conn_type" : proxy.PrimaryConnectionType
    }
    for devPath in proxy.Devices:
        dev = SystemBus().get('org.freedesktop.NetworkManager', devPath)
        data[dev.Interface] = {
            "state" : dev.State,
            "mac" : dev.HwAddress
        }
        if dev.State > 40: # is connected to something
            devIp = SystemBus().get('org.freedesktop.NetworkManager', dev.Ip4Config)
            data[dev.Interface] = {
                "address" : devIp.AddressData,
                "gateway" : devIp.Gateway,
                "dns" : devIp.NameserverData
            }
            if SystemBus().get('org.freedesktop.NetworkManager', dev.Dhcp4Config):
                data[dev.Interface]["dhcp"] = True
            else:
                data[dev.Interface]["dhcp"] = False

    return data


def log_configs():
    data = {
        "user" : { "hardware": {}, "uvcalib_data" : {}, "wizard_data" : {}},
        "factory" : { "factory" : {}, "hardware": {}, "uvcalib_data" : {}, "wizard_data" : {}}
    }
    for category, values in data.items():
        for name in values:
            path_prefix = defines.factoryMountPoint
            extension = ".toml"
            if category == "user":
                path_prefix = defines.configDir
                if name == "hardware":
                    extension = ".cfg"

            try:
                file_path = path_prefix / (name + "" + extension)
                with file_path.open("r") as f:
                    data[category][name] = toml.load(f)
                data[category][name]["last_modified"] = str(datetime.fromtimestamp(file_path.stat().st_mtime))
            except FileNotFoundError:
                data[category][name] = {"exception": "File not found"}
            except Exception as exception:
                data[category][name] = {"exception": repr(exception)}

    return data


def ch_mode_owner(src):
    """
        change group and mode of the file or folder.
    """
    shutil.chown(src, group=defines.internalProjectGroup)
    if os.path.isdir(src):
        os.chmod(src, defines.internalProjectDirMode)
        for name in os.listdir(src):
            ch_mode_owner(os.path.join(src, name))
    else:
        os.chmod(src, defines.internalProjectMode)

def log_statistics(hw: Hardware):
    data = TomlConfigStats(defines.statsData, None).load()
    data["UV LED Time Counter [h]"] = hw.getUvStatistics()[0] / 3600
    data["Display Time Counter [h]"] = hw.getUvStatistics()[1] / 3600
    return data

def log_counters():
    data = TomlConfig(defines.counterLog).load()
    return data
