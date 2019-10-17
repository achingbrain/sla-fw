# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from enum import Enum, auto
from time import monotonic
from typing import List, Dict, Tuple, Union, TYPE_CHECKING
import distro
import pydbus
from pydbus.generic import signal

from sl1fw import actions
from sl1fw.api.display_test0 import DisplayTest0

if TYPE_CHECKING:
    from sl1fw.libPrinter import Printer


class Printer0State(Enum):
    def _generate_next_value_(self, start, count, last_values):
        return self

    INITIALIZING = auto()
    IDLE = auto()
    UNBOXING = auto()
    WIZARD = auto()
    CALIBRATION = auto()
    DISPLAY_TEST = auto()
    PRINTING = auto()
    UPDATE = auto()
    ADMIN = auto()
    EXCEPTION = auto()


class NotAvailableInState(Exception):
    pass


class PositionNotAvailable(Exception):
    pass


def state_checked(allowed_state: Union[Printer0State, List[Printer0State]]):
    """
    Decorator restricting method call based on allowed state
    :param allowed_state: State in which the method is available, or list of such states
    :return: Method decorator
    """

    def decor(function):
        def func(self, *args, **kwargs):
            if isinstance(allowed_state, list):
                allowed_names = [state.name for state in allowed_state]
            else:
                allowed_names = [allowed_state.name]
            if self.state in allowed_names:
                return function(self, *args, **kwargs)
            else:
                raise NotAvailableInState
        if hasattr(function, "__dbus__"):
            func.__dbus__ = function.__dbus__
        func.__doc__ = function.__doc__
        return func
    return decor


def cached(validity_s: float = None):
    """
    Decorator limiting calls to property by using a cache with defined validity.
    This does not support passing arguments other than self to decorated method!
    :param validity_s: Cache validity in seconds, None means valid forever
    :return: Method decorator
    """

    def decor(function):
        cache = {}

        def func(self):
            if 'value' not in cache or 'last' not in cache or (
                    validity_s is not None and monotonic() - cache['last'] > validity_s):
                cache['value'] = function(self)
                cache['last'] = monotonic()
            return cache['value']
        if hasattr(function, "__dbus__"):
            func.__dbus__ = function.__dbus__
        func.__doc__ = function.__doc__
        return func
    return decor


def dbus_api(cls):
    records: List[str] = []
    for var in vars(cls):
        obj = getattr(cls, var)
        if isinstance(obj, property):
            obj = obj.fget
        if hasattr(obj, "__dbus__"):
            record = obj.__dbus__
            assert isinstance(record, str)
            records.append(record)
    cls.dbus = f"<node><interface name='{cls.__INTERFACE__}'>{''.join(records)}</interface></node>"
    return cls


def dbus_record(dbus: str):
    def decor(func):
        if func.__doc__ is None:
            func.__doc__ = ""
        func.__doc__ += f"\nD-Bus interface:: \n\n\t" + "\n\t".join(dbus.splitlines())
        func.__dbus__ = dbus
        return func
    return decor


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
    @dbus_record("""
        <property name="state" type="s" access="read">
            <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
        </property>""")
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

    @property
    @dbus_record("""
    <property name="current_page" type="s" access="read">
        <!-- DEPRECATED, we would like to switch to explicit state machine on global state -->
        <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
    </property>""")
    def current_page(self) -> str:
        """
        Get current page name

        DEPRECATED, use state if possible

        :return: Current page name
        """
        return self.printer.get_actual_page().Name

    @dbus_record("""
    <method name="beep">
        <arg type='i' name="frequency_hz" direction='in'/>
        <arg type='i' name="length_ms" direction='in'/>
    </method>
    """)
    def beep(self, frequency_hz: int, length_ms:int) -> None:
        """
        Motion controller beeper beep

        :param frequency_hz: Beep frequency in Hz
        :param length_ms: Beep duration in ms
        :return: None
        """
        self.printer.hw.beep(frequency_hz, length_ms / 1000)

    @dbus_record('<method name="save_logs_to_usb"/>')
    def save_logs_to_usb(self) -> None:
        """
        Save logs to first usb device
        :return: None
        """
        actions.save_logs_to_usb(self.printer.hw.cpuSerialNo)

    @state_checked([Printer0State.IDLE, Printer0State.EXCEPTION])
    @dbus_record("""
    <method name="poweroff">
       <arg type='b' name="do_shutdown" direction='in'/>
       <arg type='b' name="reboot" direction='in'/>
    </method>
    """)
    def poweroff(self, do_shutdown: bool, reboot: bool) -> None:
        """
        Shut down the printer

        :param do_shutdown: True for real action, False just restarts the printer logic
        :param reboot: True does reboot, False means real shutdown
        :return: None
        """
        self.printer.display.shutDown(do_shutdown, reboot=reboot)

    @state_checked(Printer0State.IDLE)
    @dbus_record('<method name="tower_home"/>')
    def tower_home(self) -> None:
        """
        Home tower axis
        """
        self.printer.hw.tower_home()

    @state_checked(Printer0State.IDLE)
    @dbus_record('<method name="tilt_home"/>')
    def tilt_home(self) -> None:
        """
        Home tilt axis

        :return: None
        """
        self.printer.hw.tilt_home()

    @state_checked(Printer0State.IDLE)
    @dbus_record('<method name="disable_motors"/>')
    def disable_motors(self) -> None:
        """
        Disable motors

        This ends the annoying sound.

        :return: None
        """
        self.printer.hw.motorsRelease()

    @state_checked(Printer0State.IDLE)
    @dbus_record("""
    <method name="tower_move">
        <arg type='i' name="speed" direction='in'/>
        <arg type='b' name="success" direction='out'/>
    </method>""")
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
    @dbus_record("""
    <method name="tilt_move">
        <arg type='i' name="speed" direction='in'/>
        <arg type='b' name="success" direction='out'/>
    </method>""")
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
    @dbus_record("""
    <property name="tower_position_nm" type="i" access="readwrite">
        <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
    </property>""")
    def tower_position_nm(self) -> int:
        """
        Read or set tower position in nm
        """
        return self.printer.hw.tower_position_nm

    @tower_position_nm.setter
    @state_checked(Printer0State.IDLE)
    def tower_position_nm(self, position_nm: int) -> None:
        self.printer.hw.tower_position_nm = position_nm

    @property
    @dbus_record("""
    <property name="tilt_position" type="i" access="readwrite">
        <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
    </property>""")
    def tilt_position(self) -> int:
        """
        Read or set tilt position in micro-steps
        """
        return self.printer.hw.tilt_position

    @tilt_position.setter
    @state_checked(Printer0State.IDLE)
    def tilt_position(self, micro_steps: int):
        self.printer.hw.tilt_position = micro_steps

    @dbus_record('<method name="get_projects"/>')
    def get_projects(self) -> List[str]:
        """
        Get available project files

        NOT IMPLEMENTED

        :return: Array of project file paths
        """
        raise NotImplementedError

    @dbus_record('<method name="get_firmwares"/>')
    def get_firmwares(self):
        """
        Get available firmware files

        NOT IMPLEMENTED

        :return: Array of firware sources (file, network)
        """
        raise NotImplementedError

    @property
    @cached()
    @dbus_record('<property name="serial_number" type="s" access="read"/>')
    def serial_number(self) -> str:
        """
        Get A64 serial

        :return: A64 serial number
        """
        return self.printer.hw.cpuSerialNo

    @property
    @cached()
    @dbus_record('<property name="system_name" type="s" access="read"/>')
    def system_name(self) -> str:
        """
        Get system name

        :return: System distribution name
        """
        return distro.name()

    @property
    @cached()
    @dbus_record('<property name="system_version" type="s" access="read"/>')
    def system_version(self) -> str:
        """
        Get system version

        :return: System distribution version
        """
        return distro.version()

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="fans" type="a{si}" access="read"/>')
    def fans(self) -> Dict[str, int]:
        """
        Get fan RPMs

        :return: Dictionary mapping from fan names to RPMs
        """
        return {'fan%d_rpm' % i: v for i, v in self.printer.hw.getFansRpm().items()}

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="temps" type="a{sd}" access="read"/>')
    def temps(self) -> Dict[str, float]:
        """
        Get temperatures

        :return: Dictionary mapping from temp sensor name to temperature in celsius
        """
        return {'temp%d_celsius' % i: v for i, v in enumerate(self.printer.hw.getMcTemperatures())}

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="cpu_temp" type="d" access="read"/>')
    def cpu_temp(self) -> float:
        """
        Get A64 temperature

        :return: A64 CPU temperature
        """
        return self.printer.hw.getCpuTemperature()

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="leds" type="a{sd}" access="read"/>')
    def leds(self) -> Dict[str, float]:
        """
        Get UV LED voltages

        :return: Dictionary mapping from LED channel anme to volatage value
        """
        return {'led%d_voltage_volt' % i: v for i, v in enumerate(self.printer.hw.getVoltages())}

    @property
    @cached(validity_s=5)
    @dbus_record("""
    <property name="devlist" type="a{ss}" access="read">
        <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
    </property>""")
    def devlist(self) -> Dict[str, str]:
        """
        Get network devices

        :return: Dictinary mapping from interface names to IP address strings
        """
        return self.printer.inet.devices

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="uv_statistics" type="a{si}" access="read"/>')
    def uv_statistics(self) -> Dict[str, int]:
        """
        Get UV statistics

        :return: Dictinary mapping from statistics name to integer value
        """
        return {'uv_stat%d' % i: v for i, v in enumerate(self.printer.hw.getUvStatistics())}
        # uv_stats0 - time counter [s] # TODO: add uv average current,

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="controller_sw_version" type="s" access="read"/>')
    def controller_sw_version(self) -> str:
        """
        Get motion controller version

        :return: Version string
        """
        return self.printer.hw.mcFwVersion

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="controller_serial" type="s" access="read"/>')
    def controller_serial(self) -> str:
        """
        Get motion controller serial

        :return: Serial number as string
        """
        return self.printer.hw.mcSerialNo

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="controller_revision" type="s" access="read"/>')
    def controller_revision(self) -> str:
        return self.printer.hw.mcBoardRevision

    @property
    @cached()
    @dbus_record('<property name="controller_revision_bin" type="ai" access="read"/>')
    def controller_revision_bin(self) -> Tuple[int, int]:
        return self.printer.hw.mcBoardRevisionBin

    @property
    @cached(validity_s=5)
    @dbus_record("""
    <property name="api_key" type="s" access="read">
        <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
    </property>""")
    def api_key(self) -> str:
        """
        Get current API key

        :return: Current api key string
        """
        return self.printer.get_actual_page().octoprintAuth

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="tilt_fast_time_sec" type="d" access="read"/>')
    def tilt_fast_time_sec(self) -> float:
        """
        Get fast tilt time
        :return: Fast tilt time in seconds
        """
        return self.printer.hwConfig.tiltFastTime

    @property
    @cached(validity_s=5)
    @dbus_record('<property name="tilt_slow_time_sec" type="d" access="read"/>')
    def tilt_slow_time_sec(self) -> float:
        """
        Get slow tilt time

        :return: Fast slow time in seconds
        """
        return self.printer.hwConfig.tiltSlowTime

    @dbus_record("""
    <method name="enable_resin_sensor">
        <arg type="b" name="value" direction='in'/>
    </method>""")
    def enable_resin_sensor(self, value: bool) -> None:
        """
        Set resin sensor enabled flag

        :param value: Enabled / disabled as boolean
        :return: None
        """
        self.printer.hw.resinSensor(value)

    @property
    @cached(validity_s=0.5)
    @dbus_record("""
    <property name="resin_sensor_state" type="b" access="read">
        <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
    </property>""")
    def resin_sensor_state(self) -> bool:
        """
        Get resin sensor state

        :return: True if enabled, False otherwise
        """
        return self.printer.hw.getResinSensorState()

    @property
    @cached(validity_s=0.5)
    @dbus_record("""
    <property name="cover_state" type="b" access="read">
        <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
    </property>""")
    def cover_state(self) -> bool:
        """
        Get cover state

        :return: True of closed, False otherwise
        """
        return self.printer.hw.isCoverClosed()

    @property
    @cached(validity_s=0.5)
    @dbus_record("""
       <property name="power_switch_state" type="b" access="read">
           <!-- TODO: <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/> -->
       </property>""")
    def power_switch_state(self) -> bool:
        """
        Get power switch state

        :return: True if pressed, False otherwise
        """
        return self.printer.hw.getPowerswitchState()

    @property
    @dbus_record('<property name="factory_mode" type="b" access="read"/>')
    def factory_mode(self) -> bool:
        """
        Check for factory mode

        :return: True if in factory mode, False otherwise
        """
        return self.printer.factoryMode

    @dbus_record("""
    <method name="display_test">
          <arg type="o" name="test_path" direction='out'/>
    </method>""")
    def display_test(self):
        """
        Initiate display test object

        :return: Display test object path
        """
        path = "/cz/prusa3d/sl1/printer0/test"

        # If test is already pending just return test object
        if self._display_test:
            return path

        self._display_test = DisplayTest0(self)
        self._display_test_registration = pydbus.SystemBus().register_object(path, self._display_test, None)

        return path


    @dbus_record('<method name="wizard"/>')
    def wizard(self):
        """
        Initiate wizard test object

        NOT IMPLEMENTED

        :return: Wizard object path
        """
        raise NotImplementedError


    @dbus_record('<method name="update_firmware"/>')
    def update_firmware(self):
        """
        Initiate firmware update

        NOT IMPLEMENTED
        """
        # TODO: Do we need to have this here? If we can do update while printing we do not need to care.
        raise NotImplementedError


    @dbus_record('<method name="factory_reset"/>')
    def factory_reset(self) -> None:
        """
        Do factory reset

        NOT IMPLEMENTED
        """
        raise NotImplementedError


    @dbus_record('<method name="enter_admin"/>')
    def enter_admin(self) -> None:
        """
        Initiate admin mode

        NOT IMPLEMENTED
        """
        raise NotImplementedError

    @dbus_record('<method name="print"/>')
    def print(self, project_path: str, auto_advance: bool) -> None:
        """Start printing project NOT IMPLEMENTED

        :param project_path: Path to project in printer filesystem
        :param auto_advance: Automatic print, no further questions

        :returns: Print task object
        """
        raise NotImplementedError

    @dbus_record('<method name="advanced_settings"/>')
    def advanced_settings(self) -> None:
        """
        Initiate advanced settings

        NOT IMPLEMENTED

        :return: Advanced settings control object
        """
        raise NotImplementedError
