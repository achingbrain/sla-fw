# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from enum import unique, Enum
from pathlib import Path
from typing import List, Dict, Tuple, TYPE_CHECKING, Any, Optional

import distro
import pydbus
from deprecated import deprecated
from pydbus.generic import signal

from sl1fw import defines
from sl1fw.api.decorators import dbus_api, state_checked, cached, auto_dbus, DBusObjectPath, wrap_variant_dict, \
    wrap_exception, last_error
from sl1fw.api.display_test0 import DisplayTest0
from sl1fw.api.exposure0 import Exposure0
from sl1fw.functions import files
from sl1fw.functions.files import get_save_path
from sl1fw.functions.system import shut_down
from sl1fw.errors.exceptions import ReprintWithoutHistory
from sl1fw.states.display import DisplayState
from sl1fw.states.printer import PrinterState

if TYPE_CHECKING:
    from sl1fw.libPrinter import Printer


@unique
class Printer0State(Enum):
    """
    General printer state enumeration
    """
    INITIALIZING = 0
    IDLE = 1
    UNBOXING = 2
    WIZARD = 3
    CALIBRATION = 4
    DISPLAY_TEST = 5
    PRINTING = 6
    UPDATE = 7
    ADMIN = 8
    EXCEPTION = 9


@dbus_api
class Printer0:
    """
    This is a 0 revision of the printer public API. This contains all the stuff that the display/pages interface can do,
    but some parts are still not implemented. As the structure was preserved from pages for easy porting and new methods
    were added as needed the API is not looking very well.

    Keep implementation out of this file. Methods here should only adapt interfaces and reformat data.
    """

    __INTERFACE__ = "cz.prusa3d.sl1.printer0"

    PRINTER_STATE_TO_STATE = {
        PrinterState.INIT: Printer0State.INITIALIZING,
        PrinterState.EXCEPTION: Printer0State.EXCEPTION,
        PrinterState.UPDATING: Printer0State.UPDATE,
        PrinterState.PRINTING: Printer0State.PRINTING,
        PrinterState.UNBOXING: Printer0State.UNBOXING,
    }

    DISPLAY_STATE_TO_STATE = {
        DisplayState.CALIBRATION: Printer0State.CALIBRATION,
        DisplayState.WIZARD: Printer0State.WIZARD,
        DisplayState.FACTORY_RESET: Printer0State.INITIALIZING,
        DisplayState.ADMIN: Printer0State.ADMIN,
        DisplayState.DISPLAY_TEST: Printer0State.DISPLAY_TEST,
    }

    PropertiesChanged = signal()

    @auto_dbus
    @property
    @deprecated(reason="Do not rely on current page, use state", action="once")
    def current_page(self) -> str:
        """
        Get current page name

        :return: Current page name
        """
        return self.printer.get_actual_page().Name

    def __init__(self, printer: Printer):
        self._last_exception: Optional[Exception] = None
        self.printer = printer
        self._display_test_registration = None
        self._unpacking = None
        self._wizard = None
        self._calibration = None
        self._prints = []
        self.printer.display.state_changed.connect(lambda x: self._state_update())
        self.printer.state_changed.connect(lambda x: self._state_update())

    def _state_update(self):
        self.PropertiesChanged(self.__INTERFACE__, {"state": self.state}, [])

    @auto_dbus
    @property
    def state(self) -> int:
        """
        Get global printer state

        :return: Global printer state
        """
        if self.printer.state in self.PRINTER_STATE_TO_STATE:
            return self.PRINTER_STATE_TO_STATE[self.printer.state].value

        if self.printer.display.state in self.DISPLAY_STATE_TO_STATE:
            return self.DISPLAY_STATE_TO_STATE[self.printer.display.state].value

        if self._display_test_registration:
            return Printer0State.DISPLAY_TEST.value

        return Printer0State.IDLE.value

    @auto_dbus
    @property
    @wrap_variant_dict
    def last_exception(self) -> Dict[str, Any]:
        return wrap_exception(self._last_exception)

    @auto_dbus
    @property
    @wrap_variant_dict
    def printer_exception(self) -> Dict[str, Any]:
        return wrap_exception(self.printer.exception)

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
    def save_logs_to_usb(self) -> None:
        """
        Save logs to first usb device
        :return: None
        """
        files.save_logs_to_usb(self.printer.hw.cpuSerialNo)

    @auto_dbus
    @state_checked([Printer0State.IDLE, Printer0State.EXCEPTION])
    @last_error
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
    @state_checked(Printer0State.IDLE)
    @last_error
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

    @state_checked(Printer0State.IDLE)
    @auto_dbus
    @last_error
    def disable_motors(self) -> None:
        """
        Disable motors

        This ends the annoying sound.

        :return: None
        """
        self.printer.hw.motorsRelease()

    @state_checked([Printer0State.IDLE, Printer0State.CALIBRATION])
    @auto_dbus
    @last_error
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

    @state_checked([Printer0State.IDLE, Printer0State.CALIBRATION])
    @auto_dbus
    @last_error
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
    @state_checked(Printer0State.IDLE)
    @last_error
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
    @state_checked(Printer0State.IDLE)
    @last_error
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
        result = {}
        rpms = self.printer.hw.getFansRpm()
        errors = self.printer.hw.getFansError()
        for i in range(len(self.printer.hw.getFansRpm())):
            result["fan%d" % i] = {"rpm": rpms[i], "error": errors[i]}
        return result

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    def temps(self) -> Dict[str, float]:
        """
        Get temperatures

        :return: Dictionary mapping from temp sensor name to temperature in celsius
        """
        return {"temp%d_celsius" % i: v for i, v in enumerate(self.printer.hw.getMcTemperatures())}

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
        return {"led%d_voltage_volt" % i: v for i, v in enumerate(self.printer.hw.getVoltages())}

    @auto_dbus
    @property
    @last_error
    @cached(validity_s=5)
    @deprecated(reason="Use NetworkManager", action="once")
    def devlist(self) -> Dict[str, str]:
        """
        Get network devices

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
        return {"uv_stat%d" % i: v for i, v in enumerate(self.printer.hw.getUvStatistics())}
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
    @cached()
    def controller_revision_bin(self) -> Tuple[int, int]:
        return self.printer.hw.mcBoardRevisionBin

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
    @property
    @last_error
    @cached(validity_s=5)
    @deprecated(reason="Use config api")
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
    @deprecated(reason="Use config api")
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
        # If test is already pending just return test object
        if self._display_test_registration:
            return DBusObjectPath(DisplayTest0.DBUS_PATH)

        display_test = DisplayTest0(self.printer.display, self._clear_display_test)
        self._display_test_registration = pydbus.SystemBus().publish(DisplayTest0.__INTERFACE__,
                                                                     (DisplayTest0.DBUS_PATH, display_test))
        self._state_update()
        return DBusObjectPath(DisplayTest0.DBUS_PATH)

    def _clear_display_test(self):
        self._display_test_registration.unpublish()
        self._display_test_registration = None
        self._state_update()

    @auto_dbus
    @last_error
    def wizard(self):
        """
        Initiate wizard test object

        NOT IMPLEMENTED

        :return: Wizard object path
        """
        raise NotImplementedError

    @auto_dbus
    @last_error
    def update_firmware(self):
        """
        Initiate firmware update

        NOT IMPLEMENTED
        """
        # TODO: Do we need to have this here? If we can do update while printing we do not need to care.
        raise NotImplementedError

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
    def enter_admin(self) -> None:
        """
        Initiate admin mode

        NOT IMPLEMENTED
        """
        raise NotImplementedError

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
        if not self.printer.runtime_config.last_project_data:
            raise ReprintWithoutHistory()

        old_data = self.printer.runtime_config.last_project_data
        expo = self.printer.action_manager.new_exposure(
            self.printer.hwConfig,
            self.printer.hw,
            self.printer.screen,
            self.printer.runtime_config,
            self.printer.action_manager.exposure.project.origin,
            exp_time_ms=old_data["exp_time_ms"],
            exp_time_first_ms=old_data["exp_time_first_ms"],
            exp_time_calibrate_ms=old_data["exp_time_calibrate_ms"],
        )
        if auto_advance:
            expo.confirm_print_start()

        return Exposure0.dbus_path(expo.instance_id)

    @auto_dbus
    @last_error
    def get_current_exposure(self) -> DBusObjectPath:
        """
        Get current exposure object DBus path

        :return: DBus path of the object
        """
        if self.printer.action_manager.exposure:
            return Exposure0.dbus_path(self.printer.action_manager.exposure.instance_id)
        else:
            return DBusObjectPath("/")

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
        return list(defines.projectExtensions)

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
        for directory in sources:
            for extension in defines.projectExtensions:
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
