# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-statements
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-branches

import gettext
import hashlib
import logging
import os
import re
import subprocess
import threading
from pathlib import Path
from time import monotonic, sleep
from typing import Optional, Set, Any

import distro
from PySignal import Signal
from pydbus import SystemBus

from sl1fw import defines
from sl1fw import test_runtime
from sl1fw.api.config0 import Config0
from sl1fw.api.logs0 import Logs0
from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.configs.stats import TomlConfigStats
from sl1fw.configs.toml import TomlConfig
from sl1fw.errors.errors import (
    NotUVCalibrated,
    NotMechanicallyCalibrated,
    BootedInAlternativeSlot,
    NoFactoryUvCalib,
    ConfigException,
    MotionControllerWrongFw, MotionControllerNotResponding, MotionControllerWrongResponse,
    UVPWMComputationError,
)
from sl1fw.functions.files import save_all_remain_wizard_history, get_all_supported_files
from sl1fw.functions.miscellaneous import toBase32hex
from sl1fw.functions.system import get_octoprint_auth, get_configured_printer_model, set_configured_printer_model, \
    set_factory_uvpwm, compute_uvpwm
from sl1fw.hardware.printer_model import PrinterModel
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.libAsync import AdminCheck
from sl1fw.libAsync import SlicerProfileUpdater
from sl1fw.libDisplay import Display
from sl1fw.libHardware import Hardware
from sl1fw.libNetwork import Network
from sl1fw.slicer.slicer_profile import SlicerProfile
from sl1fw.state_actions.manager import ActionManager
from sl1fw.states.printer import PrinterState
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.wizards.calibration import CalibrationWizard
from sl1fw.wizard.wizards.self_test import SelfTestWizard
from sl1fw.wizard.wizards.sl1s_upgrade import SL1SUpgradeWizard, SL1DowngradeWizard
from sl1fw.wizard.wizards.unboxing import CompleteUnboxingWizard, KitUnboxingWizard
from sl1fw.wizard.wizards.uv_calibration import UVCalibrationWizard


class Printer:
    def __init__(self, debug_display=None):
        self.logger = logging.getLogger(__name__)
        self._printer_identifier = None
        init_time = monotonic()
        self._exception: Optional[Exception] = None
        self.exception_changed = Signal()
        self.start_time = None
        self.admin_check = None
        self.slicer_profile = None
        self.slicer_profile_updater = None
        self.state_changed = Signal()
        self.http_digest_changed = Signal()
        self.api_key_changed = Signal()
        self.data_privacy_changed = Signal()
        self.firstRun = True
        self.action_manager = ActionManager()
        self.action_manager.exposure_change.connect(self._exposure_changed)
        self.action_manager.wizard_changed.connect(self._wizard_changed)
        self.exited = threading.Event()
        self.exited.set()
        self.logger.info("SL1 firmware initializing")
        self._states: Set[PrinterState] = {PrinterState.INIT}
        self._dbus_subscriptions = []
        self.unboxed_changed = Signal()
        self.mechanically_calibrated_changed = Signal()
        self.uv_calibrated_changed = Signal()
        self.self_tested_changed = Signal()
        self._oneclick_inhibitors: Set[str] = set()

        self.logger.info("Initializing hwconfig")
        hw_config = HwConfig(
            file_path=Path(defines.hwConfigPath), factory_file_path=Path(defines.hwConfigPathFactory), is_master=True,
        )
        hw_config.add_onchange_handler(self._config_changed)

        self.runtime_config = RuntimeConfig()
        self.runtime_config.factory_mode = defines.factory_enable.exists() or TomlConfig(
            defines.factoryConfigPath
        ).load().get(
            "factoryMode", False
        )  # Single value TOML now deprecated
        self.logger.info("Factory mode: %s", self.runtime_config.factory_mode)
        self.runtime_config.show_admin = self.runtime_config.factory_mode
        try:
            hw_config.read_file()
        except ConfigException:
            self.logger.warning("Failed to read configuration file", exc_info=True)

        self.logger.info(str(hw_config))

        self.logger.info("Initializing libHardware")

        self.hw = Hardware(hw_config)

        # needed before init of other components (display etc)
        # TODO: Enable this once kit A64 do not require being turned on during manufacturing.
        #   Currently calibration needs to be performed in the factory.
        # if self.factoryMode and self.hw.isKit:
        #     self.factoryMode = False
        #     self.logger.warning("Factory mode disabled for kit")
        #

        self.logger.info("Initializing libNetwork")
        self.inet = Network(self.hw.cpuSerialNo)

        self.logger.info("Initializing display devices")
        if debug_display:
            devices = [debug_display]
        else:
            devices = []

        self.logger.info("Initializing ExposureImage")
        self.exposure_image = ExposureImage(self.hw)

        self.logger.info("Registering config D-Bus services")
        self.system_bus = SystemBus()
        self.config0_dbus = self.system_bus.publish(Config0.__INTERFACE__, Config0(self.hw))

        self.logger.info("registering log0 dbus interface")
        self.logs0_dbus = self.system_bus.publish(Logs0.__INTERFACE__, Logs0(self.hw))

        self.logger.info("Initializing libDisplay")
        self.display = Display(
            devices, self.hw, self.inet, self.exposure_image, self.runtime_config, self.action_manager,
        )
        try:
            TomlConfigStats(defines.statsData, self.hw).update_reboot_counter()
        except Exception:
            self.logger.error("Error when update 'system_up_since' statistics.")

        self.logger.info("SL1 firmware initialized in %.03f", monotonic() - init_time)

    @property
    def state(self) -> PrinterState:
        return PrinterState.get_most_important(self._states)

    def set_state(self, state: PrinterState, active: bool = True):
        old = self.state
        if active:
            self._states.add(state)
        elif state in self._states:
            self._states.remove(state)
        if old != self.state:
            self.logger.info("Printer state changed: %s -> %s", old, self.state)
            self.state_changed.emit()

    @property
    def exception(self) -> Exception:
        return self._exception

    @exception.setter
    def exception(self, value: Exception):
        self._exception = value
        self.exception_changed.emit()

    def exit(self):
        while self.state == PrinterState.INIT:
            print("Waiting for printer to leave init")
            sleep(1)

        self.set_state(PrinterState.EXIT)
        self.display.exit()
        self.action_manager.exit()
        self.exposure_image.exit()
        self.exited.wait(timeout=60)
        self.hw.exit()
        self.config0_dbus.unpublish()
        self.logs0_dbus.unpublish()
        for subscription in self._dbus_subscriptions:
            subscription.unsubscribe()

    def printer_run(self):
        self.hw.uvLed(False)
        self.hw.powerLed("normal")

        if self.hw.checkFailedBoot():
            self.exception = BootedInAlternativeSlot()

        if self.firstRun:
            # This is supposed to run on new printers detect_sla_model file is provided by a service configured to run
            # the on firstboot. The firmware does not know whether the printer has been manufactured as SL1 or SL1S it
            # has to detect its initial HW configuration on first start.
            if defines.detect_sla_model_file.exists():
                if self.hw.printer_model == PrinterModel.SL1S:
                    self.hw.config.vatRevision = 1  # Configure SL1S vat revision
                    set_factory_uvpwm(self.hw.printer_model.default_uvpwm())
                    incompatible_extension = PrinterModel.SL1
                else:
                    incompatible_extension = PrinterModel.SL1S

                # Force remove incompatible projects on firstboot
                files_to_remove = get_all_supported_files(incompatible_extension, Path(defines.internalProjectPath))
                for file in files_to_remove:
                    self.logger.info("Removing incompatible example project: %s", file)
                    os.remove(file)
                set_configured_printer_model(self.hw.printer_model)
                defines.detect_sla_model_file.unlink()
            # Also omit running upgrade/downgrade wizard if printer is SL1 and model was not set before.
            if self.hw.printer_model == PrinterModel.SL1 and not defines.printer_model.exists():
                set_configured_printer_model(self.hw.printer_model)

            config_model = get_configured_printer_model()
            if self.hw.printer_model != config_model:
                self.logger.info('Printer model change detected from "%s" to "%s"', config_model, self.hw.printer_model)
                if self.hw.printer_model == PrinterModel.SL1S:
                    self.action_manager.start_wizard(
                        SL1SUpgradeWizard(self.hw, self.exposure_image, self.runtime_config)
                    ).join()
                elif self.hw.printer_model == PrinterModel.SL1:
                    self.action_manager.start_wizard(
                        SL1DowngradeWizard(self.hw, self.exposure_image, self.runtime_config)
                    ).join()

            if (
                    not self.hw.config.is_factory_read()
                    and not self.hw.isKit
                    and self.hw.printer_model == PrinterModel.SL1
            ):
                self.exception = NoFactoryUvCalib()

            if self.hw.printer_model == PrinterModel.SL1S:
                try:
                    pwm = compute_uvpwm(self.hw)
                    self.hw.config.uvPwm = pwm
                    self.logger.info("Computed SL1S UV PWM: %s", pwm)
                except UVPWMComputationError:
                    self.logger.exception("Failed to compute UV PWM")
                    self.hw.config.uvPwm = self.hw.printer_model.default_uvpwm()

            self._make_ready_to_print()
            save_all_remain_wizard_history()

        self.action_manager.load_exposure(self.hw)
        self.display.doMenu("home")

        self.firstRun = False

    def run(self):
        # TODO: wrap everything within this method in try-catch
        # TODO: Drop self.firstRun it does seem to make no more sense
        self.logger.info("SL1 firmware starting, PID: %d", os.getpid())
        self.logger.info("System version: %s", distro.version())
        self.start_time = monotonic()

        self.logger.info("Connecting to hardware components")
        try:
            self.hw.connect()
        except (MotionControllerWrongFw, MotionControllerNotResponding, MotionControllerWrongResponse):
            self.set_state(PrinterState.UPDATING_MC)
            self.hw.flashMC()
            try:
                self.hw.connect()
                self.hw.eraseEeprom()
                self.set_state(PrinterState.UPDATING_MC, active=False)
            except Exception as e:
                self.exception = e
                self.set_state(PrinterState.EXCEPTION)
                raise e
        except Exception as e:
            self.exception = e
            self.set_state(PrinterState.EXCEPTION)
            raise e

        self.logger.info("Starting libHardware")
        self.hw.start()
        self.logger.info("Starting ExposureImage")
        self.exposure_image.start()
        self.logger.info("Starting libDisplay")
        self.display.start()

        # Since display is initialized we can catch exceptions and report problems to display
        try:
            self.logger.info("Registering event handlers")
            self.inet.register_events()
            self._dbus_subscriptions.append(
                self.system_bus.get("org.freedesktop.locale1").PropertiesChanged.connect(self._locale_changed)
            )
            self._dbus_subscriptions.append(
                self.system_bus.get("de.pengutronix.rauc", "/").PropertiesChanged.connect(self._rauc_changed)
            )
            self.logger.info("connecting cz.prusa3d.sl1.filemanager0 DBus signals")
            self._dbus_subscriptions.append(
                self.system_bus.subscribe(
                    object="/cz/prusa3d/sl1/filemanager0", signal="MediaInserted", signal_fired=self._media_inserted
                )
            )
            self._dbus_subscriptions.append(
                self.system_bus.subscribe(
                    object="/cz/prusa3d/sl1/filemanager0", signal="MediaEjected", signal_fired=self._media_ejected
                )
            )

            if not self.runtime_config.factory_mode:
                self.logger.info("Starting admin checker")
                self.admin_check = AdminCheck(self.runtime_config, self.hw, self.inet)

            self.logger.info("Loading slicer profiles")
            self.slicer_profile = SlicerProfile(defines.slicerProfilesFile)
            if not self.slicer_profile.load():
                self.logger.debug("Trying bundled slicer profiles")
                self.slicer_profile = SlicerProfile(defines.slicerProfilesFallback)
                if not self.slicer_profile.load():
                    self.logger.error("No suitable slicer profiles found")

            if self.slicer_profile.vendor:
                self.logger.info("Starting slicer profiles updater")
                self.slicer_profile_updater = SlicerProfileUpdater(
                    self.inet, self.slicer_profile, self.hw.printer_model.name
                )

            # Force update network state (in case we missed network going online)
            # All network state handler should be already registered
            self.inet.force_refresh_state()

            self.logger.info("SL1 firmware started in %.03f seconds", monotonic() - self.start_time)
        except Exception as exception:
            self.exception = exception
            self.set_state(PrinterState.EXCEPTION)
            if test_runtime.hard_exceptions:
                raise exception
            self.logger.exception("Printer run() init failed")

        try:
            self.exited.clear()
            self.set_state(PrinterState.RUNNING)
            self.printer_run()
        except Exception as exception:
            self.exception = exception
            self.set_state(PrinterState.EXCEPTION)
            if test_runtime.hard_exceptions:
                raise exception
            self.logger.exception("run() exception:")

        if self.action_manager.exposure and self.action_manager.exposure.in_progress:
            self.action_manager.exposure.waitDone()

        self.exited.set()

    def _locale_changed(self, __, changed, ___):
        if "Locale" not in changed:
            return

        lang = re.sub(r"LANG=(.*)\..*", r"\g<1>", changed["Locale"][0])

        try:
            self.logger.debug("Obtaining translation: %s", lang)
            translation = gettext.translation("sl1fw", localedir=defines.localedir, languages=[lang], fallback=True)
            self.logger.info("Installing translation: %s", lang)
            translation.install(names="ngettext")
        except (IOError, OSError):
            self.logger.exception("Translation for %s cannot be installed.", lang)

    def _rauc_changed(self, __, changed, ___):
        if "Operation" in changed:
            self.set_state(PrinterState.UPDATING, changed["Operation"] != "idle")

    def get_actual_page(self):
        return self.display.actualPage

    def _exposure_changed(self):
        self.set_state(PrinterState.PRINTING, self.action_manager.exposure and not self.action_manager.exposure.done)

    def _wizard_changed(self):
        wizard = self.action_manager.wizard
        self.set_state(PrinterState.WIZARD, wizard and wizard.state not in WizardState.finished_states())

    @property
    def id(self) -> str:
        """Return a hex string identification for the printer image."""

        if self._printer_identifier is None:
            boot = 1
            output = subprocess.check_output("lsblk -l | grep -e '/$' | awk '{print $1}'", shell=True)
            slot = output.decode().strip()
            if slot not in ["mmcblk2p2", "mmcblk2p3"]:
                boot = 0

            mac_eth0 = self.inet.get_eth_mac()
            cpu_serial = self.hw.cpuSerialNo.strip(" *")
            emmc_serial = self.hw.emmc_serial
            trusted_image = 0

            hash_hex = hashlib.sha256((emmc_serial + mac_eth0 + cpu_serial).encode()).hexdigest()
            binary = str(trusted_image) + str(boot) + bin(int(hash_hex[:10], 16))[2:-2]
            self._printer_identifier = toBase32hex(int(binary, 2))

        return self._printer_identifier

    @property
    def http_digest(self) -> bool:
        return defines.nginx_enabled.resolve() == defines.nginx_http_digest

    @http_digest.setter
    def http_digest(self, enabled: bool) -> None:
        is_enabled = self.http_digest
        if enabled:
            if not is_enabled:
                defines.nginx_enabled.unlink()
                defines.nginx_enabled.symlink_to(defines.nginx_http_digest)
                systemd1 = SystemBus().get("org.freedesktop.systemd1", "/org/freedesktop/systemd1")
                systemd1.RestartUnit("nginx.service", "replace")
                self.http_digest_changed.emit()
        else:
            if is_enabled:
                defines.nginx_enabled.unlink()
                defines.nginx_enabled.symlink_to(defines.nginx_api_key)
                systemd1 = SystemBus().get("org.freedesktop.systemd1", "/org/freedesktop/systemd1")
                systemd1.RestartUnit("nginx.service", "replace")
                self.http_digest_changed.emit()

    @property
    def api_key(self) -> str:
        """
        Get current API key

        :return: Current api key string
        """
        return get_octoprint_auth(self.logger)

    @api_key.setter
    def api_key(self, apikey: str) -> None:
        if apikey != get_octoprint_auth(self.logger):
            subprocess.check_call(["/bin/api-keygen.sh", apikey])
            self.api_key_changed.emit()

    @property
    def data_privacy(self) -> bool:
        default = True
        if not defines.remoteConfig.is_file():
            return default
        return TomlConfig(defines.remoteConfig).load().get("data_privacy", default)

    @data_privacy.setter
    def data_privacy(self, enabled: bool) -> None:
        remote_config = TomlConfig(defines.remoteConfig)
        new_data = remote_config.load()
        if enabled != new_data.get("data_privacy", True):
            new_data["data_privacy"] = enabled
            if not remote_config.save(data=new_data):
                raise ConfigException("Data privacy change failed")
            self.data_privacy_changed.emit()

    @property
    def help_page_url(self) -> str:
        url = ""
        if self.data_privacy:
            fw_version = re.sub(r"(\d*)\.(\d*)\.(\d*)-.*", r"\g<1>\g<2>\g<3>", distro.version())
            url = url + f"/{self.id}/{fw_version}"

        return url

    def _media_inserted(self, _, __, ___, ____, params):
        if self._oneclick_inhibitors:
            self.logger.info("Oneclick inhibited by: %s", self._oneclick_inhibitors)
            return

        try:
            path = params[0]
            if path and os.path.isfile(path):
                self.logger.info("Opening project %s", path)
                last_exposure = self.action_manager.exposure
                if last_exposure:
                    last_exposure.try_cancel()
                self.action_manager.new_exposure(self.hw, self.exposure_image, self.runtime_config, path)
        except (NotUVCalibrated, NotMechanicallyCalibrated):
            self.run_make_ready_to_print()
        except Exception:
            self.logger.exception("Error handling media inserted event")

    def _media_ejected(self, _, __, ___, ____, params):
        try:
            root_path = params[0]
            self.logger.info("Media ejected: %s", root_path)
            expo = self.action_manager.exposure
            if expo and expo.project and Path(root_path) in Path(expo.project.path).parents:
                expo.try_cancel()
        except Exception:
            self.logger.exception("Error handling media ejected event")

    def add_oneclick_inhibitor(self, name: str):
        if name in self._oneclick_inhibitors:
            self.logger.warning("One click inhibitor %s already registered", name)
            return

        self._oneclick_inhibitors.add(name)

    def remove_oneclick_inhibitor(self, name: str):
        if name in self._oneclick_inhibitors:
            self._oneclick_inhibitors.remove(name)
        else:
            self.logger.warning("One click inhibitor %s not registered", name)

    @property
    def unboxed(self):
        return not self.hw.config.showUnboxing

    @property
    def mechanically_calibrated(self):
        return self.hw.config.calibrated

    @property
    def uv_calibrated(self):
        return self.hw.config.uvPwm >= self.hw.printer_model.calibration_parameters(self.hw.is500khz).min_pwm

    @property
    def self_tested(self):
        return not self.hw.config.showWizard

    def run_make_ready_to_print(self):
        threading.Thread(target=self._make_ready_to_print, daemon=True).start()

    def _make_ready_to_print(self):
        if not self.runtime_config.factory_mode and self.hw.config.showUnboxing:
            if self.hw.isKit:
                unboxing = self.action_manager.start_wizard(
                    KitUnboxingWizard(self.hw, self.runtime_config), handle_state_transitions=False
                )
            else:
                unboxing = self.action_manager.start_wizard(
                    CompleteUnboxingWizard(self.hw, self.runtime_config), handle_state_transitions=False
                )
            self.logger.info("Running unboxing wizard")
            self.set_state(PrinterState.WIZARD, active=True)
            unboxing.join()
            self.logger.info("Unboxing wizard finished")

        if self.hw.config.showWizard:
            self.logger.info("Running selftest wizard")
            selftest = self.action_manager.start_wizard(
                SelfTestWizard(self.hw, self.exposure_image, self.runtime_config), handle_state_transitions=False
            )
            self.set_state(PrinterState.WIZARD, active=True)
            selftest.join()
            self.logger.info("Selftest wizard finished")

        if not self.hw.config.calibrated:
            self.logger.info("Running calibration wizard")
            calibration = self.action_manager.start_wizard(
                CalibrationWizard(self.hw, self.runtime_config), handle_state_transitions=False
            )
            self.set_state(PrinterState.WIZARD, active=True)
            calibration.join()
            self.logger.info("Calibration wizard finished")

        if not self.uv_calibrated:
            # delete also both counters and save calibration to factory partition. It's new KIT or something went wrong.
            self.logger.info("Running UV calibration wizard")
            uv_calibration = self.action_manager.start_wizard(
                UVCalibrationWizard(
                    self.hw, self.exposure_image, self.runtime_config, display_replaced=True, led_module_replaced=True
                ),
                handle_state_transitions=False,
            )
            self.set_state(PrinterState.WIZARD, active=True)
            uv_calibration.join()
            self.logger.info("UV calibration wizard finished")

        self.set_state(PrinterState.WIZARD, active=False)

    def _config_changed(self, key: str, _: Any):
        if key.lower() == "showunboxing":
            self.unboxed_changed.emit()
            return

        if key.lower() == "showwizard":
            self.self_tested_changed.emit()
            return

        if key.lower() == "calibrated":
            self.mechanically_calibrated_changed.emit()
            return

        if key.lower() == "uvpwm":
            self.uv_calibrated_changed.emit()
            return
