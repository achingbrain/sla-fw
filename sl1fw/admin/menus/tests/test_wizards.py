# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction, AdminLabel, AdminBoolValue
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.safe_menu import SafeAdminMenu
from sl1fw.libPrinter import Printer
from sl1fw.states.wizard import WizardId
from sl1fw.wizard.wizard import Wizard, WizardDataPackage
from sl1fw.wizard.wizards.generic import ShowResultsGroup
from sl1fw.wizard.wizards.calibration import CalibrationWizard, CalibrationFinishCheckGroup
from sl1fw.wizard.wizards.displaytest import DisplayTestWizard
from sl1fw.wizard.wizards.factory_reset import PackingWizard, FactoryResetWizard
from sl1fw.wizard.wizards.self_test import SelfTestWizard
from sl1fw.wizard.wizards.sl1s_upgrade import SL1SUpgradeWizard, SL1DowngradeWizard
from sl1fw.wizard.wizards.unboxing import CompleteUnboxingWizard, KitUnboxingWizard
from sl1fw.wizard.wizards.uv_calibration import UVCalibrationWizard


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
                AdminAction("Calibration - tilt times only", self.api_calibration_tilt_times),
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

    def api_calibration_tilt_times(self):
        package = WizardDataPackage(
            self._printer.hw, self._printer.hw.config.get_writer(), self._printer.runtime_config
        )

        class CalibrationTiltTimesOnlyWizard(Wizard):
            def __init__(self):
                super().__init__(
                    WizardId.CALIBRATION,
                    [
                        CalibrationFinishCheckGroup(package),
                        ShowResultsGroup(),
                    ],
                    package,
                )

        self._printer.action_manager.start_wizard(CalibrationTiltTimesOnlyWizard())


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
