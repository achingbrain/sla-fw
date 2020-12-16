# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import timedelta

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction, AdminBoolValue
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Info, Confirm
from sl1fw.admin.safe_menu import SafeAdminMenu
from sl1fw.functions import files
from sl1fw.functions.system import hw_all_off
from sl1fw.libPrinter import Printer
from sl1fw.pages.uvcalibration import PageUvCalibration, PageUvDataShowFactory, PageUvDataShow


class DisplayRootMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_item(
            AdminAction(
                "Display service", lambda: self._control.enter(DisplayServiceMenu(self._control, self._printer))
            )
        )
        self.add_item(
            AdminAction(
                "Display control", lambda: self._control.enter(DisplayControlMenu(self._control, self._printer))
            )
        )


class DisplayServiceMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_item(AdminAction("Erase UV LED counter", self.erase_uv_led_counter))
        self.add_item(AdminAction("Erase Display counter", self.erase_display_counter))
        self.add_item(AdminAction("Show factory UV calibration data", self.show_factory_calibration))
        self.add_item(AdminAction("Show UV calibration data", self.show_calibration))
        self.add_item(AdminAction("UV (re)calibration", self.recalibrate))

    @SafeAdminMenu.safe_call
    def erase_uv_led_counter(self):
        self.logger.info("About to erase UV LED statistics")
        self.logger.info("Current statistics %s", self._printer.hw.getUvStatistics())
        self._control.enter(
            Confirm(
                self._control,
                self._do_erase_uv_led_counter,
                text=f"Do you really want to clear the UV LED counter?\n\n"
                f"UV counter: {timedelta(seconds=self._printer.hw.getUvStatistics()[0])}\n"
                f"Serial number: {self._printer.hw.cpuSerialNo}\n"
                f"IP address: {self._printer.inet.ip}",
            )
        )

    def _do_erase_uv_led_counter(self):
        self._printer.hw.clearUvStatistics()
        self._control.enter(
            Info(
                self._control,
                text="UV counter has been erased.\n\n"
                f"UV counter: {timedelta(seconds=self._printer.hw.getUvStatistics()[0])}\n"
                f"Serial number: {self._printer.hw.cpuSerialNo}\n"
                f"IP address: {self._printer.inet.ip}",
            )
        )

    @SafeAdminMenu.safe_call
    def erase_display_counter(self):
        self.logger.info("About to erase display statistics")
        self.logger.info("Current statistics %s", self._printer.hw.getUvStatistics())

        self._control.enter(
            Confirm(
                self._control,
                self._do_erase_display_counter,
                text=f"Do you really want to clear the Display counter?\n\n"
                f"Display counter: {timedelta(seconds=self._printer.hw.getUvStatistics()[1])}\n"
                f"Serial number: {self._printer.hw.cpuSerialNo}\n"
                f"IP address: {self._printer.inet.ip}",
            )
        )

    def _do_erase_display_counter(self):
        self._printer.hw.clearDisplayStatistics()
        self._control.enter(
            Info(
                self._control,
                text="Display counter has been erased.\n\n"
                f"Display counter: {timedelta(seconds=self._printer.hw.getUvStatistics()[1])}\n"
                f"Serial number: {self._printer.hw.cpuSerialNo}\n"
                f"IP address: {self._printer.inet.ip}",
            )
        )

    @SafeAdminMenu.safe_call
    def show_factory_calibration(self):
        self._printer.hw.saveUvStatistics()
        self._printer.display.forcePage(PageUvDataShowFactory.Name)

    @SafeAdminMenu.safe_call
    def show_calibration(self):
        self._printer.hw.saveUvStatistics()
        self._printer.display.forcePage(PageUvDataShow.Name)

    @SafeAdminMenu.safe_call
    def recalibrate(self):
        self._printer.hw.saveUvStatistics()
        self._printer.display.forcePage(PageUvCalibration.Name)


class DisplayControlMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()

        self.add_item(AdminBoolValue("UV", self.get_uv, self.set_uv))
        self.add_item(AdminAction("Chess 8", self.chess_8))
        self.add_item(AdminAction("Chess 16", self.chess_16))
        self.add_item(AdminAction("Grid 8", self.grid_8))
        self.add_item(AdminAction("Grid 16", self.grid_16))
        self.add_item(AdminAction("Maze", self.maze))
        self.add_item(AdminAction("USB:/test.png", self.usb_test))
        self.add_item(AdminAction("Prusa logo", self.prusa))
        self.add_item(AdminAction("Black", self.black))
        self.add_item(AdminAction("Inverse", self.invert))

    def on_leave(self):
        self._printer.hw.saveUvStatistics()
        hw_all_off(self._printer.hw, self._printer.screen)

    def get_uv(self):
        return self._printer.hw.getUvLedState()[0]

    def set_uv(self, enabled: bool):
        if enabled:
            self._printer.hw.startFans()
            self._printer.hw.uvLedPwm = self._printer.hwConfig.uvPwm
        else:
            self._printer.hw.stopFans()

        self._printer.hw.uvLed(enabled)

    @SafeAdminMenu.safe_call
    def chess_8(self):
        self._printer.screen.show_system_image("chess8.png")

    @SafeAdminMenu.safe_call
    def chess_16(self):
        self._printer.screen.show_system_image("chess16.png")

    @SafeAdminMenu.safe_call
    def grid_8(self):
        self._printer.screen.show_system_image("grid8.png")

    @SafeAdminMenu.safe_call
    def grid_16(self):
        self._printer.screen.show_system_image("grid16.png")

    @SafeAdminMenu.safe_call
    def maze(self):
        self._printer.screen.show_system_image("maze.png")

    @SafeAdminMenu.safe_call
    def usb_test(self):
        save_path = files.get_save_path()
        if save_path is None:
            raise ValueError("No USB path")
        test_file = save_path / "test.png"
        if not test_file.exists():
            raise FileNotFoundError(f"Test image not found: {test_file}")
        self._printer.screen.show_image_with_path(str(test_file))

    @SafeAdminMenu.safe_call
    def prusa(self):
        self._printer.screen.show_system_image("logo.png")

    @SafeAdminMenu.safe_call
    def black(self):
        self._printer.screen.blank_screen()

    @SafeAdminMenu.safe_call
    def invert(self):
        self._printer.screen.inverse()
