# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods

import logging
import re
import socket
import subprocess
from threading import Thread, Lock
from time import sleep
from typing import Optional, Callable, List, Any

import gpio
import serial
from PySignal import Signal
from evdev import UInput, ecodes

from sl1fw import defines
from sl1fw.motion_controller.queue_stream import QueueStream
from sl1fw.motion_controller.states import (
    MotConComState,
    ResetFlags,
    CommError,
    StatusBits,
)
from sl1fw.errors.exceptions import MotionControllerException, MotionControllerWrongRevision
from sl1fw.motion_controller.trace import LineTrace, LineMarker, Trace


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
        self.fans_state_changed = Signal()

        self.power_button_changed.connect(self._power_button_handler)
        self.cover_state_changed.connect(self._cover_state_handler)

    def start(self):
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
                if self.connect(False) != MotConComState.OK:
                    raise MotionControllerException("Reconnect after MC debug in bootloader mode failed", self.trace)

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

    def connect(self, mc_version_check: bool) -> MotConComState:
        try:
            state = self.getStateBits(["fatal", "reset"])
        except MotionControllerException:
            self.logger.exception("Motion controller connect failed")
            return MotConComState.COMMUNICATION_FAILED

        if state["fatal"]:
            return MotConComState(self.doGetInt("?err"))

        if state["reset"]:
            reset_bits = self.doGetBoolList("?rst", bit_count=8)
            bit = 0
            for val in reset_bits:
                if val:
                    self.logger.info("motion controller reset flag: %s", ResetFlags(bit).name)
                bit += 1

        tmp = self.doGetIntList("?rev")
        self.fw['revision'] = tmp[0]
        self.board['revision'] = divmod(tmp[1], 32)[1]
        self.board['subRevision'] = chr(divmod(tmp[1], 32)[0] + ord("a"))
        self.logger.info(
            "motion controller board revision: %d%s",
            self.board['revision'],
            self.board['subRevision'],
        )
        if self.board['revision'] != 6:
            raise MotionControllerWrongRevision()

        if self.fw['revision'] != self.board['revision']:
            self.logger.warning(
                "Board and firmware revisions differ! Firmware: %d, board: %d!",
                self.fw['revision'],
                self.board['revision'],
            )
            return MotConComState.WRONG_FIRMWARE

        self.fw['version'] = self.do("?ver")
        if mc_version_check and self.fw['version'] != defines.reqMcVersion:
            return MotConComState.WRONG_FIRMWARE
        self.logger.info("motion controller firmware version: %s", self.fw['version'])

        self.board['serial'] = self.do("?ser")
        if self.board['serial']:
            self.logger.info("motion controller serial number: %s", self.board['serial'])
        else:
            self.logger.warning("motion controller serial number is invalid")
            self.board.serial = "*INVALID*"

        return MotConComState.OK

    def doGetInt(self, *args):
        return self.do(*args, return_process=int)

    def doGetIntList(self, cmd, args=(), base=10, multiply: float = 1):
        return self.do(cmd, *args, return_process=lambda ret: list([int(x, base) * multiply for x in ret.split(" ")]),)

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
        Reads initial garbage found in port. Assumes portlock is already taken
        """
        # TODO: This is not correct, there should be no random garbage around
        while self.in_waiting():
            try:
                line = self._read_port(garbage=True)
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
                raise MotionControllerException("Failed to read line from MC", self.trace) from e

            ok_match = self.commOKStr.match(line)

            if ok_match is not None:
                response = ok_match.group(1).strip() if ok_match.group(1) else ""
                try:
                    return return_process(response)
                except Exception as e:
                    raise MotionControllerException("Failed to process MC response", self.trace) from e

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
                self.logger.warning("Garbage response received: %s", line)
            else:
                raise MotionControllerException("MC command resulted in non-response line", self.trace)

    def soft_reset(self) -> None:
        with self._command_lock:
            try:
                self._read_garbage()
                self.trace.append_trace(LineTrace(LineMarker.RESET, b"Motion controller soft reset"))
                self.write_port("!rst\n".encode("ascii"))

                self._ensure_ready()
            except Exception as e:
                raise MotionControllerException("Reset failed", self.trace) from e

    def _ensure_ready(self) -> None:
        """
        Ensure MC is ready after reset/flash
        This assumes portLock to be already acquired
        """
        try:
            self.logger.debug('"MCUSR..." read resulted in: "%s"', self.read_port_text())
            ready = self.read_port_text()
            if ready != "ready":
                self.logger.info(
                    '"ready" read resulted in: "%s". Sleeping to ensure MC is ready.', ready,
                )
                sleep(1.5)
                self._read_garbage()
        except Exception as e:
            raise MotionControllerException("Ready read failed", self.trace) from e

    def flash(self, mc_board_version):
        with self._flash_lock:
            with self._raw_read_lock:
                self.reset()

                process = subprocess.Popen(
                    [defines.flashMcCommand, defines.dataPath, str(mc_board_version), defines.motionControlDevice],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                )
                while True:
                    line = process.stdout.readline()
                    retc = process.poll()
                    if line == "" and retc is not None:
                        break
                    if line:
                        line = line.strip()
                        if line == "":
                            continue
                        self.logger.info("flashMC output: '%s'", line)

                if retc:
                    self.logger.error("%s failed with code %d", defines.flashMcCommand, retc)

            self._ensure_ready()

        return MotConComState.UPDATE_FAILED if retc else MotConComState.OK

    def reset(self) -> None:
        """
        Does a hard reset of the motion controller.
        Assumes portLock is already acquired
        """
        self.logger.info("Doing hard reset of the motion controller")
        self.trace.append_trace(LineTrace(LineMarker.RESET, b"Motion controller hard reset"))
        gpio.setup(131, gpio.OUT)
        gpio.set(131, 1)
        sleep(1 / 1000000)
        gpio.set(131, 0)

    def getStateBits(self, request: List[str] = None, check_for_updates: bool = True):
        if not request:
            request = StatusBits.__members__.keys()

        bits = self.doGetBoolList("?", bit_count=16)

        if len(bits) != 16:
            raise ValueError(f"State bits count not match! ({bits})")

        if check_for_updates:
            self._handle_updates(bits)

        return {name: bits[StatusBits.__members__[name.upper()].value] for name in request}

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
            self.fans_state_changed.emit(state_bits[fans_ids])

        self._old_state_bits = state_bits

    def _power_button_handler(self, state: bool):
        # pylint: disable=no-member
        self.u_input.write(ecodes.EV_KEY, ecodes.KEY_POWER, 1 if state else 0)
        self.u_input.syn()

    def _cover_state_handler(self, state: bool):
        # pylint: disable=no-member
        self.u_input.write(ecodes.EV_KEY, ecodes.KEY_CLOSE, 1 if state else 0)
        self.u_input.syn()
