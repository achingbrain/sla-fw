# This file is part of the SLA firmware
# Copyright (C) 2021-2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from datetime import timedelta, datetime
from itertools import chain
from threading import Thread
from dataclasses import asdict
from functools import partial
from pathlib import Path
from glob import iglob

from slafw import defines
from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction, AdminBoolValue, AdminIntValue, AdminLabel
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.dialogs import Info, Confirm, Wait, Error
from slafw.admin.safe_menu import SafeAdminMenu
from slafw.errors.errors import DisplayTransmittanceNotValid, CalculatedUVPWMNotInRange
from slafw.functions.system import compute_uvpwm
from slafw.functions import files, generate
from slafw.libPrinter import Printer
from slafw.hardware.sl1.tilt import TiltProfile
from slafw.libUvLedMeterMulti import UvLedMeterMulti
from slafw.hardware.power_led_action import WarningAction
from slafw.image import cairo

class ExposureDisplayMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_items(
            (
                AdminAction(
                    "Exposure display service",
                    lambda: self._control.enter(DisplayServiceMenu(self._control, self._printer))
                ),
                AdminAction(
                    "Exposure display control",
                    lambda: self._control.enter(DisplayControlMenu(self._control, self._printer))
                ),
                AdminAction("Direct UV PWM settings", self.enter_direct_uvpwm),
            )
        )

    def enter_direct_uvpwm(self):
        self._control.enter(
            Confirm(
                self._control,
                self._do_enter_direct_uvpwm,
                headline="Do you really want to enter the menu?",
                text="It will turn on the UV LED, open the exposure display\n"
                "and move the tilt. Do not enter during active print job.",
            )
        )

    def _do_enter_direct_uvpwm(self):
        self._control.enter(DirectPwmSetMenu(self._control, self._printer))


class DisplayServiceMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_items(
            (
                AdminAction("Erase UV LED counter", self.erase_uv_led_counter),
                AdminAction("Erase display counter", self.erase_display_counter),
                AdminAction(
                    "Show UV calibration data",
                    lambda: self._control.enter(ShowCalibrationMenu(self._control))
                ),
                AdminAction("Display usage heatmap", self.display_usage_heatmap),
            )
        )

    @SafeAdminMenu.safe_call
    def erase_uv_led_counter(self):
        self.logger.info("About to erase UV LED statistics")
        self.logger.info("Current statistics UV LED usage seconds %s", self._printer.hw.uv_led.usage_s)
        self._control.enter(
            Confirm(
                self._control,
                self._do_erase_uv_led_counter,
                headline="Do you really want to clear the UV LED counter?",
                text=f"UV counter: {timedelta(seconds=self._printer.hw.uv_led.usage_s)}\n"
                f"Serial number: {self._printer.hw.cpuSerialNo}\n"
                f"IP address: {self._printer.inet.ip}",
            )
        )

    def _do_erase_uv_led_counter(self):
        self._printer.hw.uv_led.clear_usage()
        self._control.enter(
            Info(
                self._control,
                headline="UV counter has been erased.",
                text=f"UV counter: {timedelta(seconds=self._printer.hw.uv_led.usage_s)}\n"
                f"Serial number: {self._printer.hw.cpuSerialNo}\n"
                f"IP address: {self._printer.inet.ip}",
            )
        )

    @SafeAdminMenu.safe_call
    def erase_display_counter(self):
        self.logger.info("About to erase display statistics")
        self.logger.info("Current UV LED usage %d seconds", self._printer.hw.uv_led.usage_s)
        self.logger.info("Current display usage %d seconds", self._printer.hw.display.usage_s)

        self._control.enter(
            Confirm(
                self._control,
                self._do_erase_display_counter,
                headline="Do you really want to clear the Display counter?",
                text=f"Display counter: {timedelta(seconds=self._printer.hw.display.usage_s)}\n"
                f"Serial number: {self._printer.hw.cpuSerialNo}\n"
                f"IP address: {self._printer.inet.ip}",
            )
        )

    def _do_erase_display_counter(self):
        self._printer.hw.display.clear_usage()
        self._control.enter(
            Info(
                self._control,
                headline="Display counter has been erased.",
                text=f"Display counter: {timedelta(seconds=self._printer.hw.display.usage_s)}\n"
                f"Serial number: {self._printer.hw.cpuSerialNo}\n"
                f"IP address: {self._printer.inet.ip}",
            )
        )

    @SafeAdminMenu.safe_call
    def display_usage_heatmap(self):
        generate.display_usage_heatmap(
                self._printer.hw.exposure_screen.parameters,
                defines.displayUsageData,
                defines.displayUsagePalette,
                defines.fullscreenImage)
        self._control.fullscreen_image()


class ShowCalibrationMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl):
        super().__init__(control)

        self.add_back()
        data_paths = (
                defines.wizardHistoryPathFactory.glob("uvcalib_data.*"),
                defines.wizardHistoryPathFactory.glob("uvcalibrationwizard_data.*"),
                defines.wizardHistoryPathFactory.glob("uv_calibration_data.*"),
                defines.wizardHistoryPathFactory.glob(f"{defines.manual_uvc_filename}.*"),
                defines.wizardHistoryPath.glob("uvcalib_data.*"),
                defines.wizardHistoryPath.glob("uvcalibrationwizard_data.*"),
                defines.wizardHistoryPath.glob("uv_calibration_data.*"),
                )
        filenames = sorted(list(chain(*data_paths)), key=lambda path: path.stat().st_mtime, reverse=True)
        if filenames:
            for fn in filenames:
                prefix = "F:" if fn.parent == defines.wizardHistoryPathFactory else "U:"
                self.add_item(AdminAction(prefix + fn.name, partial(self.show_calibration, fn)))
        else:
            self.add_label("(no data)")

    @SafeAdminMenu.safe_call
    def show_calibration(self, filename):
        generate.uv_calibration_result(None, filename, defines.fullscreenImage)
        self._control.fullscreen_image()


class DisplayControlMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_items(
            (
                AdminBoolValue("UV", self.get_uv, self.set_uv),
                AdminAction("Open screen", self.open),
                AdminAction("Close screen", self.close),
                AdminAction("Inverse", self.invert),
                AdminAction("Chess 8", self.chess_8),
                AdminAction("Chess 16", self.chess_16),
                AdminAction("Grid 8", self.grid_8),
                AdminAction("Grid 16", self.grid_16),
                AdminAction("Gradient vertical", self.gradient_vertical),
                AdminAction("Gradient horizontal", self.gradient_horizontal),
                AdminAction("Prusa logo", self.prusa_logo),
                AdminAction(
                    "file from USB",
                    lambda: self._control.enter(UsbFileMenu(self._control, self._printer))
                ),
            )
        )

    def on_leave(self):
        self._printer.hw.uv_led.save_usage()

    def get_uv(self):
        return self._printer.hw.uv_led.active

    def set_uv(self, enabled: bool):
        if enabled:
            self._printer.hw.start_fans()
            self._printer.hw.uv_led.pwm = self._printer.hw.config.uvPwmPrint  # use final UV PWM, due to possible test
            self._printer.hw.uv_led.on()
        else:
            self._printer.hw.stop_fans()
            self._printer.hw.uv_led.off()

    @SafeAdminMenu.safe_call
    def open(self):
        self._printer.exposure_image.open_screen()

    @SafeAdminMenu.safe_call
    def close(self):
        self._printer.exposure_image.blank_screen()

    @SafeAdminMenu.safe_call
    def invert(self):
        self._printer.hw.exposure_screen.draw_pattern(cairo.inverse)

    @SafeAdminMenu.safe_call
    def chess_8(self):
        self._printer.hw.exposure_screen.draw_pattern(cairo.draw_chess, 8)

    @SafeAdminMenu.safe_call
    def chess_16(self):
        self._printer.hw.exposure_screen.draw_pattern(cairo.draw_chess, 16)

    @SafeAdminMenu.safe_call
    def grid_8(self):
        self._printer.hw.exposure_screen.draw_pattern(cairo.draw_grid, 7, 1)

    @SafeAdminMenu.safe_call
    def grid_16(self):
        self._printer.hw.exposure_screen.draw_pattern(cairo.draw_grid, 14, 2)

    @SafeAdminMenu.safe_call
    def gradient_horizontal(self):
        self._printer.hw.exposure_screen.draw_pattern(cairo.draw_gradient, False)

    @SafeAdminMenu.safe_call
    def gradient_vertical(self):
        self._printer.hw.exposure_screen.draw_pattern(cairo.draw_gradient, True)

    @SafeAdminMenu.safe_call
    def prusa_logo(self):
        self._printer.hw.exposure_screen.draw_pattern(cairo.draw_svg_expand, defines.prusa_logo_file, True)


class UsbFileMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer
        self.add_back()
        usb_path = files.get_save_path()
        if usb_path is None:
            self.add_label("USB not present. To get files from USB, plug the USB and re-enter.")
        else:
            self._list_files(usb_path, "png")
            self._list_files(usb_path, "svg")

    def _list_files(self, path: Path, suffix: str):
#        all_files = iglob("**/*." + suffix, root_dir=path, recursive=True) # TODO python 3.10
        all_files = iglob(str(path / "**/*.") + suffix, recursive=True)
        cut_off = len(str(path))+1
        for file in all_files:
            self.add_item(AdminAction(
                file[cut_off:],
                partial(self._usb_test, path, file)
            ))

    @SafeAdminMenu.safe_call
    def _usb_test(self, path: Path, name: str):
        fullname = path / name
        if not fullname.exists():
            raise FileNotFoundError(f"Test image not found: {name}")
        if fullname.suffix == ".svg":
            es = self._printer.hw.exposure_screen
            es.draw_pattern(cairo.draw_svg_dpi, str(fullname), False, es.parameters.dpi)
        else:
            self._printer.exposure_image.show_image_with_path(str(fullname))


class DirectPwmSetMenu(SafeAdminMenu):
    # pylint: disable=too-many-instance-attributes
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer
        self._temp = self._printer.hw.config.get_writer()
        self._run = True
        self._status = "<h3>UV meter disconnected<h3>"
        self._data = None
        self._uv_pwm_print = self._temp.uvPwmPrint

        self.add_back()
        uv_pwm_item = AdminIntValue.from_value("UV LED PWM", self._temp, "uvPwm", 1)
        uv_pwm_item.changed.connect(self._uv_pwm_changed)
        uv_pwm_tune_item = AdminIntValue.from_value("UV LED PWM fine tune", self._temp, "uvPwmTune", 1)
        uv_pwm_tune_item.changed.connect(self._uv_pwm_changed)
        self.uv_pwm_print_item = AdminLabel.from_property(self, DirectPwmSetMenu.uv_pwm_print)
        self.add_items(
            (
                AdminBoolValue.from_value("UV LED", self, "uv_led"),
                AdminAction("Open screen", self.open),
                AdminAction("Close screen", self.close),
                AdminAction("Calculate PWM from display transmittance", self.calculate_pwm),
                self.uv_pwm_print_item,
                uv_pwm_item,
                uv_pwm_tune_item,
                AdminLabel.from_property(self, DirectPwmSetMenu.status),
                AdminAction("Show measured data", partial(self.show_calibration)),
            )
        )
        self._thread = Thread(target=self._measure)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value: str):
        self._status = value

    def on_enter(self):
        self._thread.start()
        self.enter(Wait(self._control, self._do_prepare))

    def on_leave(self):
        self._run = False
        self._printer.hw_all_off()
        self._printer.hw.uv_led.save_usage()
        self._temp.commit()
        if self._data:
            file_path = defines.wizardHistoryPathFactory / f"{defines.manual_uvc_filename}.{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
            with file_path.open("w") as file:
                json.dump(asdict(self._data), file, indent=2, sort_keys=True)
        self._thread.join()

    def _measure(self):
        meter = UvLedMeterMulti()
        connected = False
        while self._run:
            if connected:
                if meter.read():
                    self._data = meter.get_data(plain_mean=True)
                    self._data.uvFoundPwm = self._uv_pwm_print
                    self.status = "<h3>ø:%.1f σ:%.1f %.1f°C<h3>" % (
                        self._data.uvMean,
                        self._data.uvStdDev,
                        self._data.uvTemperature,
                    )
                else:
                    self.status = "<h3>UV meter disconnected<h3>"
                    connected = False
            elif meter.connect():
                self.status = "<h3>UV meter connected<h3>"
                connected = True
        meter.close()

    @SafeAdminMenu.safe_call
    def show_calibration(self):
        generate.uv_calibration_result(asdict(self._data) if self._data else None, None, defines.fullscreenImage)
        self._control.fullscreen_image()

    @SafeAdminMenu.safe_call
    def _do_prepare(self, status: AdminLabel):
        with WarningAction(self._printer.hw.power_led):
            status.set("<h3>Tilt is going to level<h3>")
            self._printer.hw.tilt.profile_id = TiltProfile.homingFast
            self._printer.hw.tilt.sync_ensure()
            self._printer.hw.tilt.profile_id = TiltProfile.moveFast
            self._printer.hw.tilt.move_ensure(self._printer.hw.config.tiltHeight)  # move to level

        status.set("<h3>Tilt leveled<h3>")
        self._printer.hw.start_fans()
        self._printer.hw.uv_led.pwm = self._uv_pwm_print
        self._printer.hw.uv_led.on()
        self._printer.exposure_image.open_screen()

    @property
    def uv_led(self) -> bool:
        return self._printer.hw.uv_led.active

    @uv_led.setter
    def uv_led(self, value: bool):
        if value:
            self._printer.hw.start_fans()
            self._printer.hw.uv_led.pwm = self._uv_pwm_print
            self._printer.hw.uv_led.on()
        else:
            self._printer.hw.stop_fans()
            self._printer.hw.uv_led.off()

    @property
    def uv_pwm_print(self) -> str:
        return "<h3>Final UV PWM value: " + str(self._uv_pwm_print) + "</h3>"

    @uv_pwm_print.setter
    def uv_pwm_print(self, value):
        self._uv_pwm_print = value

    @SafeAdminMenu.safe_call
    def open(self):
        self._printer.exposure_image.open_screen()

    @SafeAdminMenu.safe_call
    def close(self):
        self._printer.exposure_image.blank_screen()

    def _uv_pwm_changed(self):
        # TODO: simplify work with config and config writer
        self.uv_pwm_print_item.set_value(self._temp.uvPwm + self._temp.uvPwmTune)
        self._printer.hw.uv_led.pwm = self._uv_pwm_print

    def calculate_pwm(self):
        try:
            pwm = compute_uvpwm(self._printer.hw)
        except DisplayTransmittanceNotValid as exception:
            self._control.enter(
                Error(self._control, text=f"Display transmittance {exception.transmittance} is not valid", pop=1)
            )
            return
        except CalculatedUVPWMNotInRange as e:
            self._control.enter(
                Error(self._control, text=f"Calculated value {e.pwm} is not in range <{e.pwm_min},{e.pwm_max}>", pop=1)
            )
            return

        self._temp.uvPwm = pwm
        self._uv_pwm_changed()
        self._control.enter(Info(self._control, f"Calculated PWM is {pwm}"))
