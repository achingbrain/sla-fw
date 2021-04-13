# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
from abc import abstractmethod
from asyncio import sleep
from pathlib import Path
from shutil import rmtree, copyfile
from gi.repository import GLib

import pydbus

from sl1fw import defines
from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.errors.errors import MissingUVPWM, PrinterDataSendError
from sl1fw.errors.warnings import FactoryResetCheckFailure
from sl1fw.functions.files import ch_mode_owner
from sl1fw.functions.system import (
    FactoryMountedRW,
    save_factory_mode,
    send_printer_data,
)
from sl1fw.tests.mocks.hardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import Check, WizardCheckType, SyncCheck
from sl1fw.wizard.wizards.uv_calibration import UVCalibrationWizard
from sl1fw.hardware.tilt import TiltProfile


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
        with open(defines.remoteConfig, "w") as fp:
            fp.truncate(0)


class ResetHttpDigest(ResetCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(WizardCheckType.RESET_HTTP_DIGEST, *args, **kwargs)

    def reset_task_run(self, actions: UserActionBroker):
        try:
            subprocess.check_call([defines.htDigestCommand, "enable"])
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
            "/usr/share/factory/etc/localtime", "/etc/localtime", follow_symlinks=False,
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
    def __init__(self, hw_config: HwConfig, *args, disable_unboxing: bool = False, **kwargs):
        super().__init__(WizardCheckType.RESET_HW_CONFIG, *args, **kwargs)
        self._hw_config = hw_config
        self._disable_unboxing = disable_unboxing

    def reset_task_run(self, actions: UserActionBroker):
        self._hw_config.read_file()
        self._hw_config.factory_reset()
        if self._disable_unboxing:
            self._hw_config.showUnboxing = False
        self._hw_config.write()
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
        self._hw.updateMotorSensitivity(self._hw.config.tiltSensitivity, self._hw.config.towerSensitivity)


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
        if self._hw.config.uvPwm == 0:
            self._logger.error("Cannot do factory reset UV PWM not set (== 0)")
            raise MissingUVPWM()

        try:
            send_printer_data(self._hw)
        except PrinterDataSendError:
            self._logger.exception("Failed to send printer data to mqtt")
            raise


class InitiatePackingMoves(Check):
    def __init__(self, hw: Hardware):
        super().__init__(WizardCheckType.INITIATE_PACKING_MOVES)
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.towerSync()
        self._hw.tilt.sync_wait(retries=3)
        while not self._hw.isTowerSynced():
            await sleep(0.25)

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
