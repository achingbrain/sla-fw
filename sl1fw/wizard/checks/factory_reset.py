# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import subprocess
from abc import abstractmethod
from asyncio import sleep, gather
from pathlib import Path
from shutil import rmtree, copyfile

import distro
from gi.repository import GLib

import pydbus
import paho.mqtt.publish as mqtt

from sl1fw import defines, test_runtime
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.errors.errors import (
    MissingUVPWM,
    MissingWizardData,
    MissingCalibrationData,
    MissingUVCalibrationData,
    ErrorSendingDataToMQTT,
    MissingExamples,
)
from sl1fw.errors.warnings import FactoryResetCheckFailure
from sl1fw.functions.files import ch_mode_owner, get_all_supported_files
from sl1fw.functions.system import FactoryMountedRW, save_factory_mode, compute_uvpwm
from sl1fw.libHardware import Hardware, Axis
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import Check, WizardCheckType, SyncCheck, DangerousCheck
from sl1fw.wizard.wizards.self_test import SelfTestWizard
from sl1fw.wizard.wizards.uv_calibration import UVCalibrationWizard
from sl1fw.hardware.tilt import TiltProfile
from sl1fw.hardware.printer_model import PrinterModel


class ResetCheck(SyncCheck):
    def __init__(self, *args, hard_errors: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.hard_errors = hard_errors

    def task_run(self, actions: UserActionBroker):
        try:
            self.reset_task_run(actions)
            # Subtle non-asyncio delay to slow down reset check processing while providing nicer user feedback.
        except Exception as exception:
            self._logger.exception("Failed to run factory reset check: %s", type(self).__name__)
            if self.hard_errors:
                raise
            self.add_warning(FactoryResetCheckFailure(f"Failed to run factory reset check: {exception}"))

    @abstractmethod
    def reset_task_run(self, actions: UserActionBroker):
        ...


class EraseProjects(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.ERASE_PROJECTS, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        rmtree(defines.internalProjectPath)
        if not Path(defines.internalProjectPath).exists():
            Path(defines.internalProjectPath).mkdir(parents=True)
            ch_mode_owner(defines.internalProjectPath)


class ResetHostname(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_HOSTNAME, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        hostname = pydbus.SystemBus().get("org.freedesktop.hostname1")
        hostname.SetStaticHostname(defines.default_hostname, False)
        hostname.SetHostname(defines.default_hostname, False)


class ResetAPIKey(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_API_KEY, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        """
        Reset apikey (will be regenerated on next boot)
        """

        Path(defines.apikeyFile).unlink(missing_ok=True)


class ResetRemoteConfig(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_REMOTE_CONFIG, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        """
        Reset remote config (don't delete it)
        """
        if os.path.exists(defines.remoteConfig):
            os.remove(defines.remoteConfig)


class ResetHttpDigest(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_HTTP_DIGEST, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        try:
            defines.nginx_enabled.unlink()
            defines.nginx_enabled.symlink_to(defines.nginx_http_digest)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self._logger.exception("Failed to reset http digest config")


class ResetWifi(ResetCheck):
    NETWORK_MANAGER = "org.freedesktop.NetworkManager"

    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_WIFI, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        system_bus = pydbus.SystemBus()
        for connection in system_bus.get(self.NETWORK_MANAGER, "Settings").ListConnections():
            if (
                system_bus.get(self.NETWORK_MANAGER, connection).GetSettings()["connection"]["type"]
                == "802-11-wireless"
            ):
                try:
                    system_bus.get(self.NETWORK_MANAGER, connection).Delete()
                except GLib.GError:
                    self._logger.exception("Failed to delete connection %s", connection)


class ResetTimezone(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_TIMEZONE, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        Path(defines.local_time_path).unlink(missing_ok=True)
        copyfile(
            "/usr/share/factory/etc/localtime",
            "/etc/localtime",
            follow_symlinks=False,
        )


class ResetNTP(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_NTP, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        pydbus.SystemBus().get("org.freedesktop.timedate1").SetNTP(True, False)


class ResetLocale(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_LOCALE, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        pydbus.SystemBus().get("org.freedesktop.locale1").SetLocale(["C"], False)


class ResetUVCalibrationData(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_UV_CALIBRATION_DATA, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        for name in UVCalibrationWizard.get_alt_names():
            (defines.configDir / name).unlink(missing_ok=True)


class RemoveSlicerProfiles(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.REMOVE_SLICER_PROFILES, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        Path(defines.slicerProfilesFile).unlink(missing_ok=True)


class ResetHWConfig(ResetCheck):
    def __init__(self, hw: Hardware, *args, disable_unboxing: bool = False, **kwargs):
        super().__init__(WizardCheckType.RESET_HW_CONFIG, *args, **kwargs)
        self._hw = hw
        self._disable_unboxing = disable_unboxing

    def reset_task_run(self, actions: UserActionBroker):
        self._hw.config.read_file()
        self._hw.config.factory_reset()
        if self._disable_unboxing:
            self._hw.config.showUnboxing = False
        if self._hw.printer_model == PrinterModel.SL1S:
            self._hw.config.vatRevision = 1
        self._hw.config.write()
        # TODO: Why is this here? Separate task would be better.
        rmtree(defines.wizardHistoryPath, ignore_errors=True)


class EraseMCEeprom(ResetCheck):
    def __init__(self, hw: Hardware, *args, **kwargs):
        super().__init__(WizardCheckType.ERASE_MC_EEPROM, *args, **kwargs)
        self._hw = hw

    def reset_task_run(self, actions: UserActionBroker):
        self._hw.eraseEeprom()


class ResetHomingProfiles(ResetCheck):
    """
    Set homing profiles to factory defaults
    """

    def __init__(self, hw: Hardware, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_HOMING_PROFILES, *args, **kwargs)
        self._hw = hw

    def reset_task_run(self, actions: UserActionBroker):
        self._hw.updateMotorSensitivity(Axis.TOWER)
        self._hw.updateMotorSensitivity(Axis.TILT)


class DisableFactory(SyncCheck):
    def __init__(self, hw: Hardware, runtime_config: RuntimeConfig):
        super().__init__(WizardCheckType.DISABLE_FACTORY)
        self._hw = hw
        self._runtime_config = runtime_config

    def task_run(self, actions: UserActionBroker):
        self._logger.info("Factory reset - disabling factory mode")
        with FactoryMountedRW():
            defines.factory_enable.unlink(missing_ok=True)
            if not save_factory_mode(False):
                self._logger.error("Factory mode was not disabled!")
                # This is to stop shipment of factory mode enabled printer
                raise Exception("Factory mode was not disabled!")


class SendPrinterData(SyncCheck):
    def __init__(self, hw: Hardware):
        super().__init__(WizardCheckType.SEND_PRINTER_DATA)
        self._hw = hw

    def task_run(self, actions: UserActionBroker):
        # pylint: disable = too-many-branches
        # Ensure some UV PWM is set, this ensure SL1 was UV calibrated
        if self._hw.config.uvPwm == 0:
            self._logger.error("Cannot do factory reset UV PWM not set (== 0)")
            raise MissingUVPWM()

        # Ensure SL1S is able to compute UV PWM
        if self._hw.printer_model == PrinterModel.SL1S:
            compute_uvpwm(self._hw)

        # Ensure examples are present
        if not get_all_supported_files(self._hw.printer_model, Path(defines.internalProjectPath)):
            raise MissingExamples()

        # Get wizard data
        try:
            with (defines.factoryMountPoint / SelfTestWizard.get_data_filename()).open("rt") as file:
                wizard_dict = json.load(file)
            if not wizard_dict and not self._hw.isKit:
                raise ValueError("Wizard data dictionary is empty")
            if self._hw.config.showWizard:
                raise Exception("Wizard data exists, but wizard is not considered done")
        except Exception as exception:
            raise MissingWizardData from exception

        if not self._hw.config.calibrated and not self._hw.isKit:
            raise MissingCalibrationData()

        # Get UV calibration data
        calibration_dict = {}
        # SL1S does not have UV calibration
        if self._hw.printer_model != PrinterModel.SL1S:
            try:
                with (defines.factoryMountPoint / UVCalibrationWizard.get_data_filename()).open("rt") as file:
                    calibration_dict = json.load(file)
                if not calibration_dict:
                    raise ValueError("UV Calibration dictionary is empty")
            except Exception as exception:
                raise MissingUVCalibrationData() from exception

        # Compose data to single dict, ensure basic data are present
        mqtt_data = {
            "osVersion": distro.version(),
            "a64SerialNo": self._hw.cpuSerialNo,
            "mcSerialNo": self._hw.mcSerialNo,
            "mcFwVersion": self._hw.mcFwVersion,
            "mcBoardRev": self._hw.mcBoardRevision,
        }
        mqtt_data.update(wizard_dict)
        mqtt_data.update(calibration_dict)

        # Send data to MQTT
        topic = "prusa/sl1/factoryConfig"
        self._logger.info("Sending mqtt data: %s", mqtt_data)
        try:
            if not test_runtime.testing:
                mqtt.single(topic, json.dumps(mqtt_data), qos=2, retain=True, hostname=defines.mqtt_prusa_host)
            else:
                self._logger.debug("Testing mode, not sending MQTT data")
        except Exception as exception:
            self._logger.error("mqtt message not delivered. %s", exception)
            raise ErrorSendingDataToMQTT() from exception


class InitiatePackingMoves(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(hw, WizardCheckType.INITIATE_PACKING_MOVES)
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        await gather(self._hw.verify_tower(), self._hw.verify_tilt())

        # move tilt and tower to packing position
        self._hw.tilt.profile_id = TiltProfile.homingFast
        self._hw.tilt.move_absolute(defines.defaultTiltHeight)
        while self._hw.tilt.moving:
            await sleep(0.25)

        self._hw.setTowerProfile("homingFast")
        # TODO: Constant in code !!!
        self._hw.towerMoveAbsolute(self._hw.config.towerHeight - self._hw.config.calcMicroSteps(74))
        while self._hw.isTowerMoving():
            await sleep(0.25)


class FinishPackingMoves(Check):
    def __init__(self, hw: Hardware):
        super().__init__(WizardCheckType.FINISH_PACKING_MOVES)
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        # slightly press the foam against printers base
        # TODO: Constant in code !!!
        self._hw.towerMoveAbsolute(self._hw.config.towerHeight - self._hw.config.calcMicroSteps(93))
        while self._hw.isTowerMoving():
            await sleep(0.25)


class DisableAccess(SyncCheck):
    def __init__(self):
        super().__init__(WizardCheckType.DISABLE_ACCESS)

    def task_run(self, actions: UserActionBroker):
        with FactoryMountedRW():
            defines.ssh_service_enabled.unlink(missing_ok=True)
            defines.serial_service_enabled.unlink(missing_ok=True)


class ResetTouchUI(ResetCheck):
    def __init__(self):
        super().__init__(WizardCheckType.RESET_TOUCH_UI)

    def reset_task_run(self, actions: UserActionBroker):
        defines.touch_ui_config.unlink(missing_ok=True)
