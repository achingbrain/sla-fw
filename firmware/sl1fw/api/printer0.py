# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import List, Dict, Tuple, TYPE_CHECKING

import distro
import pydbus
from deprecated import deprecated
from pydbus.generic import signal

from sl1fw import actions
from sl1fw.api.decorators import dbus_api, state_checked, cached, auto_dbus, DBusObjectPath
from sl1fw.api.display_test0 import DisplayTest0
from sl1fw.api.states import Printer0State

if TYPE_CHECKING:
    from sl1fw.libPrinter import Printer


@dbus_api
class Printer0:
    """
    This is prototype of the public printer API, implementation is naive, incomplete and possibly broken.
    Keep implementation out of this file. Methods here should only adapt interfaces and reformat data.
    """
    __INTERFACE__ = "cz.prusa3d.sl1.printer0"

    PropertiesChanged = signal()

    PAGE_TO_STATE = {
        "admin": Printer0State.ADMIN,
        "calibrationconfirm": Printer0State.CALIBRATION,
        "exception": Printer0State.EXCEPTION,
        "factoryreset": Printer0State.INITIALIZING,
        "firmwareupdate": Printer0State.UPDATE,
        "print": Printer0State.PRINTING,
        "printstart": Printer0State.PRINTING,
        "start": Printer0State.INITIALIZING,
        "unboxingconfirm": Printer0State.UNBOXING,
        "uvcalibration": Printer0State.CALIBRATION,
        "uvmetershow": Printer0State.CALIBRATION,
        "uvcalibrationtest": Printer0State.CALIBRATION,
        "uvmeter": Printer0State.CALIBRATION,
        "uvcalibrationconfirm": Printer0State.CALIBRATION,
        "wizardinit": Printer0State.WIZARD,
        "wizarduvled": Printer0State.WIZARD,
        "wizardtoweraxis": Printer0State.WIZARD,
        "wizardresinsensor": Printer0State.WIZARD,
        "wizardtimezone": Printer0State.WIZARD,
        "wizardspeaker": Printer0State.WIZARD,
        "wizardfinish": Printer0State.WIZARD,
        "wizardskip": Printer0State.WIZARD,
        "displaytest": Printer0State.DISPLAY_TEST
    }

    PAGE_TO_STATE.update({
        f"calibration{i}": Printer0State.CALIBRATION for i in range(1, 12)
    })

    PAGE_TO_STATE.update({
        f"unboxing{i}": Printer0State.UNBOXING for i in range(1, 6)
    })

    def __init__(self, printer: Printer):
        self.printer = printer
        self._display_test = None
        self._display_test_registration = None
        self._unpacking = None
        self._wizard = None
        self._calibration = None
        self._prints = []

    @property
    @auto_dbus
    def state(self) -> str:
        """
        Get global printer state

        :return: Global printer state
        """
        if self._display_test:
            return Printer0State.DISPLAY_TEST.name

        # This is extremely ugly implementation, but currently it is hard to tell what is the printer doing. This
        # identifies current state based on matching current page stack agains a state to page mapping.
        if self.printer.get_actual_page_stack():
            for p in [p.Name for p in self.printer.get_actual_page_stack()] + [self.printer.get_actual_page().Name]:
                if p in self.PAGE_TO_STATE:
                    return self.PAGE_TO_STATE[p].name
        return Printer0State.IDLE.name

    @auto_dbus
    @property
    @deprecated(reason="Do not rely on current page, use state", action="once")
    def current_page(self) -> str:
        """
        Get current page name

        :return: Current page name
        """
        return self.printer.get_actual_page().Name

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
        actions.save_logs_to_usb(self.printer.hw.cpuSerialNo)

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

        :return: Array of firware sources (file, network)
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

        :return: Dictionary mapping from LED channel anme to volatage value
        """
        return {'led%d_voltage_volt' % i: v for i, v in enumerate(self.printer.hw.getVoltages())}

    @auto_dbus
    @property
    @cached(validity_s=5)
    @deprecated(reason = "Use NetworkManager", action="once")
    def devlist(self) -> Dict[str, str]:
        """
        Get network devices

        :return: Dictinary mapping from interface names to IP address strings
        """
        return self.printer.inet.devices

    @auto_dbus
    @property
    @cached(validity_s=5)
    def uv_statistics(self) -> Dict[str, int]:
        """
        Get UV statistics

        :return: Dictinary mapping from statistics name to integer value
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
        return self.printer.factoryMode

    @auto_dbus
    def display_test(self) -> DBusObjectPath:
        """
        Initiate display test object

        :return: Display test object path
        """
        path = "/cz/prusa3d/sl1/printer0/test"

        # If test is already pending just return test object
        if self._display_test:
            return DBusObjectPath(path)

        self._display_test = DisplayTest0(self)
        self._display_test_registration = pydbus.SystemBus().register_object(path, self._display_test, None)

        return DBusObjectPath(path)

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
    def print(self, project_path: str, auto_advance: bool) -> None:
        """Start printing project NOT IMPLEMENTED

        :param project_path: Path to project in printer filesystem
        :param auto_advance: Automatic print, no further questions

        :returns: Print task object
        """
        raise NotImplementedError

    @auto_dbus
    def advanced_settings(self) -> None:
        """
        Initiate advanced settings

        NOT IMPLEMENTED

        :return: Advanced settings control object
        """
        raise NotImplementedError
