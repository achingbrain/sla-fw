# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction, AdminLabel, AdminBoolValue
from slafw.admin.menu import AdminMenu
from slafw.admin.safe_menu import SafeAdminMenu
from slafw.libPrinter import Printer
from slafw.states.wizard import WizardId
from slafw.wizard.wizard import SingleCheckWizard, WizardDataPackage
from slafw.wizard.wizards.calibration import CalibrationWizard
from slafw.wizard.wizards.displaytest import DisplayTestWizard
from slafw.wizard.wizards.factory_reset import PackingWizard, FactoryResetWizard
from slafw.wizard.wizards.new_expo_panel import NewExpoPanelWizard
from slafw.wizard.wizards.self_test import SelfTestWizard
from slafw.wizard.wizards.sl1s_upgrade import SL1SUpgradeWizard, SL1DowngradeWizard
from slafw.wizard.wizards.unboxing import CompleteUnboxingWizard, KitUnboxingWizard
from slafw.wizard.wizards.uv_calibration import UVCalibrationWizard
from slafw.wizard.wizards.tank_surface_cleaner import TankSurfaceCleaner
from slafw.wizard.checks.tilt import TiltTimingTest
from slafw.wizard.checks.uvfans import UVFansTest


class TestWizardsMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()

        self.add_items(
            (
                AdminAction("Display test", self.api_display_test),
                AdminAction("Unpacking (C)", self.api_unpacking_c),
                AdminAction("Unpacking (K)", self.api_unpacking_k),
                AdminAction("Self test", self.api_self_test),
                AdminAction("Calibration", self.api_calibration),
                AdminAction("Factory reset", self.api_factory_reset),
                AdminAction("Packing (Factory factory reset)", self.api_packing),
                AdminAction(
                    "API UV Calibration wizard",
                    lambda: self._control.enter(TestUVCalibrationWizardMenu(self._control, self._printer)),
                ),
                AdminAction("SL1S upgrade", self.sl1s_upgrade),
                AdminAction("SL1 downgrade", self.sl1_downgrade),
                AdminAction("Self-test - UV & fans test only", self.api_selftest_uvfans),
                AdminAction("Calibration - tilt times only", self.api_calibration_tilt_times),
                AdminAction("Tank Surface Cleaner", self.tank_surface_cleaner),
                AdminAction("New expo panel", self.new_expo_panel)
            )
        )

    def api_display_test(self):
        self._printer.action_manager.start_wizard(
            DisplayTestWizard(self._printer.hw, self._printer.exposure_image, self._printer.runtime_config)
        )

    def api_unpacking_c(self):
        self._printer.action_manager.start_wizard(
            CompleteUnboxingWizard(self._printer.hw, self._printer.runtime_config)
        )

    def api_unpacking_k(self):
        self._printer.action_manager.start_wizard(KitUnboxingWizard(self._printer.hw, self._printer.runtime_config))

    def api_self_test(self):
        self._printer.action_manager.start_wizard(
            SelfTestWizard(self._printer.hw, self._printer.exposure_image, self._printer.runtime_config)
        )

    def api_calibration(self):
        self._printer.action_manager.start_wizard(CalibrationWizard(self._printer.hw, self._printer.runtime_config))

    def api_packing(self):
        self._printer.action_manager.start_wizard(PackingWizard(self._printer.hw, self._printer.runtime_config))

    def api_factory_reset(self):
        self._printer.action_manager.start_wizard(FactoryResetWizard(self._printer.hw, self._printer.runtime_config))

    def sl1s_upgrade(self):
        self._printer.action_manager.start_wizard(
            SL1SUpgradeWizard(self._printer.hw, self._printer.exposure_image, self._printer.runtime_config)
        )

    def sl1_downgrade(self):
        self._printer.action_manager.start_wizard(
            SL1DowngradeWizard(self._printer.hw, self._printer.exposure_image, self._printer.runtime_config)
        )

    def api_selftest_uvfans(self):
        package = WizardDataPackage(
            self._printer.hw, self._printer.hw.config.get_writer(), self._printer.runtime_config
        )
        self._printer.action_manager.start_wizard(SingleCheckWizard(
            WizardId.SELF_TEST,
            UVFansTest(package.hw),
            package,
            show_results=False))

    def api_calibration_tilt_times(self):
        package = WizardDataPackage(
            self._printer.hw, self._printer.hw.config.get_writer(), self._printer.runtime_config
        )
        self._printer.action_manager.start_wizard(SingleCheckWizard(
            WizardId.CALIBRATION,
            TiltTimingTest(package.hw, package.config_writer),
            package))

    def tank_surface_cleaner(self):
        self._printer.action_manager.start_wizard(
            TankSurfaceCleaner(self._printer.hw, self._printer.exposure_image, self._printer.runtime_config)
        )

    def new_expo_panel(self):
        self._printer.action_manager.start_wizard(
            NewExpoPanelWizard(self._printer.hw)
        )


class TestUVCalibrationWizardMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._lcd_replaced = False
        self._led_replaced = False
        self._printer = printer

        self.add_back()
        self.add_item(AdminLabel("UV Calibration wizard setup"))
        self.add_item(AdminBoolValue.from_value("LCD replaced", self, "_lcd_replaced"))
        self.add_item(AdminBoolValue.from_value("LED replaced", self, "_led_replaced"))
        self.add_item(AdminAction("Run calibration", self.run_calibration))

    def run_calibration(self):
        self._control.pop()

        self._printer.action_manager.start_wizard(
            UVCalibrationWizard(
                self._printer.hw,
                self._printer.exposure_image,
                self._printer.runtime_config,
                display_replaced=self._lcd_replaced,
                led_module_replaced=self._led_replaced,
            )
        )
