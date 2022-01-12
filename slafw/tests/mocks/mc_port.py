# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import re
from datetime import datetime, timedelta
from queue import Queue
from subprocess import Popen, PIPE
from time import monotonic_ns, sleep
from typing import Optional

from serial.serialutil import SerialTimeoutException

from slafw import defines, test_runtime


class Serial:
    def __init__(self, *_, **kwargs):
        self.implementation = None
        self.port = None
        if "port" in kwargs:
            self.port = kwargs["port"]
            self._set_implementation()

    def _set_implementation(self):
        if self.port == defines.motionControlDevice:
            self.implementation = MCSerial()
        elif self.port == defines.uv_meter_device:
            self.implementation = UVSerial()
        else:
            raise ValueError(f"Port {self.port} has no mock implementation")

    def open(self):
        if not self.implementation:
            self._set_implementation()

        return self.implementation.open()

    @property
    def is_open(self):
        return self.implementation.is_open

    def close(self):
        return self.implementation.close()

    def write(self, data):
        return self.implementation.write(data)

    def read(self):
        return self.implementation.read()

    def inWaiting(self):
        return self.implementation.inWaiting()

    def readline(self):
        return self.implementation.readline()


class UVSerial:
    def __init__(self):
        self._data = Queue()
        self._error_cnt = 0
        self._connect()

    def _connect(self):
        self._data.put("<done".encode())

    def open(self):
        pass

    @property
    def is_open(self):
        return True

    def close(self):
        pass

    def write(self, data):
        if data == b">all\n":
            self._data.put(data)
            if test_runtime.uv_on_until and test_runtime.uv_on_until > datetime.now() and not test_runtime.exposure_image.is_screen_black:
                intensity = self._intensity_response(test_runtime.uv_pwm)
            else:
                intensity = 0
            response = "<" + ",".join([str(intensity) for _ in range(60)]) + ",347"
            self._data.put(response.encode())

    def read(self):
        raise NotImplementedError()

    def readline(self):
        self._simulate_error()
        sleep(0.1)
        return self._data.get()

    def _simulate_error(self):
        if not test_runtime.uv_error_each:
            return

        self._error_cnt += 1
        if self._error_cnt > test_runtime.uv_error_each:
            self._error_cnt = 0
            self._data.put("<done".encode())
            raise IOError("Injected error")

    def inWaiting(self):
        return self._data.qsize()

    @staticmethod
    def _intensity_response(pwm) -> float:
        # Linear response
        # 140 intensity at 200 PWM
        return 140 * pwm / 200


class MCSerial:
    TIMEOUT_MS = 3000

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pwm_re = re.compile(b"!upwm ([0-9][0-9]*)\n")
        self.uled_re = re.compile(b"!uled ([01]) ([0-9][0-9]*)\n")
        self.process: Optional[Popen] = None

    def open(self):
        self.process = Popen(["SLA-control-01.elf"], stdin=PIPE, stdout=PIPE)
        mcusr = self.process.stdout.readline()
        self.logger.debug("MC serial simulator MCUSR = %s", mcusr)
        ready = self.process.stdout.readline()
        self.logger.debug("MC serial simulator ready = %s", ready)
        assert ready == b"ready\n"

    @property
    def is_open(self) -> bool:
        return not (self.process and self.process.returncode)

    def close(self):
        """
        Stop MS Port simulator
        Terminate simulator and output reading thread

        :return: None
        """
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=3)
            self.process.stdin.close()
            self.process.stdout.close()

    def write(self, data: bytes):
        """
        Write data to simulated MC serial port

        :param data: Data to be written to simulated serial port
        :return: None
        """
        self.logger.debug("< %s", data)
        try:
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except IOError:
            self.logger.exception("Failed to write to simulated port")

        # Decode UV PWM
        pwm_match = self.pwm_re.fullmatch(data)
        if pwm_match:
            try:
                test_runtime.uv_pwm = int(pwm_match.groups()[0].decode())
                self.logger.debug("UV PWM discovered: %d", test_runtime.uv_pwm)
            except (IndexError, UnicodeDecodeError, ValueError):
                self.logger.exception("Failed to decode UV PWM from MC data")

        # Decode UV LED state
        led_match = self.uled_re.fullmatch(data)
        if led_match:
            try:
                on = led_match.groups()[0].decode() == "1"
                duration_ms = int(led_match.groups()[1].decode())
                self.logger.debug("UV LED state discovered: %d %d", on, duration_ms)
                if on:
                    if duration_ms:
                        test_runtime.uv_on_until = datetime.now() + timedelta(milliseconds=duration_ms)
                    else:
                        test_runtime.uv_on_until = datetime.now() + timedelta(days=1)
                else:
                    test_runtime.uv_on_until = None
            except (IndexError, UnicodeDecodeError, ValueError):
                self.logger.exception("Failed to decode UV LED state from MC data")

    def read(self):
        """
        Read line from simulated serial port

        TODO: This pretends MC communication start has no weak places. In reality the MC "usually" starts before
              the libHardware. In such case the "start" is never actually read from MC. Therefore this also throws
              "start" away. In fact is may happen that the MC is initializing in paralel with the libHardware (resets)
              In such case the "start" can be read and libHardware will throw an exception. This is correct as
              working with uninitialized MC is not safe. Unfortunately we cannot wait for start/(future ready) as
              it may not come if the MC has initialized before we do so. Therefore we need to have a safe command
              that checks whenever the MC is ready.

        :return: Line read from simulated serial port
        """
        start_ns = monotonic_ns()

        while monotonic_ns() - start_ns < self.TIMEOUT_MS * 1000:
            # Unfortunately, there is no way how to make readline not block
            try:
                line = self.process.stdout.readline()
            except ValueError:
                break
            if line:
                self.logger.debug("> %s", line)
                return line
            sleep(0.001)
        raise SerialTimeoutException("Nothing to read from serial port")

    def inWaiting(self):
        raise NotImplementedError()

    def readline(self):
        raise NotImplementedError()
