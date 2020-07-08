# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import logging
import os
import re
import glob
import shutil
import hashlib
import subprocess
import sys
from tempfile import TemporaryDirectory
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil
import requests
import toml
from gi.repository import GLib
from pydbus import SystemBus

from sl1fw import defines
from sl1fw.errors.exceptions import ConfigException
from sl1fw.functions.system import get_update_channel
from sl1fw.libConfig import HwConfig
from sl1fw.libHardware import Hardware


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
    # pylint: disable=broad-except
    logger = logging.getLogger(__name__)
    text = "Export logs data summary\n"
    erros = []
    try:
        text += log_data_summary_hw(hw)
    except Exception as e:
        erros.append(last_traceback(e))
        text += "\nHw export to log failed\n"
    try:
        text += log_data_summary_system()
    except Exception as e:
        erros.append(last_traceback(e))
        text += "\nSystem export to log failed\n"
    try:
        text += log_data_summary_config()
    except Exception as e:
        erros.append(last_traceback(e))
        text += "\nConfig export to log failed"

    if erros:
        text += "\n\n----WARNINGS SUMMARY----\n"
        text += "".join([f"{i+1}. {error[0]}\n{error[1]}\n" for i, error in enumerate(erros)])

    logger.info(text)

    try:
        subprocess.check_call(["export_logs.bash", log_file])
    except Exception as exception:
        raise Exception(N_("Saving logs failed")) from exception


def log_data_summary_hw(hw: Hardware):
    text = "\n----CURRENT STATE----:\n"
    text += "UV LED Time Counter [h]: %s\n" % str(hw.getUvStatistics()[0] / 3600)
    text += "Print Display Time Counter [h]: %s\n" % str(hw.getUvStatistics()[1] / 3600)
    text += "Resin Sensor State: %s\n" % str(hw.getResinSensorState())
    text += "Cover State: Closed\n" if hw.isCoverClosed() else "Cover State: Opened\n"
    text += "Power Switch State: Pressed\n" if hw.getPowerswitchState() else "Power Switch State: Released\n"
    text += "UV LED Temperature: %s\n" % str(hw.getUvLedTemperature())
    text += "Ambient Temperature: %s\n" % str(hw.getAmbientTemperature())
    text += "CPU Temperature: %s\n" % str(hw.getCpuTemperature())
    fans_rpm = hw.getFansRpm()
    text += "UV LED fan [rpm]: %s\n" % fans_rpm[0]
    text += "Blower fan [rpm]: %s\n" % fans_rpm[1]
    text += "Rear fan [rpm]: %s\n" % fans_rpm[2]
    text += "A64 Controller SN: %s\n" % str(hw.cpuSerialNo)
    text += "MC FW version: %s\n" % str(hw.mcFwVersion)
    text += "MC HW Reversion: %s\n" % str(hw.mcFwRevision)
    text += "MC Serial number: %s\n" % str(hw.mcSerialNo)
    voltages = hw.getVoltages()
    text += "UV LED Line 1 Voltage: %s\n" % voltages[0]
    text += "UV LED Line 2 Voltage: %s\n" % voltages[1]
    text += "UV LED Line 3 Voltage: %s\n" % voltages[2]
    text += "Power Supply Voltage: %s\n" % voltages[3]
    text += "Free Space in eMMC: %s\n" % str(psutil.disk_usage("/"))
    return text


def log_data_summary_network():
    text = "\n----NETWORK INFO----\n"
    proxy = SystemBus().get("org.freedesktop.NetworkManager")
    text += "Wireless Enabled: %s\n" % proxy.WirelessEnabled
    text += "Primary Connection Type: %s\n" % proxy.PrimaryConnectionType
    for i in range(2):
        dev = SystemBus().get("org.freedesktop.NetworkManager", proxy.Devices[i + 1])
        text += "%s:\n" % dev.Interface
        try:
            devIp = SystemBus().get("org.freedesktop.NetworkManager", dev.Ip4Config)
            text += "    IP Address: %s\n" % devIp.AddressData[0]["address"]
            text += "    Gateway: %s\n" % devIp.Gateway
            try:
                devDhcp = SystemBus().get("org.freedesktop.NetworkManager", dev.Dhcp4Config)
                text += "    DHCP: Enabled\n"
                text += "    MASK: %s\n" % devDhcp.Options["subnet_mask"]
                text += "    DNS: %s\n" % devDhcp.Options["domain_name_servers"]
                # text += "    DHCP Options: %s\n" % devDhcp.Options
            except KeyError:
                text += "    DHCP: Disabled\n"
            if i == 1:
                text += "    MAC: %s\n" % dev.HwAddress
        except KeyError:
            text += "    No connection\n"
        if i == 0:
            text += "    MAC: %s\n" % dev.HwAddress

    return text


def log_data_summary_system():
    text = "\nLanguage: "
    try:
        text += "%s\n" % SystemBus().get("org.freedesktop.locale1").Locale[0]
    except GLib.GError:
        text += "No info"

    text += "\n----TIME SETTINGS----\n"
    content = subprocess.check_output("timedatectl", universal_newlines=True)
    if content != "":
        text += "%s\n" % content
    else:
        text += "No info\n"

    text += "\n----DUMP FACTORY SETTINGS----\n"
    if os.path.isfile(defines.factoryConfigFile):
        with open(defines.factoryConfigFile, "r") as f:
            factory_data = toml.load(f)
        text += "%s\n" % str(factory_data)
    else:
        text = "Factory settings not found"

    text += "\n----UPDATE CHANNEL----\n%s\n" % get_update_channel()
    if os.path.isfile("/etc/rauc/ca.cert.pem"):
        hash_md5 = hashlib.md5()
        with open("/etc/rauc/ca.cert.pem", "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        text += "Certificate md5: %s\n" % hash_md5.hexdigest()
    else:
        text += "Certificate md5: not found\n"

    text += log_data_summary_network()

    text += "\n----SLOTS INFO----\n"
    text += "%s\n" % subprocess.check_output(["rauc", "status", "--detailed"], universal_newlines=True)
    fw_files = glob.glob(os.path.join(defines.mediaRootPath, "**/*.raucb"))
    if os.path.exists(defines.firmwareTempFile):
        fw_files.append(defines.firmwareTempFile)
    for fw_file in fw_files:
        text += (
            "%s\n"
            % subprocess.run(
                ["rauc", "info", fw_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                check=False,
            ).stdout
        )

    return text


def log_data_summary_config():
    text = "\n----HARDWARE CONFIG----\n"
    try:
        hw_config = HwConfig(
            file_path=Path(defines.hwConfigFile),
            factory_file_path=Path(defines.hwConfigFactoryDefaultsFile),
            is_master=False,
        )
        hw_config.read_file()
        text += "%s\n" % str(hw_config)
    except ConfigException:
        text += "HwConfig read not successful"

    text += "\n----WIZARD DATA----\n"
    if os.path.isfile(defines.wizardDataFile):
        with open(defines.wizardDataFile, "r") as f:
            wizard_data = toml.load(f)
        for k, v in wizard_data.items():
            text += "%s: %s\n" % (k, v)
    else:
        text += "Wizard not performed yet"

    text += "\n----UV CALIBRATION DATA----\n"
    if os.path.isfile(defines.uvCalibDataPathFactory):
        with open(defines.uvCalibDataPathFactory, "r") as f:
            uvcalib_data = toml.load(f)
        for k, v in uvcalib_data.items():
            text += "%s: %s\n" % (k, v)
    else:
        text += "UV Calibration not performed yet"

    return text


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
