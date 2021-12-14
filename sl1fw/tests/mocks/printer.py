# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from PySignal import Signal

from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.states.printer import PrinterState
from sl1fw.tests.mocks.hardware import Hardware
from sl1fw.tests.mocks.network import Network
from sl1fw.tests.mocks.action_manager import ActionManager


class Printer:
    # pylint: disable = too-many-instance-attributes
    def __init__(self, exposure):
        self.state_changed = Signal()
        self.http_digest_changed = Signal()
        self.api_key_changed = Signal()
        self.data_privacy_changed = Signal()
        self.exception_changed = Signal()
        self.hw = Hardware()
        self.action_manager = ActionManager(exposure)
        self.runtime_config = RuntimeConfig()
        self.unboxed_changed = Signal()
        self.self_tested_changed = Signal()
        self.mechanically_calibrated_changed = Signal()
        self.uv_calibrated_changed = Signal()
        self.inet = Network()

        self.state = PrinterState.PRINTING
        self.exception = None

        self.http_digest = True
        self.api_key = "developer"
        self.data_privacy = "data privacy"
        self.help_page_url = "hpu"
        self.unboxed = True
        self.self_tested = True
        self.uv_calibrated = True
        self.mechanically_calibrated = True

    def remove_oneclick_inhibitor(self, _):
        pass

    def set_state(self, state):
        self.state = state
        self.state_changed.emit()
