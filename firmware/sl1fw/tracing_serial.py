# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from collections import deque
from enum import Enum
import serial


class MotionControllerTracingSerial(serial.Serial):
    """
    This is an extension of Serial that supports logging of traces and reading of decode text lines.
    """

    TRACE_LINES = 30

    class LineMarker(Enum):
        INPUT = ">"
        GARBAGE = "|"
        OUTPUT = "<"
        RESET = "="

    class LineTrace:
        def __init__(self, marker, line: bytes):
            self._line = line
            self._marker = marker
            self._repeats = 1

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return False
            else:
                return self._line == other._line and self._marker == other._marker

        def repeat(self):
            self._repeats += 1

        def __str__(self):
            if self._repeats > 1:
                return f"{self._repeats}x {self._marker.value} {self._line}"
            else:
                return f"{self._marker.value} {self._line}"

    def __init__(self, *args, **kwargs):
        self.__trace = deque(maxlen=self.TRACE_LINES)
        self.__debug = kwargs["debug"]
        del kwargs["debug"]
        super().__init__(*args, **kwargs)

    def __append_trace(self, current_trace):
        # < b'?mot\n' -3
        # > b'1 ok\n' -2
        # < b'?mot\n' -1
        # > b'1 ok\n' current_trace

        if len(self.__trace) > 3 and self.__trace[-3] == self.__trace[-1] and self.__trace[-2] == current_trace:
            self.__trace[-3].repeat()
            self.__trace[-2].repeat()
            del self.__trace[-1]
        else:
            self.__trace.append(current_trace)

    def readline(self, garbage=False) -> bytes:
        """
        Read raw line from motion controller
        :param garbage: Whenever to mark line read as garbage in command trace
        :return: Line read as raw bytes
        """
        marker = self.LineMarker.GARBAGE if garbage else self.LineMarker.INPUT
        ret = super().readline()
        trace = self.LineTrace(marker, ret)
        self.__append_trace(trace)
        self.__debug.log(str(trace))
        return ret

    def write(self, data: bytes) -> int:
        """
        Write data to a motion controller
        :param data: Data to be written
        :return: Number of bytes written
        """
        self.__append_trace(self.LineTrace(self.LineMarker.OUTPUT, data))
        self.__debug.log(f"< {data}")
        return super().write(data)

    def mark_reset(self):
        self.__append_trace(self.LineTrace(self.LineMarker.RESET, b"Motion controller reset"))

    @property
    def trace(self) -> str:
        """
        Get formated motion controller command trace
        :return: Trace string
        """
        return f"last {self.TRACE_LINES} lines:\n" + "\n".join([str(x) for x in self.__trace])

    def read_text_line(self, garbage=False) -> str:
        """
        Read line from serial as stripped decoded text
        :param garbage: Mark this data as garbage. LIne will be amrked as such in trace
        :return: Line read from motion controller
        """
        return self.readline(garbage=garbage).decode("ascii").strip()
