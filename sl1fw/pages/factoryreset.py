# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=too-many-branches
# pylint: disable=too-many-statements

import os
import subprocess
from shutil import copyfile, rmtree
from time import sleep

import pydbus
from gi.repository import GLib
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw import defines
from sl1fw.api.decorators import wrap_exception
from sl1fw.errors.errors import (
    MissingWizardData,
    MissingCalibrationData,
    MissingUVCalibrationData,
    PrinterDataSendError,
)
from sl1fw.errors.exceptions import ConfigException, MotionControllerException, get_exception_code
from sl1fw.functions.system import shut_down, save_factory_mode, send_printer_data, FactoryMountedRW
from sl1fw.functions.files import ch_mode_owner
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.calibration import PageCalibrationStart
from sl1fw.pages.uvcalibration import PageUvCalibration
from sl1fw.pages.wait import PageWait
from sl1fw.states.display import DisplayState


@page
class PageFactoryReset(Page):
    Name = "factoryreset"

    NETWORK_MANAGER = "org.freedesktop.NetworkManager"

    def __init__(self, display):
        super(PageFactoryReset, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Are you sure?")
        self.checkPowerbutton = False
        self.eraseProjects = False

    def show(self):
        self.items.update(
            {"text": _("Do you really want to perform the factory reset?\n\n" "All settings will be erased!\n" + ("All projects on Interenal storage will be removed!" if self.eraseProjects else "Projects will stay untouched."))}
        )
        super().show()

    def yesButtonRelease(self):
        return self._do_factory_reset()

    def _do_factory_reset(self):
        self.logger.info("Starting factory reset with factory mode: %s", self.display.runtime_config.factory_mode)
        if self.display.runtime_config.factory_mode and self.display.hwConfig.uvPwm == 0:
            self.logger.error("Cannot do factory reset UV PWM not set (== 0)")
            self.display.pages["error"].setParams(code=Sl1Codes.MISSING_UVPWM_SETTINGS.raw_code)
            return "error"

        self.display.state = DisplayState.FACTORY_RESET

        page_wait = PageWait(self.display)
        page_wait.show()

        if self.display.runtime_config.factory_mode:
            page_wait.showItems(line1=_("Sending printer data"))
            try:
                send_printer_data(self.display.hw, self.display.hwConfig)
            except PrinterDataSendError as error:
                self.logger.exception("Failed to send printer data to mqtt")
                if isinstance(error, MissingWizardData):
                    back_fce = lambda: "wizardinit"
                elif isinstance(error, MissingCalibrationData):
                    back_fce = lambda: PageCalibrationStart.Name
                elif isinstance(error, MissingUVCalibrationData):
                    back_fce = lambda: PageUvCalibration.Name
                else:
                    back_fce = None

                self.display.state = DisplayState.IDLE
                self.display.pages["error"].setParams(
                    backFce=back_fce,
                    code=get_exception_code(error).raw_code,
                    params=wrap_exception(error),
                )
                return "error"

        # http://www.wavsource.com/snds_2018-06-03_5106726768923853/movie_stars/schwarzenegger/erased.wav
        page_wait.showItems(line1=_("Relax... You've been erased."))
        self._reset_printer_settings()
        self._reset_system_settings()
        self._erase_projects()

        # continue only in factory mode
        if not self.display.runtime_config.factory_mode:
            self.logger.info("Factory reset shutdown")
            shut_down(self.display.hw, reboot=True)
            return None

        # disable factory mode
        self._disableFactory()

        return self._pack_to_box(page_wait)

    def _reset_printer_settings(self):
        # save hwConfig
        try:
            self.display.hwConfig.read_file()
            self.display.hwConfig.factory_reset()
            # do not display unpacking after user factory reset
            if not self.display.runtime_config.factory_mode:
                self.display.hwConfig.showUnboxing = False
            self.display.hwConfig.write()
            rmtree(defines.wizardHistoryPath, ignore_errors=True)
        except ConfigException:
            self.logger.exception("Failed to do factory reset on config")

        # erase MC EEPROM
        try:
            self.display.hw.eraseEeprom()
        except MotionControllerException:
            self.logger.exception("Failed to erase EEPROM")

        # set homing profiles to factory defaults
        try:
            self.display.hw.updateMotorSensitivity(
                self.display.hwConfig.tiltSensitivity, self.display.hwConfig.towerSensitivity
            )
        except MotionControllerException:
            self.logger.exception("Failed to set default sensitivity profiles")

        # Reset user UV calibration data
        try:
            os.remove(defines.uvCalibDataPath)
        except (FileNotFoundError, PermissionError):
            self.logger.exception("Failed to remove user UV calibration data")

        # Remove downloaded slicer profiles
        try:
            os.remove(defines.slicerProfilesFile)
        except (FileNotFoundError, PermissionError):
            self.logger.exception("Failed to remove remove downloaded slicer profiles")

    def _reset_system_settings(self):
        system_bus = pydbus.SystemBus()

        # Reset hostname
        try:
            hostnamectl = system_bus.get("org.freedesktop.hostname1")
            hostnamectl.SetStaticHostname(defines.default_hostname, False)
            hostnamectl.SetHostname(defines.default_hostname, False)
        except GLib.GError:
            self.logger.exception("Failed to set hostname to factory default")

        # Reset apikey (will be regenerated on next boot)
        try:
            os.remove(defines.apikeyFile)
        except FileNotFoundError:
            self.logger.exception("Failed to remove api.key")

        # Reset remote config (don't delete it)
        try:
            with open(defines.remoteConfig, 'w') as fp:
                fp.truncate(0)
        except FileNotFoundError:
            self.logger.exception("Failed to clean remoteConfig.toml")

        # Reset http_digest
        try:
            subprocess.check_call([defines.htDigestCommand, "enable"])
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.exception("Failed to reset http digest config")

        # Reset wifi
        try:
            for connection in system_bus.get(self.NETWORK_MANAGER, "Settings").ListConnections():
                if system_bus.get(self.NETWORK_MANAGER, connection).GetSettings()["connection"]["type"] == "802-11-wireless":
                    try:
                        system_bus.get(self.NETWORK_MANAGER, connection).Delete()
                    except GLib.GError:
                        self.logger.exception("Failed to delete connection %s", connection)
        except GLib.GError:
            self.logger.exception("Failed to reset wifi config")

        # Reset timezone
        try:
            os.remove("/etc/localtime")
        except (FileNotFoundError, PermissionError):
            self.logger.exception("Failed to remove old timezone configuration")

        try:
            copyfile("/usr/share/factory/etc/localtime", "/etc/localtime", follow_symlinks=False)
        except (OSError, FileNotFoundError, PermissionError):
            self.logger.exception("Failed to reset timezone")

        # Reset NTP
        try:
            system_bus.get("org.freedesktop.timedate1").SetNTP(True, False)
        except GLib.GError:
            self.logger.exception("Failed to set NTP to factory default")

        # Reset locale
        try:
            system_bus.get("org.freedesktop.locale1").SetLocale(["C"], False)
        except GLib.GError:
            self.logger.exception("Setting locale failed")

        # Reset user UV calibration data
        try:
            os.remove(defines.uvCalibDataPath)
        except (FileNotFoundError, PermissionError):
            self.logger.exception("Failed to remove user UV calibration data")

        # Remove downloaded slicer profiles
        try:
            os.remove(defines.slicerProfilesFile)
        except (FileNotFoundError, PermissionError):
            self.logger.exception("Failed to remove downloaded slicer profiles")

    def _erase_projects(self, force = False):
        if self.eraseProjects or force:
            try:
                rmtree(defines.internalProjectPath)
                if not os.path.exists(defines.internalProjectPath):
                    os.makedirs(defines.internalProjectPath)
                    ch_mode_owner(defines.internalProjectPath)
            except (OSError, FileNotFoundError, PermissionError):
                self.logger.exception("Failed to erase projects from Internal storage")

    def _pack_to_box(self, page_wait: PageWait):
        # do not do packing moves for kit
        if self.display.hw.isKit:
            shut_down(self.display.hw)
            return None

        page_wait.showItems(line1=_("Printer is being set to packing positions"))
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait(retries=3)
        while not self.display.hw.isTowerSynced():
            sleep(0.25)

        # move tilt and tower to packing position
        self.display.hw.setTiltProfile("homingFast")
        self.display.hw.tiltMoveAbsolute(defines.defaultTiltHeight)
        while self.display.hw.isTiltMoving():
            sleep(0.25)

        self.display.hw.setTowerProfile("homingFast")
        self.display.hw.towerMoveAbsolute(self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(74))
        while self.display.hw.isTowerMoving():
            sleep(0.25)

        # at this height may be screwed down tank and inserted protective foam
        self.display.pages["confirm"].setParams(
            continueFce=self._finish_packaging_moves, text=_("Insert protective foam")
        )
        return "confirm"

    def _finish_packaging_moves(self):
        page_wait = PageWait(self.display, line1=_("Printer is being set to packing positions"))
        page_wait.show()

        # slightly press the foam against printers base
        self.display.hw.towerMoveAbsolute(self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(93))
        while self.display.hw.isTowerMoving():
            sleep(0.25)

        shut_down(self.display.hw)

    def noButtonRelease(self):
        # FIXME - to Page()
        return self.backButtonRelease()

    def _disableFactory(self):
        self.logger.info("Factory reset - disabling factory mode")
        with FactoryMountedRW():
            if defines.factory_enable.exists():
                defines.factory_enable.unlink()
            if defines.ssh_service_enabled.exists():
                defines.ssh_service_enabled.unlink()
            if defines.serial_service_enabled.exists():
                defines.serial_service_enabled.unlink()
            if not save_factory_mode(False):
                self.logger.error("Factory mode was not disabled!")
