# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Tuple, TYPE_CHECKING

import distro
import pydbus
from pydbus.generic import signal
from deprecated import deprecated

from sl1fw import defines
from sl1fw.api.decorators import dbus_api, state_checked, cached, auto_dbus, DBusObjectPath
from sl1fw.functions import files
from sl1fw.api.display_test0 import DisplayTest0
from sl1fw.api.exposure0 import Exposure0
from sl1fw.api.states import Printer0State
from sl1fw.functions.files import get_save_path
from sl1fw.display_state import DisplayState
from sl1fw.printer_state import PrinterState

if TYPE_CHECKING:
    from sl1fw.libPrinter import Printer


@dbus_api
class Printer0:
    """
    This is prototype of the public printer API, implementation is naive, incomplete and possibly broken.
    Keep implementation out of this file. Methods here should only adapt interfaces and reformat data.
    """
    __INTERFACE__ = "cz.prusa3d.sl1.printer0"

    PRINTER_STATE_TO_STATE = {
        PrinterState.INIT: Printer0State.INITIALIZING,
        PrinterState.EXCEPTION: Printer0State.EXCEPTION,
        PrinterState.UPDATING: Printer0State.UPDATE,
        PrinterState.PRINTING: Printer0State.PRINTING,
    }

    DISPLAY_STATE_TO_STATE = {
        DisplayState.CALIBRATION: Printer0State.CALIBRATION,
        DisplayState.WIZARD: Printer0State.WIZARD,
        DisplayState.UNBOXING: Printer0State.UNBOXING,
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
    def beep(self, frequency_hz: int, length_ms:int) -> None:
        """
        Motion controller beeper beep

        :param frequency_hz: Beep frequency in Hz
        :param length_ms: Beep duration in ms
        :return: None
        """
        self.printer.hw.beep(frequency_hz, length_ms / 1000)

    @auto_dbus
    def save_logs_to_usb(self) -> None:
        """
        Save logs to first usb device
        :return: None
        """
        files.save_logs_to_usb(self.printer.hw.cpuSerialNo)

    @auto_dbus
    @state_checked([Printer0State.IDLE, Printer0State.EXCEPTION])
    def poweroff(self, do_shutdown: bool, reboot: bool) -> None:
        """
        Shut down the printer

        :param do_shutdown: True for real action, False just restarts the printer logic
        :param reboot: True does reboot, False means real shutdown
        :return: None
        """
        self.printer.display.shutDown(do_shutdown, reboot=reboot)

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
        self.printer.hw.tilt_home()

    @state_checked(Printer0State.IDLE)
    @auto_dbus
    def disable_motors(self) -> None:
        """
        Disable motors

        This ends the annoying sound.

        :return: None
        """
        self.printer.hw.motorsRelease()

    @state_checked(Printer0State.IDLE)
    @auto_dbus
    def tower_move(self, speed: int) -> bool:
        """
        Start / stop tower movement

        TODO: This should be checked by heartbeat or the command should have limited ttl

        :param: Movement speed

            :-2: Fast down
            :-1: Slow down
            :0: Stop
            :1: Slow up
            :2: Fast up
        :return: True on success, False otherwise
        """
        return self.printer.hw.tower_move(speed)

    @state_checked(Printer0State.IDLE)
    @auto_dbus
    def tilt_move(self, speed: int) -> bool:
        """
        Start / stop tilt movement

        TODO: This should be checked by heartbeat or the command should have limited ttl

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
        return self.printer.hw.tilt_position

    @auto_dbus
    @tilt_position.setter
    @state_checked(Printer0State.IDLE)
    def tilt_position(self, micro_steps: int):
        self.printer.hw.tilt_position = micro_steps

    @auto_dbus
    def get_projects(self) -> List[str]:
        """
        Get available project files

        NOT IMPLEMENTED

        :return: Array of project file paths
        """
        raise NotImplementedError

    @auto_dbus
    def get_firmwares(self) -> List[str]:
        """
        Get available firmware files

        NOT IMPLEMENTED

        :return: Array of firmware sources (file, network)
        """
        raise NotImplementedError

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
    @cached(validity_s=5)
    def fans(self) -> Dict[str, Dict[str, int]]:
        """
        Get fan RPMs and errors

        :return: Dictionary mapping from fan names to RPMs and errors
        """
        result ={}
        rpms = self.printer.hw.getFansRpm()
        errors = self.printer.hw.getFansError()
        for i in range(len(self.printer.hw.getFansRpm())):
            result['fan%d' % i] = {'rpm': rpms[i], 'error': errors[i]}
        return result

    @auto_dbus
    @property
    @cached(validity_s=5)
    def temps(self) -> Dict[str, float]:
        """
        Get temperatures

        :return: Dictionary mapping from temp sensor name to temperature in celsius
        """
        return {'temp%d_celsius' % i: v for i, v in enumerate(self.printer.hw.getMcTemperatures())}

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
        return {'led%d_voltage_volt' % i: v for i, v in enumerate(self.printer.hw.getVoltages())}

    @auto_dbus
    @property
    @cached(validity_s=5)
    @deprecated(reason = "Use NetworkManager", action="once")
    def devlist(self) -> Dict[str, str]:
        """
        Get network devices

        :return: Dictionary mapping from interface names to IP address strings
        """
        return self.printer.inet.devices

    @auto_dbus
    @property
    @cached(validity_s=5)
    def uv_statistics(self) -> Dict[str, int]:
        """
        Get UV statistics

        :return: Dictionary mapping from statistics name to integer value
        """
        return {'uv_stat%d' % i: v for i, v in enumerate(self.printer.hw.getUvStatistics())}
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
    @cached()
    def controller_revision_bin(self) -> Tuple[int, int]:
        return self.printer.hw.mcBoardRevisionBin

    @auto_dbus
    @property
    @cached(validity_s=5)
    def api_key(self) -> str:
        """
        Get current API key

        :return: Current api key string
        """
        return self.printer.get_actual_page().octoprintAuth

    @auto_dbus
    @property
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
    @cached(validity_s=5)
    @deprecated(reason="Use config api")
    def tilt_slow_time_sec(self) -> float:
        """
        Get slow tilt time

        :return: Fast slow time in seconds
        """
        return self.printer.hwConfig.tiltSlowTime

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
    @state_checked([Printer0State.IDLE, Printer0State.DISPLAY_TEST])
    def display_test(self) -> DBusObjectPath:
        """
        Initiate display test object

        :return: Display test object path
        """
        path = "/cz/prusa3d/sl1/displaytest0"

        # If test is already pending just return test object
        if self._display_test_registration:
            return DBusObjectPath(path)

        display_test = DisplayTest0(self.printer.display, self._clear_display_test)
        self._display_test_registration = pydbus.SystemBus().publish(DisplayTest0.__INTERFACE__, (path, display_test))
        self._state_update()
        return DBusObjectPath(path)

    def _clear_display_test(self):
        self._display_test_registration.unpublish()
        self._display_test_registration = None
        self._state_update()

    @auto_dbus
    def wizard(self):
        """
        Initiate wizard test object

        NOT IMPLEMENTED

        :return: Wizard object path
        """
        raise NotImplementedError

    @auto_dbus
    def update_firmware(self):
        """
        Initiate firmware update

        NOT IMPLEMENTED
        """
        # TODO: Do we need to have this here? If we can do update while printing we do not need to care.
        raise NotImplementedError

    @auto_dbus
    def factory_reset(self) -> None:
        """
        Do factory reset

        NOT IMPLEMENTED
        """
        raise NotImplementedError

    @auto_dbus
    def enter_admin(self) -> None:
        """
        Initiate admin mode

        NOT IMPLEMENTED
        """
        raise NotImplementedError

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def print(self, project_path: str, auto_advance: bool) -> DBusObjectPath:
        """
        Start printing project

        :param project_path: Path to project in printer filesystem
        :param auto_advance: Automatic print, no further questions - NOT SUPPORTED

        :returns: Print task object
        """
        if auto_advance:
            raise NotImplementedError

        expo = self.printer.exposure_manager.new_exposure(self.printer.hwConfig, self.printer.hw, self.printer.screen,
                                                          self.printer.runtime_config)
        expo.setProject(project_path)
        return Exposure0.dbus_path(expo.instance_id)

    @auto_dbus
    def get_current_exposure(self) -> DBusObjectPath:
        """
        Get current exposure object DBus path

        :return: DBus path of the object
        """
        if self.printer.exposure_manager.exposure:
            return Exposure0.dbus_path(self.printer.exposure_manager.exposure.instance_id)
        else:
            return DBusObjectPath("/")

    @auto_dbus
    @property
    def project_config_file_name(self) -> str:
        """
        Name of the config file embedded in project files

        :return: Name as string
        """
        return defines.configFile

    @auto_dbus
    @property
    def project_extensions(self) -> List[str]:
        """
        Set of supported project extensions

        :return: Set of extension strings
        """
        return list(defines.projectExtensions)

    @auto_dbus
    @property
    def persistent_storage_path(self) -> str:
        """
        Filesystem path of the persistent internal storage

        :return: Path as string
        """
        return defines.persistentStorage

    @auto_dbus
    @property
    def internal_project_path(self) -> str:
        """
        Filesystem path to the projects root on the internal storage
        :return: Path as string
        """
        return defines.internalProjectPath

    @auto_dbus
    @property
    def media_root_path(self) -> str:
        """
        Filesystem path to the root of the mounted media

        New media are mounted into directories residing inside this path.

        :return: Path as string
        """
        return defines.mediaRootPath

    @auto_dbus
    def list_projects_raw(self) -> List[str]:
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
    def usb_path(self) -> str:
        """
        Read path to currently inserted USB drive

        :return: Path as string or empty string in case of no USB present
        """
        path = get_save_path()
        if path:
            return str(path)
        return ""
