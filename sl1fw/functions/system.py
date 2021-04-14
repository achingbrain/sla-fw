# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import os
import subprocess

import distro
import paho.mqtt.publish as mqtt

from sl1fw import defines, test_runtime
from sl1fw.errors.errors import (
    MissingWizardData,
    MissingCalibrationData,
    MissingUVCalibrationData,
    ErrorSendingDataToMQTT,
    FailedUpdateChannelSet,
    FailedUpdateChannelGet,
)
from sl1fw.errors.exceptions import ConfigException
from sl1fw.configs.toml import TomlConfig
from sl1fw.hardware.printer_model import PrinterModel
from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage


def shut_down(hw: Hardware, reboot=False):
    if test_runtime.testing:
        print("Skipping poweroff due to testing")
        return

    hw.uvLed(False)
    hw.motorsRelease()

    if reboot:
        os.system("reboot")
    else:
        os.system("poweroff")


def save_factory_mode(enable: bool):
    """
    Save factory mode

    This has to be called with factory partition mounted rw

    :param enable: Required factory mode state
    :return: True if successful, false otherwise
    """
    return TomlConfig(defines.factoryConfigPath).save(data={"factoryMode": enable})


def send_printer_data(hw: Hardware):
    logger = logging.getLogger(__name__)

    # Get wizard data
    try:
        # TODO: Reference SelfTestWizard.data_filename once this does not cause circular import
        with (defines.factoryMountPoint / "self_test_data.json").open("rt") as file:
            wizard_dict = json.load(file)
        if not wizard_dict and not hw.isKit:
            raise MissingWizardData()
    except Exception as exception:
        raise MissingWizardData from exception

    if not hw.config.calibrated and not hw.isKit:
        raise MissingCalibrationData()

    # Get UV calibration data
    calibration_dict = TomlConfig(defines.uvCalibDataPathFactory).load()
    if not calibration_dict:
        raise MissingUVCalibrationData()

    # Compose data to single dict, ensure basic data are present
    mqtt_data = {
        "osVersion": distro.version(),
        "a64SerialNo": hw.cpuSerialNo,
        "mcSerialNo": hw.mcSerialNo,
        "mcFwVersion": hw.mcFwVersion,
        "mcBoardRev": hw.mcBoardRevision,
    }
    mqtt_data.update(wizard_dict)
    mqtt_data.update(calibration_dict)

    # Send data to MQTT
    topic = "prusa/sl1/factoryConfig"
    logger.info("Sending mqtt data: %s", mqtt_data)
    try:
        if not test_runtime.testing:
            mqtt.single(topic, json.dumps(mqtt_data), qos=2, retain=True, hostname=defines.mqtt_prusa_host)
        else:
            logger.debug("Testing mode, not sending MQTT data")
    except Exception as e:
        logger.error("mqtt message not delivered. %s", e)
        raise ErrorSendingDataToMQTT() from e


def get_update_channel() -> str:
    try:
        return defines.update_channel.read_text().strip()
    except (FileNotFoundError, PermissionError) as e:
        raise FailedUpdateChannelGet() from e


def set_update_channel(channel: str):
    try:
        subprocess.check_call([defines.set_update_channel_bin, channel])
    except Exception as e:
        raise FailedUpdateChannelSet() from e


def get_octoprint_auth(logger: logging.Logger) -> str:
    try:
        with open(defines.octoprintAuthFile, "r") as f:
            return f.read()
    except IOError as e:
        logger.exception("Octoprint auth file read failed")
        raise ConfigException("Octoprint auth file read failed") from e


def hw_all_off(hw: Hardware, exposure_image: ExposureImage):
    exposure_image.blank_screen()
    hw.uvLed(False)
    hw.stopFans()
    hw.motorsRelease()


class FactoryMountedRW:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        self.logger.info("Remounting factory partition rw")
        if test_runtime.testing:
            self.logger.warning("Skipping factory RW remount due to testing")
        else:
            subprocess.check_call(["/usr/bin/mount", "-o", "remount,rw", str(defines.factoryMountPoint)])

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.logger.info("Remounting factory partition ro")
        if test_runtime.testing:
            self.logger.warning("Skipping factory RW remount due to testing")
        else:
            subprocess.check_call(["/usr/bin/mount", "-o", "remount,ro", str(defines.factoryMountPoint)])


def set_configured_printer_model(model: PrinterModel):
    """
    Adjust printer model definition files to match new printer model

    :param model: New printer model
    :raises ValueError: Raised on unknown model - no modification is done
    """

    # Obtain new model file before clearing existing definitions (just in case this raises an exception)
    if model == PrinterModel.SL1:
        model_file = defines.sl1_model_file
    elif model == PrinterModel.SL1S:
        model_file = defines.sl1s_model_file
    else:
        raise ValueError(f"No file defined for model: {model}")

    # Clear existing model definitions
    for file in defines.printer_model.glob("*"):
        if file.is_file():
            file.unlink()

    # Add new model definition
    model_file.parent.mkdir(exist_ok=True)
    model_file.touch()

def get_configured_printer_model() -> PrinterModel:
    if defines.sl1s_model_file.exists():
        return PrinterModel.SL1S

    if defines.sl1_model_file.exists():
        return PrinterModel.SL1

    return PrinterModel.NONE
