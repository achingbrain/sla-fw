# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, TYPE_CHECKING, Any, Optional

import distro
import pydbus
from deprecation import deprecated
from pydbus.generic import signal

from slafw import defines
from slafw.api.decorators import (
    dbus_api,
    state_checked,
    cached,
    auto_dbus,
    DBusObjectPath,
    wrap_dict_data,
    auto_dbus_signal,
)
from slafw.api.examples0 import Examples0
from slafw.api.exposure0 import Exposure0
from slafw.configs.stats import TomlConfigStats
from slafw.errors import tests
from slafw.errors.errors import ReprintWithoutHistory, PrinterException
from slafw.functions.files import get_all_supported_files
from slafw.functions.system import shut_down
from slafw.hardware.base.fan import Fan
from slafw.hardware.power_led_action import WarningAction
from slafw.project.functions import check_ready_to_print
from slafw.state_actions.examples import Examples
from slafw.states.examples import ExamplesState
from slafw.states.printer import Printer0State
from slafw.wizard.wizards.calibration import CalibrationWizard
from slafw.wizard.wizards.displaytest import DisplayTestWizard
from slafw.wizard.wizards.factory_reset import PackingWizard, FactoryResetWizard
from slafw.wizard.wizards.self_test import SelfTestWizard
from slafw.wizard.wizards.tank_surface_cleaner import TankSurfaceCleaner
from slafw.wizard.wizards.unboxing import CompleteUnboxingWizard, KitUnboxingWizard
from slafw.wizard.wizards.uv_calibration import UVCalibrationWizard

if TYPE_CHECKING:
    from slafw.libPrinter import Printer


@dbus_api
class Printer0:
    """
    This is a 0 revision of the printer public API. This contains all the stuff that the display/pages interface can do,
    but some parts are still not implemented. As the structure was preserved from pages for easy porting and new methods
    were added as needed the API is not looking very well.

    Keep implementation out of this file. Methods here should only adapt interfaces and reformat data.

    # Error handling
    Errors and exception come with data dictionary that is supposed to include at last a "code" member pointing to a
    standard Prusa error code.

    - Internal non-fatal errors at startup are reported using exception signal. The signal includes exception data
      dictionary.
    - Fatal errors result in printer crash and are supposed to be resolved by systemd
    - Errors resulting from DBus calls are reported as native DBus errors. Exception data dictionary is embedded as Json
      into a DBus error message.
    """

    __INTERFACE__ = "cz.prusa3d.sl1.printer0"

    PropertiesChanged = signal()

    def __init__(self, printer: Printer):
        self.printer = printer
        self._examples: Optional[Examples] = None
        self._examples0: Optional[Examples0] = None
        self._examples_registration = None
        self._unpacking = None
        self._wizard = None
        self._calibration = None

        self.printer.state_changed.connect(self._on_state_changed)
        self.printer.http_digest_changed.connect(self._on_http_digest_changed)
        self.printer.api_key_changed.connect(self._on_api_key_changed)
        self.printer.data_privacy_changed.connect(self._on_data_privacy_changed)
        self.printer.hw.uv_led_fan.rpm_changed.connect(self._on_uv_led_fan_changed)
        self.printer.hw.uv_led_fan.error_changed.connect(self._on_uv_led_fan_changed)
        self.printer.hw.blower_fan.rpm_changed.connect(self._on_blower_fan_changed)
        self.printer.hw.blower_fan.error_changed.connect(self._on_blower_fan_changed)
        self.printer.hw.rear_fan.rpm_changed.connect(self._on_rear_fan_changed)
        self.printer.hw.rear_fan.error_changed.connect(self._on_rear_fan_changed)
        self.printer.hw.uv_led_temp.value_changed.connect(self._on_uv_temp_changed)
        self.printer.hw.ambient_temp.value_changed.connect(self._on_ambient_temp_changed)
        self.printer.hw.cpu_temp_changed.connect(self._on_cpu_temp_changed)
        self.printer.hw.led_voltages_changed.connect(self._on_led_voltages_changed)
        self.printer.hw.resin_sensor_state_changed.connect(self._on_resin_sensor_changed)
        self.printer.hw.cover_state_changed.connect(self._on_cover_state_changed)
        self.printer.hw.power_button_state_changed.connect(self._on_power_switch_state_changed)
        self.printer.action_manager.exposure_change.connect(self._on_exposure_change)
        self.printer.hw.mc_sw_version_changed.connect(self._on_controller_sw_version_change)
        self.printer.hw.uv_statistics_changed.connect(self._on_uv_statistics_changed)
        self.printer.runtime_config.factory_mode_changed.connect(self._on_factory_mode_changed)
        self.printer.runtime_config.show_admin_changed.connect(self._on_admin_enabled_changed)
        self.printer.hw.tower_position_changed.connect(self._on_tower_position_changed)
        self.printer.hw.tilt_position_changed.connect(self._on_tilt_position_changed)
        self.printer.unboxed_changed.connect(self._on_unboxed_changed)
        self.printer.self_tested_changed.connect(self._on_self_tested_changed)
        self.printer.mechanically_calibrated_changed.connect(self._on_mechanically_calibrated_changed)
        self.printer.uv_calibrated_changed.connect(self._on_uv_calibrated_changed)
        self.printer.exception_occurred.connect(self._on_exception)

    def _on_state_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"state": self.state}, [])

    def _on_exception(self, exception: Exception):
        self.exception(wrap_dict_data(PrinterException.as_dict(exception)))

    def _on_http_digest_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"http_digest": self.http_digest}, [])

    def _on_api_key_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"api_key": self.api_key}, [])

    def _on_data_privacy_changed(self):
        self.PropertiesChanged(
            self.__INTERFACE__, {"data_privacy": self.data_privacy, "help_page_url": self.help_page_url}, []
        )

    def _on_uv_led_fan_changed(self, _):
        self.PropertiesChanged(self.__INTERFACE__, {"uv_led_fan": self.uv_led_fan}, [])

    def _on_blower_fan_changed(self, _):
        self.PropertiesChanged(self.__INTERFACE__, {"blower_fan": self.blower_fan}, [])

    def _on_rear_fan_changed(self, _):
        self.PropertiesChanged(self.__INTERFACE__, {"rear_fan": self.rear_fan}, [])

    def _on_uv_temp_changed(self, uv_temp: float):
        self.PropertiesChanged(self.__INTERFACE__, {"uv_led_temp": uv_temp}, [])

    def _on_ambient_temp_changed(self, ambient_temp: float):
        self.PropertiesChanged(self.__INTERFACE__, {"ambient_temp": ambient_temp}, [])

    def _on_cpu_temp_changed(self, value):
        self.PropertiesChanged(self.__INTERFACE__, {"cpu_temp": value}, [])

    def _on_led_voltages_changed(self, value):
        self.PropertiesChanged(self.__INTERFACE__, {"leds": self._format_leds(value)}, [])

    def _on_resin_sensor_changed(self, value: bool):
        self.PropertiesChanged(self.__INTERFACE__, {"resin_sensor_state": value}, [])

    def _on_cover_state_changed(self, value):
        self.PropertiesChanged(self.__INTERFACE__, {"cover_state": value}, [])

    def _on_power_switch_state_changed(self, value):
        self.PropertiesChanged(self.__INTERFACE__, {"power_switch_state": value}, [])

    def _on_exposure_change(self):
        self.PropertiesChanged(self.__INTERFACE__, {"current_exposure": self.current_exposure}, [])

    def _on_controller_sw_version_change(self):
        self.PropertiesChanged(self.__INTERFACE__, {"controller_sw_version": self.controller_sw_version}, [])

    def _on_uv_statistics_changed(self, value):
        self.PropertiesChanged(self.__INTERFACE__, {"uv_statistics": self._format_uv_statistics(value)}, [])

    def _on_factory_mode_changed(self, value):
        self.PropertiesChanged(self.__INTERFACE__, {"factory_mode": value}, [])

    def _on_admin_enabled_changed(self, value):
        self.PropertiesChanged(self.__INTERFACE__, {"admin_enabled": value}, [])

    def _on_tower_position_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"tower_position_nm": self.tower_position_nm}, [])

    def _on_tilt_position_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"tilt_position": self.tilt_position}, [])

    def _on_unboxed_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"unboxed": self.unboxed}, [])

    def _on_self_tested_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"self_tested": self.self_tested}, [])

    def _on_mechanically_calibrated_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"mechanically_calibrated": self.mechanically_calibrated}, [])

    def _on_uv_calibrated_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"uv_calibrated": self.uv_calibrated}, [])

    @auto_dbus
    @property
    def state(self) -> int:
        """
        Get global printer state

        :return: Global printer state
        """
        state = self.printer.state.to_state0()
        if state:
            return state.value

        return Printer0State.IDLE.value

    @auto_dbus_signal
    def exception(self, value: Dict[str, Any]):
        pass

    @auto_dbus
    @property
    def http_digest(self) -> bool:
        return self.printer.http_digest

    @auto_dbus
    @http_digest.setter
    def http_digest(self, enabled: bool) -> None:
        self.printer.http_digest = enabled

    @auto_dbus
    def beep(self, frequency_hz: int, length_ms: int) -> None:
        """
        Motion controller beeper beep

        :param frequency_hz: Beep frequency in Hz
        :param length_ms: Beep duration in ms
        :return: None
        """
        self.printer.hw.beep(frequency_hz, length_ms / 1000)

    @auto_dbus
    @state_checked([Printer0State.IDLE, Printer0State.EXCEPTION, Printer0State.ADMIN])
    def poweroff(self, do_shutdown: bool, reboot: bool) -> None:
        """
        Shut down the printer

        :param do_shutdown: True for real action, False just restarts the printer logic
        :param reboot: True does reboot, False means real shutdown
        :return: None
        """
        if do_shutdown:
            shut_down(self.printer.hw, reboot=reboot)
        else:
            self.printer.hw.uvLed(False)
            self.printer.hw.motorsRelease()

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def tower_home(self) -> None:
        """
        Home tower axis
        """
        self.printer.hw.tower_home()

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def tilt_home(self) -> None:
        """
        Home tilt axis

        :return: None
        """
        with WarningAction(self.printer.hw.power_led):
            self.printer.hw.tilt.level()

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def disable_motors(self) -> None:
        """
        Disable motors

        This ends the annoying sound.

        :return: None
        """
        self.printer.hw.motorsRelease()

    @auto_dbus
    @state_checked([Printer0State.IDLE, Printer0State.WIZARD])
    def tower_move(self, speed: int) -> bool:
        """
        Start / stop tower movement

        TODO: This should be checked by heartbeat or the command should have limited ttl
        TODO: Allowed for calibration as calibration does not have dedicated control object, yet
        TODO: Was limited only for calibration wizard. Now its allowed in all wizards.
              We may want to restrict it back just for calibration.

        :param: Movement speed

            :-2: Fast down
            :-1: Slow down
            :0: Stop
            :1: Slow up
            :2: Fast up
        :return: True on success, False otherwise
        """
        return self.printer.hw.tower_move(speed)

    @auto_dbus
    @state_checked([Printer0State.IDLE, Printer0State.WIZARD])
    def tilt_move(self, speed: int) -> bool:
        """
        Start / stop tilt movement

        TODO: This should be checked by heartbeat or the command should have limited ttl
        TODO: Allowed for calibration as calibration does not have dedicated control object, yet
        TODO: Was limited only for calibration wizard. Now its allowed in all wizards.
              We may want to restrict it back just for calibration.

        :param: Movement speed

           :-2: Fast down
           :-1: Slow down
           :0: Stop
           :1: Slow up
           :2: Fast up
        :return: True on success, False otherwise
        """
        return self.printer.hw.tilt.move(speed)

    @property
    def tower_position_nm(self) -> int:
        """
        Read or set tower position in nm
        """
        return self.printer.hw.tower_position_nm

    @auto_dbus
    @tower_position_nm.setter
    @state_checked(Printer0State.IDLE)
    def tower_position_nm(self, position_nm: int) -> None:
        self.printer.hw.tower_position_nm = position_nm

    @property
    def tilt_position(self) -> int:
        """
        Read or set tilt position in micro-steps
        """
        return self.printer.hw.tilt.position

    @auto_dbus
    @tilt_position.setter
    @state_checked(Printer0State.IDLE)
    def tilt_position(self, micro_steps: int):
        self.printer.hw.tilt.position = micro_steps

    @auto_dbus
    @property
    @cached()
    def serial_number(self) -> str:
        """
        Get A64 serial

        :return: A64 serial number
        """
        return self.printer.hw.cpuSerialNo

    @auto_dbus
    @property
    @cached()
    def system_name(self) -> str:
        """
        Get system name

        :return: System distribution name
        """
        return distro.name()

    @auto_dbus
    @property
    @cached()
    def system_version(self) -> str:
        """
        Get system version

        :return: System distribution version
        """
        return distro.version()

    @auto_dbus
    @property
    def uv_led_fan(self) -> Dict[str, int]:
        return self._format_fan(self.printer.hw.uv_led_fan)

    @auto_dbus
    @property
    def blower_fan(self) -> Dict[str, int]:
        return self._format_fan(self.printer.hw.blower_fan)

    @auto_dbus
    @property
    def rear_fan(self) -> Dict[str, int]:
        return self._format_fan(self.printer.hw.rear_fan)

    @staticmethod
    def _format_fan(fan: Fan):
        return {
            "rpm": fan.rpm,
            "error": 1 if fan.error else 0
        }

    @auto_dbus
    @property
    def uv_led_temp(self) -> float:
        return self.printer.hw.uv_led_temp.value

    @auto_dbus
    @property
    def ambient_temp(self) -> float:
        return self.printer.hw.ambient_temp.value

    @auto_dbus
    @property
    @cached(validity_s=5)
    def cpu_temp(self) -> float:
        """
        Get A64 temperature

        :return: A64 CPU temperature
        """
        return self.printer.hw.getCpuTemperature()

    @auto_dbus
    @property
    @cached(validity_s=5)
    def leds(self) -> Dict[str, float]:
        """
        Get UV LED voltages

        :return: Dictionary mapping from LED channel name to voltage value
        """
        return self._format_leds(self.printer.hw.getVoltages(1))

    @staticmethod
    def _format_leds(leds):
        return {"led%d_voltage_volt" % i: v for i, v in enumerate(leds)}

    @auto_dbus
    @property
    @cached(validity_s=5)
    def uv_statistics(self) -> Dict[str, int]:
        """
        Get UV statistics

        :return: Dictionary mapping from statistics name to integer value
        """
        return self._format_uv_statistics(self.printer.hw.getUvStatistics())

    @staticmethod
    def _format_uv_statistics(statistics):
        # Saturate the value at max 32bit signed int due to DBus and UI
        # DBus can handle more if we pass
        return {"uv_stat%d" % i: min(v, 0x7FFFFFFF) for i, v in enumerate(statistics)}
        # uv_stats0 - time counter [s] # TODO: add uv average current,

    @auto_dbus
    @property
    @cached(validity_s=5)
    def controller_sw_version(self) -> str:
        """
        Get motion controller version

        :return: Version string
        """
        return self.printer.hw.mcFwVersion

    @auto_dbus
    @property
    @cached(validity_s=5)
    def controller_serial(self) -> str:
        """
        Get motion controller serial

        :return: Serial number as string
        """
        return self.printer.hw.mcSerialNo

    @auto_dbus
    @property
    @cached(validity_s=5)
    def controller_revision(self) -> str:
        return self.printer.hw.mcBoardRevision

    @auto_dbus
    @property
    @cached(validity_s=5)
    def api_key(self) -> str:
        """
        Get current API key

        :return: Current api key string
        """
        return self.printer.api_key

    @auto_dbus
    @api_key.setter
    def api_key(self, apikey: str) -> None:
        self.printer.api_key = apikey

    @auto_dbus
    def enable_resin_sensor(self, value: bool) -> None:
        """
        Set resin sensor enabled flag

        :param value: Enabled / disabled as boolean
        :return: None
        """
        self.printer.hw.resinSensor(value)

    @auto_dbus
    @property
    @cached(validity_s=0.5)
    def resin_sensor_state(self) -> bool:
        """
        Get resin sensor state

        :return: True if enabled, False otherwise
        """
        return self.printer.hw.getResinSensorState()

    @auto_dbus
    @property
    @cached(validity_s=0.5)
    def cover_state(self) -> bool:
        """
        Get cover state

        :return: True of closed, False otherwise
        """
        return self.printer.hw.isCoverClosed()

    @auto_dbus
    @property
    @cached(validity_s=0.5)
    def power_switch_state(self) -> bool:
        """
        Get power switch state

        :return: True if pressed, False otherwise
        """
        return self.printer.hw.getPowerswitchState()

    @auto_dbus
    @property
    def factory_mode(self) -> bool:
        """
        Check for factory mode

        :return: True if in factory mode, False otherwise
        """
        return self.printer.runtime_config.factory_mode

    @auto_dbus
    @state_checked([Printer0State.IDLE])
    def download_examples(self) -> DBusObjectPath:
        """
        Initiate examples download

        :return: Download object path
        """
        # Examples download in progress, just return existing object
        if self._examples and self._examples.state not in ExamplesState.get_finished():
            return DBusObjectPath(Examples0.DBUS_PATH)

        # Unregister existing instance and join examples thread
        if self._examples_registration:
            self._examples_registration.unpublish()
            self._examples_registration = None
        if self._examples:
            self._examples.join()

        # Initiate new examples download
        self._examples = Examples(self.printer.inet, self.printer.model)
        self._examples0 = Examples0(self._examples)
        self._examples_registration = pydbus.SystemBus().publish(
            Examples0.__INTERFACE__, (Examples0.DBUS_PATH, self._examples0)
        )
        self._examples.start()
        return DBusObjectPath(Examples0.DBUS_PATH)

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def update_firmware(self, fw_file: str):
        """
        Initiate firmware update

        Pass-through to Rauc install. Only works when printer in idle state.
        """
        # pylint: disable=no-self-use
        pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"].InstallBundle(
            fw_file, dict()
        )

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def check_ready(self) -> None:
        """
        Check printer is ready to print

        This raises subset of exceptions the print raises, but does not do anything on success
        :return: None
        """
        check_ready_to_print(self.printer.hw.config, self.printer.hw.uv_led.parameters)

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def print(self, project_path: str, auto_advance: bool) -> DBusObjectPath:
        """
        Start printing project

        :param project_path: Path to project in printer filesystem
        :param auto_advance: Automatic print

        :returns: Print task object
        """
        expo = self.printer.action_manager.new_exposure(
            self.printer.hw,
            self.printer.exposure_image,
            self.printer.runtime_config,
            project_path,
        )
        if auto_advance:
            expo.confirm_print_start()

        return Exposure0.dbus_path(expo.instance_id)

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def reprint(self, auto_advance: bool) -> DBusObjectPath:
        """
        Reprint last project

        :raises ReprintWithoutHistory

        :param auto_advance: Automatic print
        :return:  Print task object
        """
        if not self.printer.action_manager.exposure:
            raise ReprintWithoutHistory()

        last_exposure = self.printer.action_manager.exposure
        exposure = self.printer.action_manager.reprint_exposure(
            last_exposure,
            self.printer.hw,
            self.printer.exposure_image,
            self.printer.runtime_config,
        )
        if auto_advance:
            exposure.confirm_print_start()

        return Exposure0.dbus_path(exposure.instance_id)

    @auto_dbus
    @property
    def current_exposure(self) -> DBusObjectPath:
        """
        Get current exposure object DBus path

        :return: DBus path of the object
        """
        if not self.printer.action_manager.exposure:
            return DBusObjectPath("/")
        return Exposure0.dbus_path(self.printer.action_manager.exposure.instance_id)

    @auto_dbus
    @property
    def project_extensions(self) -> List[str]:
        """
        Set of supported project extensions

        :return: Set of extension strings
        """
        return list(self.printer.model.extensions)

    @auto_dbus
    @deprecated("Use filemanager instead")
    def list_projects_raw(self) -> List[str]:  # pylint: disable=no-self-use
        """
        List available projects

        This just lists raw project paths that can be passed to print. No further info. Mainly for testing purposes.

        :return: List of project files with path as list of strings
        """
        sources = [Path(defines.internalProjectPath), Path(defines.mediaRootPath)]
        projects = []
        for directory in sources:
            projects.extend(get_all_supported_files(self.printer.model, directory))
        return [str(project) for project in projects]

    @auto_dbus
    @property
    def printer_model(self) -> int:
        return self.printer.model.value

    @auto_dbus
    @property
    def resin_tank_capacity_ml(self) -> float:
        """
        Resin tank capacity in milliliters

        :return: Resin tank capacity as float in milliliters
        """
        return defines.resinMaxVolume

    @auto_dbus
    @property
    def admin_enabled(self) -> bool:
        """
        Whenever the user has admin access (show admin)

        :return: True if admin enabled, false otherwise
        """
        return self.printer.runtime_config.show_admin

    @auto_dbus
    @property
    @cached(validity_s=5)
    def statistics(self) -> Dict[str, Any]:
        """
        Get statistics

        :return: Dictionary mapping from statistics name to value
        """
        return wrap_dict_data(TomlConfigStats(defines.statsData, self.printer.hw).load())

    @auto_dbus
    def run_displaytest_wizard(self) -> None:
        self.printer.action_manager.start_wizard(
            DisplayTestWizard(self.printer.hw, self.printer.exposure_image, self.printer.runtime_config)
        )

    @auto_dbus
    def run_unboxing_wizard(self) -> None:
        self.printer.action_manager.start_wizard(CompleteUnboxingWizard(self.printer.hw, self.printer.runtime_config))

    @auto_dbus
    def run_kit_unboxing_wizard(self) -> None:
        self.printer.action_manager.start_wizard(KitUnboxingWizard(self.printer.hw, self.printer.runtime_config))

    @auto_dbus
    def run_self_test_wizard(self) -> None:
        self.printer.action_manager.start_wizard(
            SelfTestWizard(self.printer.hw, self.printer.exposure_image, self.printer.runtime_config)
        )

    @auto_dbus
    def run_calibration_wizard(self) -> None:
        self.printer.action_manager.start_wizard(CalibrationWizard(self.printer.hw, self.printer.runtime_config))

    @auto_dbus
    def run_tank_surface_cleaner_wizard(self) -> None:
        self.printer.action_manager.start_wizard(
            TankSurfaceCleaner(self.printer.hw, self.printer.exposure_image, self.printer.runtime_config)
        )

    @auto_dbus
    def run_factory_reset_wizard(self) -> None:
        if self.printer.runtime_config.factory_mode:
            self.printer.action_manager.start_wizard(PackingWizard(self.printer.hw, self.printer.runtime_config))
        else:
            self.printer.action_manager.start_wizard(FactoryResetWizard(self.printer.hw, self.printer.runtime_config))

    @auto_dbus
    def run_uv_calibration_wizard(self, display_replaced: bool, led_module_replaced: bool) -> None:
        self.printer.action_manager.start_wizard(
            UVCalibrationWizard(
                self.printer.hw,
                self.printer.exposure_image,
                self.printer.runtime_config,
                display_replaced=display_replaced,
                led_module_replaced=led_module_replaced,
            )
        )

    @auto_dbus
    @property
    def data_privacy(self) -> bool:
        return self.printer.data_privacy

    @auto_dbus
    @data_privacy.setter
    def data_privacy(self, enabled: bool) -> None:
        self.printer.data_privacy = enabled

    @auto_dbus
    @property
    def help_page_url(self) -> str:
        return self.printer.help_page_url

    @auto_dbus
    def cmd_try_cancel_by_path(self, path: str) -> None:
        """
        Cancel exposure if the paths are equals

        :return: None
        """
        self.printer.action_manager.try_cancel_by_path(path)

    @auto_dbus
    @property
    def unboxed(self) -> bool:
        return self.printer.unboxed

    @auto_dbus
    @property
    def mechanically_calibrated(self) -> bool:
        return self.printer.mechanically_calibrated

    @auto_dbus
    @property
    def uv_calibrated(self) -> bool:
        return self.printer.uv_calibrated

    @auto_dbus
    @property
    def self_tested(self) -> bool:
        return self.printer.self_tested

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def make_ready_to_print(self):
        return self.printer.run_make_ready_to_print()

    @auto_dbus
    def add_oneclick_inhibitor(self, name: str) -> None:
        self.printer.add_oneclick_inhibitor(name)

    @auto_dbus
    def remove_oneclick_inhibitor(self, name: str) -> None:
        self.printer.remove_oneclick_inhibitor(name)

    @auto_dbus
    @property
    @cached()
    def booster_serial(self) -> str:
        """
        Get booster board serial number

        :return: booster board serial number
        """
        # TODO: booster could be encapsulated inside UvLed
        try:
            return self.printer.hw.sl1s_booster.board_serial_no
        except AttributeError:
            return "NA"

    @auto_dbus
    @property
    @cached()
    def expo_panel_serial(self) -> str:
        """
        Get exposure display serial number

        :return: exposure display serial number
        """
        return self.printer.hw.exposure_screen.serial_number

    @auto_dbus
    @property
    @cached()
    def expo_panel_transmittance(self) -> float:
        """
        Get exposure display transmittance

        :return: exposure display transmittance
        """
        return self.printer.hw.exposure_screen.transmittance

    @auto_dbus
    def inject_exception(self, code: str):
        self.printer.inject_exception(code)

    @auto_dbus
    def fail_action(self, code: str):  # pylint: disable = no-self-use
        raise tests.get_instance_by_code(code)

    @auto_dbus
    def power_led_set_warning(self) -> None:
        return self.printer.hw.power_led.set_warning()

    @auto_dbus
    def power_led_remove_warning(self) -> None:
        return self.printer.hw.power_led.remove_warning()

    @auto_dbus
    def power_led_set_error(self) -> None:
        return self.printer.hw.power_led.set_error()

    @auto_dbus
    def power_led_remove_error(self) -> None:
        return self.printer.hw.power_led.remove_error()
