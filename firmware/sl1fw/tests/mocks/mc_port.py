# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from subprocess import Popen, PIPE
from time import sleep
from typing import Optional

from serial import SerialTimeoutException


class Serial:
    TIMEOUT_MS = 3000

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # MC simulator process
        self.process: Optional[Popen] = None

    def open(self):
        self.process = Popen(["SLA-control-01.elf"], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        ready = self.process.stdout.readline()
        self.logger.debug("MC serial simulator ready = %s", ready)
        assert ready == b'ready\n'

    @property
    def is_open(self) -> bool:
        return not self.process.returncode

    def close(self):
        """
        Stop MS Port simulator
        Terminate simulator and output reading thread

        :return: None
        """
        self.process.terminate()
        self.process.wait(timeout=3)

        self.process.stdin.close()
        self.process.stdout.close()
        self.process.stderr.close()

    def write(self, data):
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
        for _ in range(self.TIMEOUT_MS):
            line = self.process.stdout.readline()
            if line:
                self.logger.debug("> %s", line)
                return line
            sleep(0.001)

        raise SerialTimeoutException("Nothing to read from serial port")
