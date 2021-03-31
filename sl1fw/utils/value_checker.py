# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Callable

from PySignal import Signal


class ValueChecker:
    """
    Utility class for checking values for change
    """

    def __init__(self, getter: Callable, signal: Signal, pass_value: bool = True):
        self._getter = getter
        self._signal = signal
        self._pass_value = pass_value
        self._last_value = None

    def check(self):
        new_value = self._getter()
        if self._last_value != new_value:
            self._last_value = new_value
            self.emit(new_value)

    def emit(self, value):
        if self._signal is not None:
            if self._pass_value:
                self._signal.emit(value)
            else:
                self._signal.emit()
