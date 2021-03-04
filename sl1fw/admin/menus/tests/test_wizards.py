# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.functions.wizards import (
    displaytest_wizard,
    unboxing_wizard,
    kit_unboxing_wizard,
    self_test_wizard,
    calibration_wizard,
    packing_wizard,
    factory_reset_wizard,
)
from sl1fw.libPrinter import Printer


class TestWizardsMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_item(AdminAction("back", self._control.pop))

        self.add_item(AdminAction("Self test", self.self_test))
        self.add_item(AdminAction("Calibration", self.calibration))
        self.add_item(AdminAction("API Display test", self.api_display_test))
        self.add_item(AdminAction("API Unpacking (C)", self.api_unpacking_c))
        self.add_item(AdminAction("API Unpacking (K)", self.api_unpacking_k))
        self.add_item(AdminAction("API Self test", self.api_wizard))
        self.add_item(AdminAction("API Calibration", self.api_calibration))
        self.add_item(AdminAction("API Factory reset", self.api_factory_reset))
        self.add_item(
            AdminAction("API Packing (Factory factory reset)", self.api_packing)
        )

    def self_test(self):
        self._printer.display.doMenu("wizardinit")
        return "_SELF_"

    def calibration(self):
        self._printer.display.doMenu("calibrationstart")
        return "_SELF_"

    def api_display_test(self):
        displaytest_wizard(
            self._printer.display.action_manager,
            self._printer.display.hw,
            self._printer.display.exposure_image,
            self._printer.display.runtime_config,
        )

    def api_unpacking_c(self):
        unboxing_wizard(
            self._printer.action_manager,
            self._printer.hw,
            self._printer.hwConfig,
            self._printer.runtime_config,
        )

    def api_unpacking_k(self):
        kit_unboxing_wizard(
            self._printer.action_manager,
            self._printer.hw,
            self._printer.hwConfig,
            self._printer.runtime_config,
        )

    def api_wizard(self):
        self_test_wizard(
            self._printer.action_manager,
            self._printer.hw,
            self._printer.hwConfig,
            self._printer.exposure_image,
            self._printer.runtime_config,
        )

    def api_calibration(self):
        calibration_wizard(
            self._printer.action_manager,
            self._printer.hw,
            self._printer.hwConfig,
            self._printer.runtime_config,
        )

    def api_packing(self):
        packing_wizard(
            self._printer.action_manager,
            self._printer.hw,
            self._printer.hwConfig,
            self._printer.runtime_config,
        )

    def api_factory_reset(self):
        factory_reset_wizard(
            self._printer.action_manager,
            self._printer.hw,
            self._printer.hwConfig,
            self._printer.runtime_config,
        )
