# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Dict, TYPE_CHECKING, Any, Optional

import distro
import pydbus
from deprecation import deprecated
from pydbus.generic import signal

from sl1fw import defines
from sl1fw.api.decorators import (
    dbus_api,
    state_checked,
    cached,
    auto_dbus,
    DBusObjectPath,
    wrap_exception,
    last_error,
    wrap_dict_data,
)
from sl1fw.api.display_test0 import DisplayTest0
from sl1fw.api.examples0 import Examples0
from sl1fw.api.exposure0 import Exposure0
from sl1fw.configs.stats import TomlConfigStats
from sl1fw.configs.toml import TomlConfig
from sl1fw.errors.errors import NotUVCalibrated, NotMechanicallyCalibrated
from sl1fw.errors.exceptions import ReprintWithoutHistory, ConfigException
from sl1fw.functions.files import get_save_path
from sl1fw.functions.system import shut_down
from sl1fw.functions.wizards import (
    displaytest_wizard,
    unboxing_wizard,
    kit_unboxing_wizard,
    the_wizard,
    calibration_wizard,
)
from sl1fw.project.functions import check_ready_to_print
from sl1fw.state_actions.examples import Examples
from sl1fw.states.examples import ExamplesState
from sl1fw.states.printer import Printer0State

if TYPE_CHECKING:
    from sl1fw.libPrinter import Printer


@dbus_api
class Printer0:
    """
    This is a 0 revision of the printer public API. This contains all the stuff that the display/pages interface can do,
    but some parts are still not implemented. As the structure was preserved from pages for easy porting and new methods
    were added as needed the API is not looking very well.

    Keep implementation out of this file. Methods here should only adapt interfaces and reformat data.
    """

    __INTERFACE__ = "cz.prusa3d.sl1.printer0"

    PropertiesChanged = signal()

    @auto_dbus
    @property
    @deprecated("Do not rely on current page, use state")
    def current_page(self) -> str:
        """
        Get current page name

        Does not provide changed signal as this property is deprecated.

        :return: Current page name
        """
        return self.printer.get_actual_page().Name

    def __init__(self, printer: Printer):
        self._last_exception_data: Optional[Exception] = None
        self.printer = printer
        self._examples: Optional[Examples] = None
        self._examples0: Optional[Examples0] = None
        self._examples_registration = None
        self._unpacking = None
        self._wizard = None
        self._calibration = None
        self._prints = []

        self.printer.display.state_changed.connect(self._on_state_changed)
        self.printer.state_changed.connect(self._on_state_changed)
        self.printer.exception_changed.connect(self._on_exception_changed)
        self.printer.hw.fans_changed.connect(self._on_fans_changed)
        self.printer.hw.mc_temps_changed.connect(self._on_temps_changed)
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

    def _on_state_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"state": self.state}, [])

    def _on_exception_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"printer_exception": self.printer_exception}, [])

    def _on_fans_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"fans": self.fans}, [])

    def _on_temps_changed(self, value):
        self.PropertiesChanged(self.__INTERFACE__, {"temps": self._format_temps(value)}, [])

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

    @auto_dbus
    @property
    @last_error
    def state(self) -> int:
        """
        Get global printer state

        :return: Global printer state
        """
        state = self.printer.state.to_state0()
        if state:
            return state.value

        state = self.printer.display.state.to_state0()
        if state:
            return state.value

        return Printer0State.IDLE.value

    @auto_dbus
    @property
    def last_exception(self) -> Dict[str, Any]:
        return wrap_dict_data(wrap_exception(self._last_exception))

    @property
    def _last_exception(self) -> Exception:
        return self._last_exception_data

    @_last_exception.setter
    def _last_exception(self, value: Exception):
        self._last_exception_data = value
        self.PropertiesChanged(self.__INTERFACE__, {"last_exception": self.last_exception}, [])

    @auto_dbus
    @property
    def printer_exception(self) -> Dict[str, Any]:
        return wrap_dict_data(wrap_exception(self.printer.exception))

    @auto_dbus
    @property
    def http_digest(self) -> bool:
        return TomlConfig(defines.remoteConfig).load().get("http_digest", True)

    @auto_dbus
    @http_digest.setter
    @last_error
    def http_digest(self, enabled: bool) -> None:
        remote_config = TomlConfig(defines.remoteConfig)
        new_data = remote_config.load()
        new_data["http_digest"] = enabled
        if not remote_config.save(data=new_data):
            raise ConfigException("Octoprint API key change failed")
        if enabled:
            subprocess.check_call([defines.htDigestCommand, "enable"])
        else:
            subprocess.check_call([defines.htDigestCommand, "disable"])
        self.PropertiesChanged(self.__INTERFACE__, {"http_digest": enabled}, [])

    @auto_dbus
    @last_error
    def beep(self, frequency_hz: int, length_ms: int) -> None:
        """
        Motion controller beeper beep

        :param frequency_hz: Beep frequency in Hz
        :param length_ms: Beep duration in ms
        :return: None
        """
        self.printer.hw.beep(frequency_hz, length_ms / 1000)

    @auto_dbus
    @last_error
    @state_checked([Printer0State.IDLE, Printer0State.EXCEPTION])
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
            self.printer.display.forcedPage("start")

    @auto_dbus
    @last_error
    @state_checked(Printer0State.IDLE)
    def tower_home(self) -> None:
        """
        Home tower axis
        """
        self.printer.hw.tower_home()

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    @last_error
    def tilt_home(self) -> None:
        """
        Home tilt axis

        :return: None
        """
        self.printer.hw.tilt_home()

    @auto_dbus
    @last_error
    @state_checked(Printer0State.IDLE)
    def disable_motors(self) -> None:
        """
        Disable motors

        This ends the annoying sound.

        :return: None
        """
        self.printer.hw.motorsRelease()

    @auto_dbus
    @last_error
    @state_checked([Printer0State.IDLE, Printer0State.CALIBRATION])
    def tower_move(self, speed: int) -> bool:
        """
        Start / stop tower movement

        TODO: This should be checked by heartbeat or the command should have limited ttl
        TODO: Allowed for calibration as calibration does not have dedicated control object, yet

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
    @last_error
    @state_checked([Printer0State.IDLE, Printer0State.CALIBRATION])
    def tilt_move(self, speed: int) -> bool:
        """
        Start / stop tilt movement

        TODO: This should be checked by heartbeat or the command should have limited ttl
        TODO: Allowed for calibration as calibration does not have dedicated control object, yet

        :param: Movement speed

           :-2: Fast down
           :-1: Slow down
           :0: Stop
           :1: Slow up
           :2: Fast up
        :return: True on success, False otherwise
        """
        return self.printer.hw.tilt_move(speed)

    @property
    @last_error
    def tower_position_nm(self) -> int:
        """
        Read or set tower position in nm
        """
        return self.printer.hw.tower_position_nm

    @auto_dbus
    @tower_position_nm.setter
    @last_error
    @state_checked(Printer0State.IDLE)
    def tower_position_nm(self, position_nm: int) -> None:
        self.printer.hw.tower_position_nm = position_nm

    @property
    @last_error
    def tilt_position(self) -> int:
        """
        Read or set tilt position in micro-steps
        """
        return self.printer.hw.tilt_position

    @auto_dbus
    @tilt_position.setter
    @last_error
    @state_checked(Printer0State.IDLE)
    def tilt_position(self, micro_steps: int):
        self.printer.hw.tilt_position = micro_steps

    @auto_dbus
    @last_error
    def get_projects(self) -> List[str]:
        """
        Get available project files

        NOT IMPLEMENTED

        :return: Array of project file paths
        """
        raise NotImplementedError

    @auto_dbus
    @last_error
    def get_firmwares(self) -> List[str]:
        """
        Get available firmware files

        NOT IMPLEMENTED

        :return: Array of firmware sources (file, network)
        """
        raise NotImplementedError

    @auto_dbus
    @property
    @last_error
    @cached()
    def serial_number(self) -> str:
        """
        Get A64 serial

        :return: A64 serial number
        """
        return self.printer.hw.cpuSerialNo

    @auto_dbus
    @property
    @last_error
    @cached()
    def system_name(self) -> str:
        """
        Get system name

        :return: System distribution name
        """
        return distro.name()

    @auto_dbus
    @property
    @last_error
    @cached()
    def system_version(self) -> str:
        """
        Get system version

        :return: System distribution version
        """
        return distro.version()

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def fans(self) -> Dict[str, Dict[str, int]]:
        """
        Get fan RPMs and errors

        :return: Dictionary mapping from fan names to RPMs and errors
        """
        return self._format_fans(self.printer.hw.getFansRpm(), self.printer.hw.getFansError())

    @staticmethod
    def _format_fans(rpms, errors):
        return {f"fan{i}": {"rpm": rpm, "error": error} for i, (rpm, error) in enumerate(zip(rpms, errors.values()))}

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def temps(self) -> Dict[str, float]:
        """
        Get temperatures

        :return: Dictionary mapping from temp sensor name to temperature in celsius
        """
        return self._format_temps(self.printer.hw.getMcTemperatures(False))

    @staticmethod
    def _format_temps(temps):
        return {"temp%d_celsius" % i: v for i, v in enumerate(temps)}

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def cpu_temp(self) -> float:
        """
        Get A64 temperature

        :return: A64 CPU temperature
        """
        return self.printer.hw.getCpuTemperature()

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def leds(self) -> Dict[str, float]:
        """
        Get UV LED voltages

        :return: Dictionary mapping from LED channel name to voltage value
        """
        return self._format_leds(self.printer.hw.getVoltages())

    @staticmethod
    def _format_leds(leds):
        return {"led%d_voltage_volt" % i: v for i, v in enumerate(leds)}

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    @deprecated("Use NetworkManager")
    def devlist(self) -> Dict[str, str]:
        """
        Get network devices

        No changed events are send for this item

        :return: Dictionary mapping from interface names to IP address strings
        """
        return self.printer.inet.devices

    @auto_dbus
    @property
    @last_error
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
    @last_error
    @cached(validity_s=5)
    def controller_sw_version(self) -> str:
        """
        Get motion controller version

        :return: Version string
        """
        return self.printer.hw.mcFwVersion

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def controller_serial(self) -> str:
        """
        Get motion controller serial

        :return: Serial number as string
        """
        return self.printer.hw.mcSerialNo

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def controller_revision(self) -> str:
        return self.printer.hw.mcBoardRevision

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def api_key(self) -> str:
        """
        Get current API key

        :return: Current api key string
        """
        return self.printer.get_actual_page().octoprintAuth

    @auto_dbus
    @api_key.setter
    @last_error
    def api_key(self, apikey: str) -> None:
        if apikey != self.printer.get_actual_page().octoprintAuth:
            subprocess.check_call(["/bin/api-keygen.sh", apikey])
            self.PropertiesChanged(self.__INTERFACE__, {"api_key": apikey}, [])

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    @deprecated("Use config api")
    def tilt_fast_time_sec(self) -> float:
        """
        Get fast tilt time
        :return: Fast tilt time in seconds
        """
        return self.printer.hwConfig.tiltFastTime

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    @deprecated("Use config api")
    def tilt_slow_time_sec(self) -> float:
        """
        Get slow tilt time

        :return: Fast slow time in seconds
        """
        return self.printer.hwConfig.tiltSlowTime

    @auto_dbus
    @last_error
    def enable_resin_sensor(self, value: bool) -> None:
        """
        Set resin sensor enabled flag

        :param value: Enabled / disabled as boolean
        :return: None
        """
        self.printer.hw.resinSensor(value)

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=0.5)
    def resin_sensor_state(self) -> bool:
        """
        Get resin sensor state

        :return: True if enabled, False otherwise
        """
        return self.printer.hw.getResinSensorState()

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=0.5)
    def cover_state(self) -> bool:
        """
        Get cover state

        :return: True of closed, False otherwise
        """
        return self.printer.hw.isCoverClosed()

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=0.5)
    def power_switch_state(self) -> bool:
        """
        Get power switch state

        :return: True if pressed, False otherwise
        """
        return self.printer.hw.getPowerswitchState()

    @auto_dbus
    @property
    @last_error
    def factory_mode(self) -> bool:
        """
        Check for factory mode

        :return: True if in factory mode, False otherwise
        """
        return self.printer.runtime_config.factory_mode

    @auto_dbus
    @last_error
    @state_checked([Printer0State.IDLE, Printer0State.DISPLAY_TEST])
    def display_test(self) -> DBusObjectPath:
        """
        Initiate display test object

        :return: Display test object path
        """
        self.printer.action_manager.start_display_test(
            self.printer.hw, self.printer.hwConfig, self.printer.screen, self.printer.runtime_config
        )
        return DBusObjectPath(DisplayTest0.DBUS_PATH)

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
        self._examples = Examples(self.printer.inet)
        self._examples0 = Examples0(self._examples)
        self._examples_registration = pydbus.SystemBus().publish(
            Examples0.__INTERFACE__, (Examples0.DBUS_PATH, self._examples0)
        )
        self._examples.start()
        return DBusObjectPath(Examples0.DBUS_PATH)

    @auto_dbus
    @last_error
    @state_checked(Printer0State.IDLE)
    def wizard(self) -> DBusObjectPath:
        """
        Initiate wizard test object

        Implemented by page transition. No wizard object available, yet.

        :return: Wizard object path - currently only "/" string
        """
        self.printer.display.forcePage("wizardinit")
        return DBusObjectPath("/")

    @auto_dbus
    @last_error
    @state_checked(Printer0State.IDLE)
    def update_firmware(self, fw_file: str):
        """
        Initiate firmware update

        Pass-through to Rauc install. Only works when printer in idle state.
        """
        # pylint: disable=no-self-use
        pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"].Install(fw_file)

    @auto_dbus
    @last_error
    def factory_reset(self) -> None:
        """
        Do factory reset

        NOT IMPLEMENTED
        """
        raise NotImplementedError

    @auto_dbus
    @last_error
    @state_checked([Printer0State.IDLE])
    def enter_home(self) -> None:
        """
        Enter home page
        """
        self.printer.display.forcePage("home")

    @auto_dbus
    @last_error
    @state_checked(Printer0State.IDLE)
    def check_ready(self) -> None:
        """
        Check printer is ready to print

        This raises subset of exceptions the print raises, but does not do anything on success
        :return: None
        """
        check_ready_to_print(self.printer.hwConfig, self.printer.screen.printer_model.calibration(self.printer.hw.is500khz))

    @auto_dbus
    @last_error
    @state_checked(Printer0State.IDLE)
    def print(self, project_path: str, auto_advance: bool) -> DBusObjectPath:
        """
        Start printing project

        :param project_path: Path to project in printer filesystem
        :param auto_advance: Automatic print

        :returns: Print task object
        """
        expo = self.printer.action_manager.new_exposure(
            self.printer.hwConfig, self.printer.hw, self.printer.screen, self.printer.runtime_config, project_path
        )
        if auto_advance:
            expo.confirm_print_start()

        return Exposure0.dbus_path(expo.instance_id)

    @auto_dbus
    @last_error
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
            last_exposure, self.printer.hwConfig, self.printer.hw, self.printer.screen, self.printer.runtime_config
        )
        if auto_advance:
            exposure.confirm_print_start()

        return Exposure0.dbus_path(exposure.instance_id)

    @auto_dbus
    @property
    @last_error
    def current_exposure(self) -> DBusObjectPath:
        """
        Get current exposure object DBus path

        :return: DBus path of the object
        """
        if not self.printer.action_manager.exposure:
            return DBusObjectPath("/")
        return Exposure0.dbus_path(self.printer.action_manager.exposure.instance_id)

    @auto_dbus
    @last_error
    @deprecated("Use current_exposure property")
    def get_current_exposure(self) -> DBusObjectPath:
        return self.current_exposure

    @auto_dbus
    @property
    @last_error
    def project_config_file_name(self) -> str:
        """
        Name of the config file embedded in project files

        :return: Name as string
        """
        return defines.configFile

    @auto_dbus
    @property
    @last_error
    def project_extensions(self) -> List[str]:
        """
        Set of supported project extensions

        :return: Set of extension strings
        """
        return list(self.printer.screen.printer_model.extensions)

    @auto_dbus
    @property
    @last_error
    def persistent_storage_path(self) -> str:
        """
        Filesystem path of the persistent internal storage

        :return: Path as string
        """
        return defines.persistentStorage

    @auto_dbus
    @property
    @last_error
    def internal_project_path(self) -> str:
        """
        Filesystem path to the projects root on the internal storage
        :return: Path as string
        """
        return defines.internalProjectPath

    @auto_dbus
    @property
    @last_error
    def media_root_path(self) -> str:
        """
        Filesystem path to the root of the mounted media

        New media are mounted into directories residing inside this path.

        :return: Path as string
        """
        return defines.mediaRootPath

    @auto_dbus
    @last_error
    def list_projects_raw(self) -> List[str]:  # pylint: disable=no-self-use
        """
        List available projects

        This just lists raw project paths that can be passed to print. No further info. Mainly for testing purposes.

        :return: List of project files with path as list of strings
        """
        sources = [Path(defines.internalProjectPath), Path(defines.mediaRootPath)]
        projects = []
        extensions = self.printer.screen.printer_model.extensions
        for directory in sources:
            for extension in extensions:
                projects.extend(directory.rglob(f"*{extension}"))
        return [str(project) for project in projects]

    @auto_dbus
    @property
    @last_error
    def usb_path(self) -> str:
        """
        Read path to currently inserted USB drive

        :return: Path as string or empty string in case of no USB present
        """
        path = get_save_path()
        if path:
            return str(path)
        return ""

    @auto_dbus
    @property
    @last_error
    def resin_tank_capacity_ml(self) -> float:
        """
        Resin tank capacity in milliliters

        :return: Resin tank capacity as float in milliliters
        """
        return defines.resinMaxVolume

    @auto_dbus
    @property
    @last_error
    def admin_enabled(self) -> bool:
        """
        Whenever the user has admin access (show admin)

        :return: True if admin enabled, false otherwise
        """
        return self.printer.runtime_config.show_admin

    @auto_dbus
    def add_usb(self) -> None:
        try:
            self.PropertiesChanged(self.__INTERFACE__, {"usb_path": self.usb_path}, [])
            path = get_save_path()
            if path:
                projects = path.glob("**/*.sl1")
                newest_proj = sorted(projects, key=lambda proj: proj.stat().st_mtime).pop()
                last_exposure = self.printer.action_manager.exposure
                if last_exposure:
                    last_exposure.try_cancel()
                self.print(str(newest_proj), False)
        except NotUVCalibrated:
            self.printer.display.forcePage("uvcalibrationstart")
        except NotMechanicallyCalibrated:
            self.printer.display.forcePage("calibrationstart")
        except Exception:
            pass

    @auto_dbus
    def remove_usb(self) -> None:
        try:
            expo = self.printer.action_manager.exposure
            if expo and Path(defines.mediaRootPath) in Path(expo.project.path).parents:
                expo.try_cancel()
        except Exception:
            pass

    @auto_dbus
    @last_error
    def try_open_project(self, project_path: str) -> DBusObjectPath:
        last_exposure = self.printer.action_manager.exposure
        if last_exposure:
            last_exposure.try_cancel()
        try:
            return self.print(project_path, False)
        except NotUVCalibrated:
            self.printer.display.forcePage("uvcalibrationstart")
            raise
        except NotMechanicallyCalibrated:
            self.printer.display.forcePage("calibrationstart")
            raise

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def statistics(self) -> Dict[str, Any]:
        """
        Get statistics

        :return: Dictionary mapping from statistics name to value
        """
        return wrap_dict_data(TomlConfigStats(defines.statsData, self.printer.hw).load())

    @last_error
    def run_displaytest_wizard(self) -> None:
        displaytest_wizard(
            self.printer.action_manager,
            self.printer.hw,
            self.printer.hwConfig,
            self.printer.screen,
            self.printer.runtime_config,
        )

    @auto_dbus
    @last_error
    def run_unboxing_wizard(self) -> None:
        unboxing_wizard(self.printer.action_manager, self.printer.hw, self.printer.hwConfig)

    @auto_dbus
    @last_error
    def run_kit_unboxing_wizard(self) -> None:
        kit_unboxing_wizard(self.printer.action_manager, self.printer.hw, self.printer.hwConfig)

    @auto_dbus
    @last_error
    def run_the_wizard(self) -> None:
        the_wizard(
            self.printer.action_manager,
            self.printer.hw,
            self.printer.hwConfig,
            self.printer.screen,
            self.printer.runtime_config,
        )

    @auto_dbus
    @last_error
    def run_calibration_wizard(self) -> None:
        calibration_wizard(self.printer.action_manager, self.printer.hw, self.printer.hwConfig)

    @auto_dbus
    @property
    def data_privacy(self) -> bool:
        return TomlConfig(defines.remoteConfig).load().get("data_privacy", True)

    @auto_dbus
    @data_privacy.setter
    @last_error
    def data_privacy(self, enabled: bool) -> None:
        remote_config = TomlConfig(defines.remoteConfig)
        new_data = remote_config.load()
        if enabled != new_data.get("data_privacy", True):
            new_data["data_privacy"] = enabled
            if not remote_config.save(data=new_data):
                raise ConfigException("Data privacy change failed")
            self.PropertiesChanged(self.__INTERFACE__, {"data_privacy": enabled, "help_page_url": self.help_page_url}, [])

    @auto_dbus
    @property
    @last_error
    def help_page_url(self) -> str:
        url = ""
        if TomlConfig(defines.remoteConfig).load().get("data_privacy", True):
            printer_identifier = self.printer.id
            fw_version = re.sub(r"(\d*)\.(\d*)\.(\d*)-.*", r"\g<1>\g<2>\g<3>", distro.version())
            url = url + f"/{printer_identifier}/{fw_version}"

        return url
