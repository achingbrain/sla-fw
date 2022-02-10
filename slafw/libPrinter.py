# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2021-2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import gettext
import hashlib
import json
import logging
import os
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Optional, Set, Any, Dict

import distro
from PySignal import Signal
from pydbus import SystemBus

from slafw import defines
from slafw.api.config0 import Config0
from slafw.api.logs0 import Logs0
from slafw.configs.hw import HwConfig
from slafw.configs.runtime import RuntimeConfig
from slafw.configs.stats import TomlConfigStats, TomlConfigStatsException
from slafw.configs.toml import TomlConfig
from slafw.errors import tests
from slafw.errors.errors import (
    NotUVCalibrated,
    NotMechanicallyCalibrated,
    BootedInAlternativeSlot,
    NoFactoryUvCalib,
    ConfigException,
    MotionControllerWrongFw,
    MotionControllerNotResponding,
    MotionControllerWrongResponse,
    UVPWMComputationError,
    OldExpoPanel,
    UvTempSensorFailed,
    FanFailed, PrinterException,
)
from slafw.functions.files import save_all_remain_wizard_history, get_all_supported_files
from slafw.functions.miscellaneous import toBase32hex
from slafw.functions.system import (
    get_octoprint_auth,
    get_configured_printer_model,
    set_configured_printer_model,
    set_factory_uvpwm,
    compute_uvpwm,
    FactoryMountedRW,
    reset_hostname,
)
from slafw.hardware.printer_model import PrinterModel
from slafw.image.exposure_image import ExposureImage
from slafw.libAsync import AdminCheck
from slafw.libAsync import SlicerProfileUpdater
from slafw.libHardware import Hardware
from slafw.libNetwork import Network
from slafw.slicer.slicer_profile import SlicerProfile
from slafw.state_actions.manager import ActionManager
from slafw.states.printer import PrinterState
from slafw.states.wizard import WizardState
from slafw.wizard.wizards.calibration import CalibrationWizard
from slafw.wizard.wizards.new_expo_panel import NewExpoPanelWizard
from slafw.wizard.wizards.self_test import SelfTestWizard
from slafw.wizard.wizards.sl1s_upgrade import SL1SUpgradeWizard, SL1DowngradeWizard
from slafw.wizard.wizards.unboxing import CompleteUnboxingWizard, KitUnboxingWizard
from slafw.wizard.wizards.uv_calibration import UVCalibrationWizard


class Printer:
    # pylint: disable = too-many-instance-attributes
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("SLA firmware initializing")
        self._printer_identifier: Optional[str] = None
        init_time = monotonic()
        self.exception_occurred = Signal()  # Use this one to emit recoverable errors
        self.admin_check: Optional[AdminCheck] = None
        self.slicer_profile: Optional[SlicerProfile] = None
        self.slicer_profile_updater: Optional[SlicerProfileUpdater] = None
        self.state_changed = Signal()
        self.http_digest_changed = Signal()
        self.api_key_changed = Signal()
        self.data_privacy_changed = Signal()
        self.action_manager: ActionManager = ActionManager()
        self.action_manager.exposure_change.connect(self._exposure_changed)
        self.action_manager.wizard_changed.connect(self._wizard_changed)
        self._states: Set[PrinterState] = {PrinterState.INIT}
        self._dbus_subscriptions = []
        self.unboxed_changed = Signal()
        self.mechanically_calibrated_changed = Signal()
        self.uv_calibrated_changed = Signal()
        self.self_tested_changed = Signal()
        self._oneclick_inhibitors: Set[str] = set()
        self._run_expo_panel_wizard = False

        # HwConfig and runtime config
        hw_config = HwConfig(
            file_path=Path(defines.hwConfigPath),
            factory_file_path=Path(defines.hwConfigPathFactory),
            is_master=True,
        )
        hw_config.add_onchange_handler(self._config_changed)
        self.runtime_config = RuntimeConfig()
        try:
            hw_config.read_file()
        except ConfigException:
            self.logger.warning("Failed to read configuration file", exc_info=True)
        self.logger.info(str(hw_config))

        self.logger.info("Initializing libHardware")
        self.hw = Hardware(hw_config)
        self.hw.uv_led_overheat_changed.connect(self._on_uv_led_temp_overheat)
        self.hw.fans_error_changed.connect(self._on_fans_error)

        # needed before init of other components (display etc)
        # TODO: Enable this once kit A64 do not require being turned on during manufacturing.
        #   Currently calibration needs to be performed in the factory.
        # if self.factoryMode and self.hw.isKit:
        #     self.factoryMode = False
        #     self.logger.warning("Factory mode disabled for kit")
        #

        self.logger.info("Initializing libNetwork")
        self.inet = Network(self.hw.cpuSerialNo)

        self.logger.info("Initializing ExposureImage")
        self.exposure_image = ExposureImage(self.hw)

        self.logger.info("Registering config D-Bus services")
        self.system_bus = SystemBus()
        self.config0_dbus = self.system_bus.publish(Config0.__INTERFACE__, Config0(self.hw))

        self.logger.info("registering log0 dbus interface")
        self.logs0_dbus = self.system_bus.publish(Logs0.__INTERFACE__, Logs0(self.hw))

        self.logger.info("SLA firmware initialized in %.03f", monotonic() - init_time)

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

    def has_state(self, state: PrinterState) -> bool:
        return state in self._states

    def setup(self):
        self.logger.info("SLA firmware starting, PID: %d", os.getpid())
        self.logger.info("System version: %s", distro.version())
        start_time = monotonic()

        try:
            TomlConfigStats(defines.statsData, self.hw).update_reboot_counter()
        except TomlConfigStatsException:
            self.logger.exception("Error when update 'system_up_since' statistics.")

        self._connect_hw()
        self._register_event_handlers()

        # Factory mode and admin
        self.runtime_config.factory_mode = defines.factory_enable.exists()
        self.logger.info("Factory mode: %s", self.runtime_config.factory_mode)
        self.runtime_config.show_admin = self.runtime_config.factory_mode
        if not self.runtime_config.factory_mode:
            self.admin_check = AdminCheck(self.runtime_config, self.hw, self.inet)

        self._load_slicer_profiles()

        # Force update network state (in case we missed network going online)
        # All network state handler should be already registered
        self.inet.force_refresh_state()

        if self.hw.checkFailedBoot():
            self.exception_occurred.emit(BootedInAlternativeSlot())

        # Model detection
        self._model_detect()
        if self.hw.printer_model == PrinterModel.SL1 and not defines.printer_model.exists():
            set_configured_printer_model(self.hw.printer_model)  # Configure model for old SL1 printers
        self._model_update()
        self.logger.info("Printer model: %s", self.hw.printer_model)

        # UV calibration
        if not self.hw.config.is_factory_read() and not self.hw.isKit and self.hw.printer_model == PrinterModel.SL1:
            self.exception_occurred.emit(NoFactoryUvCalib())
        self._compute_uv_pwm()

        # Past exposures
        save_all_remain_wizard_history()
        self.action_manager.load_exposure(self.hw)

        # Finish startup
        self.set_state(PrinterState.RUNNING)
        self.logger.info("SLA firmware started in %.03f seconds", monotonic() - start_time)

    def stop(self):
        self.action_manager.exit()
        self.exposure_image.exit()
        self.hw.exit()
        self.config0_dbus.unpublish()
        self.logs0_dbus.unpublish()
        for subscription in self._dbus_subscriptions:
            subscription.unsubscribe()

    def _connect_hw(self):
        self.logger.info("Connecting to hardware components")
        try:
            self.hw.connect()
        except (MotionControllerWrongFw, MotionControllerNotResponding, MotionControllerWrongResponse):
            self.logger.info("HW connect failed with a recoverable error, flashing MC firmware")
            self.set_state(PrinterState.UPDATING_MC)
            self.hw.flashMC()
            self.hw.connect()
            self.hw.eraseEeprom()
            self.set_state(PrinterState.UPDATING_MC, active=False)

        self.logger.info("Starting libHardware")
        self.hw.start()
        self.logger.info("Starting ExposureImage")
        self.exposure_image.start()
        self.hw.uvLed(False)
        self.hw.power_led.reset()

    def _register_event_handlers(self):
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

    def _load_slicer_profiles(self):
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

    def _model_detect(self):
        # This is supposed to run on new printers detect_sla_model file is provided by a service configured to run
        # on the firstboot. The firmware does not know whether the printer has been manufactured as SL1 or SL1S it
        # has to detect its initial HW configuration on first start.
        # M1 is detected as SL1S and switched in admin
        if not defines.detect_sla_model_file.exists():
            return

        self.hw.config.vatRevision = self.hw.printer_model.options.vat_revision
        if self.hw.printer_model == PrinterModel.SL1S:
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

    def _model_update(self):
        config_model = get_configured_printer_model()
        if self.hw.printer_model == config_model:
            return

        self.logger.info('Printer model change detected from "%s" to "%s"', config_model, self.hw.printer_model)
        if self.hw.printer_model == PrinterModel.SL1S:
            self.action_manager.start_wizard(
                SL1SUpgradeWizard(self.hw, self.exposure_image, self.runtime_config)
            ).join()
        elif self.hw.printer_model == PrinterModel.SL1:
            self.action_manager.start_wizard(
                SL1DowngradeWizard(self.hw, self.exposure_image, self.runtime_config)
            ).join()
        try:
            reset_hostname(self.hw.printer_model)  # set model specific default hostname
        except PrinterException:
            self.logger.exception("Failed to reset hostname after model ")

    def _compute_uv_pwm(self):
        if not self.hw.printer_model.options.has_UV_calculation:
            return

        self._detect_new_expo_panel()
        try:
            pwm = compute_uvpwm(self.hw)
            self.hw.config.uvPwm = pwm
            self.logger.info("Computed UV PWM: %s", pwm)
        except UVPWMComputationError:
            self.logger.exception("Failed to compute UV PWM")
            self.hw.config.uvPwm = self.hw.printer_model.default_uvpwm()

    def _locale_changed(self, __, changed, ___):
        if "Locale" not in changed:
            return

        lang = re.sub(r"LANG=(.*)\..*", r"\g<1>", changed["Locale"][0])

        try:
            self.logger.debug("Obtaining translation: %s", lang)
            translation = gettext.translation("slafw", localedir=defines.localedir, languages=[lang], fallback=True)
            self.logger.info("Installing translation: %s", lang)
            translation.install(names="ngettext")
        except (IOError, OSError):
            self.logger.exception("Translation for %s cannot be installed.", lang)

    def _rauc_changed(self, __, changed, ___):
        if "Operation" in changed:
            self.set_state(PrinterState.UPDATING, changed["Operation"] != "idle")

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
        return defines.nginx_http_digest.exists()

    @http_digest.setter
    def http_digest(self, enabled: bool) -> None:
        is_enabled = self.http_digest
        if enabled:
            if not is_enabled:
                defines.nginx_http_digest.touch()
        else:
            if is_enabled:
                defines.nginx_http_digest.unlink()
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
            url += f"/{self.id}/{fw_version}"

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
            raise

    def _media_ejected(self, _, __, ___, ____, params):
        try:
            root_path = params[0]
            self.logger.info("Media ejected: %s", root_path)
            expo = self.action_manager.exposure
            if expo and expo.project and Path(root_path) in Path(expo.project.path).parents:
                expo.try_cancel()
        except Exception:
            self.logger.exception("Error handling media ejected event")
            raise

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

        if self._run_expo_panel_wizard:
            self.logger.info("Running new expo panel wizard")
            new_expo_panel_wizard = self.action_manager.start_wizard(
                NewExpoPanelWizard(self.hw), handle_state_transitions=False
            )
            self.set_state(PrinterState.WIZARD, active=True)
            new_expo_panel_wizard.join()
            self.logger.info("New expo panel wizard finished")

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

    def inject_exception(self, code: str):
        exception = tests.get_instance_by_code(code)
        self.logger.info("Injecting exception %s", exception)
        self.exception_occurred.emit(exception)

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

    def _detect_new_expo_panel(self):
        panel_sn = self.hw.exposure_screen.panel.serial_number()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(defines.expoPanelLogPath, "r") as f:
                log = json.load(f)
            last_key = list(log)[-1]
            if log[last_key]["panel_sn"] != panel_sn:  # if new panel detected
                for record in log.values():  # check if panel was already used in this printer
                    if record["panel_sn"] == panel_sn and "counter_s" in record.keys():
                        self.exception_occurred.emit(
                            OldExpoPanel(counter_h=round(record["counter_s"] / 3600))
                        )  # show warning about used panel
                self._run_expo_panel_wizard = True
                # Force selftest and calibration with new display as:
                # - Printer internals might have been tempered with
                # - Display plane might have shifted
                self.hw.config.showWizard = True
                self.hw.config.calibrated = False
                self.hw.config.write()

        except FileNotFoundError:  # no records found
            with FactoryMountedRW():
                with open(defines.expoPanelLogPath, "w") as f:
                    self.logger.info("No records in expo panel logs. Adding first record: %s", panel_sn)
                    record = dict()
                    record[timestamp] = {"panel_sn": panel_sn}
                    json.dump(record, f, indent=2)

    def _on_uv_led_temp_overheat(self, overheated: bool):
        if not overheated:
            self.power_led.remove_error()
            self.set_state(PrinterState.OVERHEATED, False)
        else:
            self.logger.error("UV LED overheated")
            self.power_led.set_error()
            if not self.has_state(PrinterState.PRINTING):
                self.hw.uvLed(False)
            self.set_state(PrinterState.OVERHEATED, True)

            if self.hw.getUvLedTemperature() < 0:
                self.logger.error("UV temperature reading failed")
                self.hw.uvLed(False)
                self.exception_occurred.emit(UvTempSensorFailed())

    def _on_fans_error(self, fans_error: Dict[str, bool]):
        if not any(fans_error.values()):
            self.logger.debug("Fans recovered")
            return

        failed_fans_text = self.hw.getFansErrorText()
        self.logger.error("Detected fan error, text: %s", failed_fans_text)
        # Report error only if not printing to avoid mixing exposure and printer error reports
        if not self.has_state(PrinterState.PRINTING):
            fans_state = self.hw.getFansError().values()
            failed_fans = [num for num, state in enumerate(fans_state) if state]
            failed_fan_names = [self.hw.fans[i].name for i in failed_fans]
            failed_fans_text = self.hw.getFansErrorText()
            self.exception_occurred.emit(FanFailed(failed_fans, failed_fan_names, failed_fans_text))
