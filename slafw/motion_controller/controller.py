# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods

import asyncio
import logging
import re
import socket
import subprocess
from asyncio import Task, CancelledError
from threading import Thread, Lock
from time import sleep
from typing import Optional, Callable, List, Any, Tuple

from gpiod import chip, line_request, find_line
import serial
from PySignal import Signal
from evdev import UInput, ecodes

from slafw import defines
from slafw.motion_controller.queue_stream import QueueStream
from slafw.motion_controller.states import (
    ResetFlags,
    CommError,
    StatusBits,
)
from slafw.errors.errors import MotionControllerException, MotionControllerWrongRevision, MotionControllerWrongFw, \
    MotionControllerNotResponding, MotionControllerWrongResponse
from slafw.motion_controller.trace import LineTrace, LineMarker, Trace
from slafw.functions.decorators import safe_call
from slafw.utils.value_checker import ValueChecker, UpdateInterval


class MotionController:
    fw = {
        "version": "",
        "revision": -1
    }
    board = {
        "revision": -1,
        "subRevision": "",
        "serial": ""
    }

    BAUD_RATE_NORMAL = 115200
    BAUD_RATE_BOOTLOADER = 19200
    TIMEOUT_SEC = 3
    TEMP_UPDATE_INTERVAL_S = 3
    FAN_UPDATE_INTERVAL_S = 3

    commOKStr = re.compile("^(.*)ok$")
    commErrStr = re.compile("^e(.)$")

    def __init__(self, device: str):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.device = device
        self.trace = Trace(defines.traces)

        self._debug_sock: Optional[socket.socket] = None
        self._port: Optional[serial.Serial] = None
        self._read_stream = QueueStream(self.TIMEOUT_SEC)
        self._reader_thread: Optional[Thread] = None
        self._debug_thread: Optional[Thread] = None
        self._raw_read_lock = Lock()
        self._command_lock = Lock()
        self._exclusive_lock = Lock()
        self._flash_lock = Lock()

        self.u_input: Optional[UInput] = None
        self._old_state_bits: Optional[List[bool]] = None

        self.tower_status_changed = Signal()
        self.tilt_status_changed = Signal()
        self.power_button_changed = Signal()
        self.cover_state_changed = Signal()
        self.value_refresh_failed = Signal()
        self.temps_changed = Signal()
        self.fans_rpm_changed = Signal()
        self.fans_error_changed = Signal()
        self.statistics_changed = Signal()

        self.power_button_changed.connect(self._power_button_handler)
        self.cover_state_changed.connect(self._cover_state_handler)

        self._value_refresh_thread = Thread(target=self._value_refresh_body, daemon=True)
        self._value_refresh_task: Optional[Task] = None
        self._fans_mask = {0: False, 1: False, 2: False}
        self._fans_rpm = {0: defines.fanMinRPM, 1: defines.fanMinRPM, 2: defines.fanMinRPM}


    def open(self):
        self._port = serial.Serial()
        self._port.port = self.device
        self._port.baudrate = self.BAUD_RATE_NORMAL
        self._port.bytesize = 8
        self._port.parity = "N"
        self._port.stopbits = 1
        self._port.timeout = self.TIMEOUT_SEC
        self._port.writeTimeout = self.TIMEOUT_SEC
        self._port.xonxoff = False
        self._port.rtscts = False
        self._port.dsrdtr = False
        self._port.interCharTimeout = None

        self._port.open()

        # pylint: disable=no-member
        self.u_input = UInput(
            {ecodes.EV_KEY: [ecodes.KEY_CLOSE, ecodes.KEY_POWER]}, name="sl1-motioncontroller", version=0x1,
        )

        self._reader_thread = Thread(target=self._port_read_thread, daemon=True)
        self._reader_thread.start()

    def __del__(self):
        self.exit()

    def exit(self):
        if self.is_open:
            self._port.close()
        if self.u_input:
            self.u_input.close()
        if self._value_refresh_thread.is_alive():
            while not self._value_refresh_task:
                sleep(0.1)
            self._value_refresh_task.cancel()
            self._value_refresh_thread.join()

    def _port_read_thread(self):
        """
        Body of a thread responsible for reading data from serial port

        This reads everything from serial and
           - Stores it in a queue stream for later use
           - Sends it to the debugger
        """
        while self._port.is_open:
            with self._raw_read_lock:
                try:
                    data = self._port.read()
                except serial.SerialTimeoutException:
                    data = b""
            if data:
                self._read_stream.put(data)
                self._debug_send(data)

    def in_waiting(self) -> bool:
        return self._read_stream.waiting()

    @property
    def is_open(self) -> bool:
        return self._port.is_open if self._port else False

    def _read_port(self, garbage=False) -> bytes:
        """
        Read raw line from motion controller

        :param garbage: Whenever to mark line read as garbage in command trace
        :return: Line read as raw bytes
        """
        marker = LineMarker.GARBAGE if garbage else LineMarker.INPUT
        ret = self._read_stream.readline()
        trace = LineTrace(marker, ret)
        self.trace.append_trace(trace)
        return ret

    def read_port_text(self, garbage=False) -> str:
        """
        Read line from serial as stripped decoded text

        :param garbage: Mark this data as garbage. Line will be marked as such in trace
        :return: Line read from motion controller
        """
        return self._read_port(garbage=garbage).decode("ascii").strip()

    def write_port(self, data: bytes) -> int:
        """
        Write data to a motion controller

        :param data: Data to be written
        :return: Number of bytes written
        """
        self.trace.append_trace(LineTrace(LineMarker.OUTPUT, data))
        self._debug_send(bytes(LineMarker.OUTPUT) + data)
        return self._port.write(data)

    def start_debugging(self, bootloader: bool) -> None:
        """
        Starts debugger thread

        :param bootloader: True for bootloader mode, False for user mode
        :return: None
        """
        self._debug_thread = Thread(target=self._debug, args=(bootloader,))
        self._debug_thread.start()

    def _debug(self, bootloader: bool) -> None:
        """
        Debugging thread body

        This runs the debugging session. Initially this thread waits for debugger connection
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", defines.mc_debug_port))
            self.logger.info("Listening for motion controller debug connection")
            s.listen(1)
            self._debug_sock, address = s.accept()
            self.logger.info("Debug connection accepted from %s", address)

            if bootloader:
                self._debug_bootloader()
            else:
                self._debug_user()

            self.logger.info("Terminating debugging session on client disconnect")
            self._debug_sock = None
            s.close()
            self._port.baudrate = self.BAUD_RATE_NORMAL
            self.logger.info("Debugging session terminated")

            if bootloader:
                # A custom firmware was uploaded, lets reconnect with version check disabled
                self.connect(False)

    def _debug_bootloader(self):
        self.logger.info("Starting bootloader debugging session")
        with self._exclusive_lock:
            self._port.baudrate = self.BAUD_RATE_BOOTLOADER
            self.reset()

            while True:
                data = self._debug_sock.recv(1)
                if not data:
                    break
                self._port.write(data)

    def _debug_user(self):
        self.logger.info("Starting normal debugging session")
        self._debug_sock.sendall(b"\n\n\n>>> Debugging session started, command history: <<<\n\n\n")
        self._debug_sock.sendall(bytes(self.trace))
        self._debug_sock.sendall(b"\n\n\n>>> Type #stop for exclusive mode <<<\n\n\n")

        with self._debug_sock.makefile("rb") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                if line.startswith(b"#stop"):
                    self.logger.info("Starting exclusive debugging")
                    if not self._exclusive_lock.locked():
                        self.logger.debug("Switching to exclusive debugging")
                        self._exclusive_lock.acquire()
                        self._debug_sock.sendall(b"\n\n\n>>> Now in exclusive mode type #cont to leave it <<<\n\n\n")
                    else:
                        self._debug_sock.sendall(b"\n\n\n>>> Exclusive mode already enabled <<<\n\n\n")

                elif line.startswith(b"#cont"):
                    self.logger.info("Stopping exclusive debugging")
                    if self._exclusive_lock.locked():
                        self.logger.debug("Switching to normal debugging")
                        self._exclusive_lock.release()
                        self._debug_sock.sendall(b"\n\n\n>>> Now in normal mode <<<\n\n\n")
                    else:
                        self._debug_sock.sendall(b"\n\n\n>>> Already in normal mode, do action <<<\n\n\n")
                else:
                    with self._command_lock:
                        self.logger.debug("Passing user command: %s", line)
                        self._port.write(line)
            if self._exclusive_lock.locked():
                self._exclusive_lock.release()

    def _debug_send(self, data: bytes):
        if self._debug_sock:
            try:
                self._debug_sock.sendall(data)
            except BrokenPipeError:
                self.logger.exception("Attempt to send data to broken debug socket")

    def connect(self, mc_version_check: bool = True) -> None:
        if not self.is_open:
            self.open()
        state = self.getStateBits(["fatal", "reset"], check_for_updates=False)
        if state["fatal"]:
            raise MotionControllerException("MC failed with fatal flag", self.trace)
        if state["reset"]:
            reset_bits = self.doGetBoolList("?rst", bit_count=8)
            bit = 0
            for val in reset_bits:
                if val:
                    self.logger.info("motion controller reset flag: %s", ResetFlags(bit).name)
                bit += 1
        tmp = self._get_board_revision()
        self.fw['revision'] = tmp[0]
        self.board['revision'] = divmod(tmp[1], 32)[1]
        self.board['subRevision'] = chr(divmod(tmp[1], 32)[0] + ord("a"))
        self.logger.info(
            "motion controller board revision: %d%s",
            self.board['revision'],
            self.board['subRevision'],
        )
        if self.board['revision'] != 6:
            raise MotionControllerWrongRevision(trace=self.trace)
        if self.fw['revision'] != self.board['revision']:
            self.logger.warning(
                "Board and firmware revisions differ! Firmware: %d, board: %d!",
                self.fw['revision'],
                self.board['revision'],
            )
            raise MotionControllerWrongFw(trace=self.trace)
        self.fw['version'] = self.do("?ver")
        self.logger.info("Motion controller firmware version: %s", self.fw['version'])
        if mc_version_check:
            if self.fw['version'] != defines.reqMcVersion:
                raise MotionControllerWrongFw(
                    message="Incorrect firmware, version %s is required" % defines.reqMcVersion,
                    trace=self.trace
                )

        self.board['serial'] = self.do("?ser")
        if self.board['serial']:
            self.logger.info("motion controller serial number: %s", self.board['serial'])
        else:
            self.logger.warning("motion controller serial number is invalid")
            self.board['serial'] = "*INVALID*"

        # Value refresh thread
        self.temps_changed.emit(self._get_temperatures())  # Initial values for MC temperatures
        self._value_refresh_thread.start()

    def doGetInt(self, *args):
        return self.do(*args, return_process=int)

    def doGetIntList(self, cmd, args=(), base=10, multiply: float = 1):
        return self.do(cmd, *args, return_process=lambda ret: list([int(x, base) * multiply for x in ret.split(" ")]), )

    def doGetBool(self, cmd, *args):
        return self.do(cmd, *args, return_process=lambda x: x == "1")

    def doGetBoolList(self, cmd, bit_count, args=()) -> List[bool]:
        def process(data):
            bits = list()
            num = int(data)
            for i in range(bit_count):
                bits.append(bool(num & (1 << i)))
            return bits

        return self.do(cmd, *args, return_process=process)

    def doGetHexedString(self, *args):
        return self.do(*args, return_process=lambda x: bytes.fromhex(x).decode("ascii"))

    def doSetBoolList(self, command, bits):
        bit = 0
        out = 0
        for val in bits:
            out |= 1 << bit if val else 0
            bit += 1
        self.do(command, out)

    def _read_garbage(self) -> None:
        """
        Reads initial garbage/comments found in port.

        This assumes portlock is already taken

        Random garbage/leftovers signal an error. Lines starting with comment "#" are considered debug output of the
        motion controller code. Those produced by asynchronous commands (like tilt/tower home) end up here.
        """
        while self.in_waiting():
            try:
                line = self._read_port(garbage=True)
                if line.startswith(b"#"):
                    self.logger.debug("Comment in MC port: %s", line)
                else:
                    self.logger.warning("Garbage pending in MC port: %s", line)
            except (serial.SerialException, UnicodeError) as e:
                raise MotionControllerException("Failed garbage read", self.trace) from e

    def do(self, cmd, *args, return_process: Callable = lambda x: x) -> Any:
        with self._exclusive_lock, self._command_lock:
            if self._flash_lock.acquire(blocking=False):
                try:
                    self._read_garbage()
                    self.do_write(cmd, *args)
                    return self.do_read(return_process=return_process)
                finally:
                    self._flash_lock.release()
            else:
                raise MotionControllerException("MC flash in progress", self.trace)

    def do_write(self, cmd, *args) -> None:
        """
        Write command

        :param cmd: Command string
        :param args: Command arguments
        :return: None
        """
        cmd_string = " ".join(str(x) for x in (cmd,) + args)
        try:
            self.write_port(f"{cmd_string}\n".encode("ascii"))
        except serial.SerialTimeoutException as e:
            raise MotionControllerException(f"Timeout writing serial port: {cmd_string}", self.trace) from e

    def do_read(self, return_process: Callable) -> Any:
        """
        Read until some response is received

        :return: Processed MC response
        """
        while True:
            try:
                line = self.read_port_text()
            except Exception as e:
                raise MotionControllerNotResponding("Failed to read line from MC", self.trace) from e

            ok_match = self.commOKStr.match(line)

            if ok_match is not None:
                response = ok_match.group(1).strip() if ok_match.group(1) else ""
                try:
                    return return_process(response)
                except Exception as e:
                    raise MotionControllerWrongResponse("Failed to process MC response", self.trace) from e

            err_match = self.commErrStr.match(line)
            if err_match is not None:
                try:
                    err_code = int(err_match.group(1))
                except ValueError:
                    err_code = 0
                err = CommError(err_code).name
                self.logger.error("error: '%s'", err)
                raise MotionControllerException(f"MC command failed with error: {err}", self.trace)

            if line.startswith("#"):
                self.logger.debug("Received comment response: %s", line)
            else:
                raise MotionControllerException("MC command resulted in non-response line", self.trace)

    def soft_reset(self) -> None:
        with self._exclusive_lock, self._command_lock:
            if self._flash_lock.acquire(blocking=False):
                try:
                    self._read_garbage()
                    self.trace.append_trace(LineTrace(LineMarker.RESET, b"Motion controller soft reset"))
                    self.write_port("!rst\n".encode("ascii"))
                    self._ensure_ready(after_soft_reset=True)
                except Exception as e:
                    raise MotionControllerException("Reset failed", self.trace) from e
                finally:
                    self._flash_lock.release()
            else:
                raise MotionControllerException("MC flash in progress", self.trace)

    def _ensure_ready(self, after_soft_reset=False) -> None:
        """
        Ensure MC is ready after reset/flash
        This assumes portLock to be already acquired
        """
        try:
            mcusr = self.read_port_text()
            if after_soft_reset and self.commOKStr.match(mcusr):
                # This handles a bug in MC, !rst is sometimes not responded with ok. Correct solution is to ensure "ok"
                # is returned and handling soft reset as general command. This just eats the "ok" in case it is present.
                self.logger.debug("Detected \"ok\" instead of MCUSR, skipping")
                mcusr = self.read_port_text()
            self.logger.debug('"MCUSR..." read resulted in: "%s"', mcusr)
            ready = self.read_port_text()
            if ready != "ready":
                self.logger.info('"ready" read resulted in: "%s". Sleeping to ensure MC is ready.', ready)
                sleep(1.5)
                self._read_garbage()
        except Exception as e:
            raise MotionControllerException("Ready read failed", self.trace) from e

    def flash(self, mc_board_version) -> None:
        with self._flash_lock:
            with self._raw_read_lock:
                self.reset()

                process = subprocess.Popen(
                    [defines.script_dir / "flashMC.sh",
                        defines.dataPath,
                        str(mc_board_version),
                        defines.motionControlDevice],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                )
                while True:
                    line = process.stdout.readline()
                    try:
                        retc = process.poll()
                    except Exception as e:
                        raise MotionControllerException(f"Flashing MC failed with code {retc}", self.trace) from e
                    if line == "" and retc is not None:
                        break
                    if line:
                        line = line.strip()
                        if line == "":
                            continue
                        self.logger.info("flashMC output: '%s'", line)

            self._ensure_ready()

    def reset(self) -> None:
        """
        Does a hard reset of the motion controller.
        Assumes portLock is already acquired
        """
        self.logger.info("Doing hard reset of the motion controller")
        self.trace.append_trace(LineTrace(LineMarker.RESET, b"Motion controller hard reset"))
        rst = find_line("mc-reset")
        if not rst:
            self.logger.info("GPIO mc-reset not found")
            rst = chip(2).get_line(131)  # type: ignore[assignment]
        if not rst:
            raise MotionControllerException("Hard reset failed", self.trace)
        config = line_request()
        config.request_type = line_request.DIRECTION_OUTPUT
        rst.request(config)
        rst.set_value(1)
        sleep(1 / 1000000)
        rst.set_value(0)

    def getStateBits(self, request: List[str] = None, check_for_updates: bool = True):
        if not request:
            # pylint: disable = no-member
            request = StatusBits.__members__.keys()  # type: ignore

        bits = self.doGetBoolList("?", bit_count=16)
        if len(bits) != 16:
            raise ValueError(f"State bits count not match! ({bits})")

        if check_for_updates:
            self._handle_updates(bits)

        # pylint: disable = unsubscriptable-object
        return {name: bits[StatusBits.__members__[name.upper()].value] for name in request}

    @safe_call(False, MotionControllerException)
    def checkState(self, name, check_for_updates: bool = True):
        state = self.getStateBits([name], check_for_updates)
        return state[name]

    def _handle_updates(self, state_bits: List[bool]):
        # pylint: disable=no-member
        tower_idx = StatusBits.TOWER.value
        if not self._old_state_bits or state_bits[tower_idx] != self._old_state_bits[tower_idx]:
            self.tower_status_changed.emit(state_bits[tower_idx])
        tilt_idx = StatusBits.TILT.value
        if not self._old_state_bits or state_bits[tilt_idx] != self._old_state_bits[tilt_idx]:
            self.tilt_status_changed.emit(state_bits[tilt_idx])
        power_idx = StatusBits.BUTTON.value
        if not self._old_state_bits or state_bits[power_idx] != self._old_state_bits[power_idx]:
            self.power_button_changed.emit(state_bits[power_idx])
        cover_idx = StatusBits.COVER.value
        if not self._old_state_bits or state_bits[cover_idx] != self._old_state_bits[cover_idx]:
            self.cover_state_changed.emit(state_bits[cover_idx])
        fans_ids = StatusBits.FANS.value
        if not self._old_state_bits or state_bits[fans_ids] != self._old_state_bits[fans_ids]:
            self.fans_error_changed.emit(self.get_fans_error())
        self._old_state_bits = state_bits

    def _power_button_handler(self, state: bool):
        # pylint: disable=no-member
        self.u_input.write(ecodes.EV_KEY, ecodes.KEY_POWER, 1 if state else 0)
        self.u_input.syn()

    def _cover_state_handler(self, state: bool):
        # pylint: disable=no-member
        self.u_input.write(ecodes.EV_KEY, ecodes.KEY_CLOSE, 1 if state else 0)
        self.u_input.syn()

    def _get_board_revision(self):
        return self.doGetIntList("?rev")

    def _get_temperatures(self):
        temps = self.doGetIntList("?temp", multiply=0.1)
        if len(temps) != 4:
            raise ValueError(f"TEMPs count not match! ({temps})")

        return [round(temp, 1) for temp in temps]

    def _value_refresh_body(self):
        self.logger.info("Value refresh thread running")
        try:
            # Run refresh task
            asyncio.run(self._value_refresh())
        except CancelledError:
            pass  # This is normal printer shutdown
        except Exception:
            self.logger.exception("Value checker crashed")
            self.value_refresh_failed.emit()
            raise
        finally:
            self.logger.info("Value refresh checker ended")

    async def _value_refresh(self):
        checkers = [
            ValueChecker(
                self._get_temperatures, self.temps_changed, UpdateInterval.seconds(self.TEMP_UPDATE_INTERVAL_S)
            ),
            ValueChecker(self._get_fans_rpm, self.fans_rpm_changed, UpdateInterval.seconds(self.FAN_UPDATE_INTERVAL_S)),
            ValueChecker(self._get_statistics, self.statistics_changed, UpdateInterval.seconds(30)),
        ]
        checks = [checker.check() for checker in checkers]
        self._value_refresh_task = asyncio.gather(*checks)
        await self._value_refresh_task

    def set_fan_enabled(self, index: int, enabled: bool):
        self._fans_mask[index] = enabled
        self.doSetBoolList("!fans", self._fans_mask.values())

    def set_fan_rpm(self, index: int, rpm: int):
        self._fans_rpm[index] = rpm
        self.do("!frpm", " ".join([str(v) for v in self._fans_rpm.values()]))

    def _get_fans_rpm(self) -> Tuple[int, int, int]:
        rpms = self.doGetIntList("?frpm", multiply=1)
        if not rpms or len(rpms) != 3:
            raise MotionControllerException(f"RPMs count not match! ({rpms})")

        return rpms

    def _get_statistics(self):
        data = self.doGetIntList("?usta")  # time counter [s] #TODO add uv average current, uv average temperature
        if len(data) != 2:
            raise ValueError(f"UV statistics data count not match! ({data})")

        return data

    @safe_call({0: True, 1: True, 2: True}, (MotionControllerException, ValueError))
    def get_fans_error(self):
        state = self.getStateBits(["fans"], check_for_updates=False)
        if "fans" not in state:
            raise ValueError(f"'fans' not in state: {state}")

        return self.get_fans_bits("?fane", (0, 1, 2))

    def get_fans_bits(self, cmd, request):
        bits = self.doGetBoolList(cmd, bit_count=3)
        if len(bits) != 3:
            raise ValueError(f"Fans bits count not match! {bits}")

        return {idx: bits[idx] for idx in request}
