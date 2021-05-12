# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminIntValue, AdminBoolValue, AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Confirm, Error, Info
from sl1fw.errors.exceptions import ConfigException
from sl1fw.functions.system import FactoryMountedRW
from sl1fw.libPrinter import Printer
from sl1fw.hardware.printer_model import PrinterModel


class FansAndUVLedMenu(AdminMenu):
    # pylint: disable=too-many-instance-attributes

    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer
        self._temp = self._printer.hw.config.get_writer()
        self._init_fans = self._printer.hw.getFans()
        self._override_fans = self._printer.hw.getFans()
        uv_led_state = self._printer.hw.getUvLedState()
        self._init_uv_led = uv_led_state[0] and uv_led_state[1] == 0

        self.add_back()
        self.add_item(AdminBoolValue.from_value("UV LED fan", self, "uv_led_fan"))
        uv_led_fan_rpm_item = AdminIntValue.from_value("UV LED fan RPM", self._temp, "fan1Rpm", 100)
        uv_led_fan_rpm_item.changed.connect(self._uv_led_fan_changed)
        self.add_item(uv_led_fan_rpm_item)
        self.add_item(AdminBoolValue.from_value("Blower fan", self, "blower_fan"))
        blower_fan_rpm_item = AdminIntValue.from_value("Blower fan RPM", self._temp, "fan2Rpm", 100)
        blower_fan_rpm_item.changed.connect(self._blower_fan_changed)
        self.add_item(blower_fan_rpm_item)
        rear_fan_rpm_item = AdminBoolValue.from_value("Rear fan", self, "rear_fan")
        rear_fan_rpm_item.changed.connect(self._rear_fan_changed)
        self.add_item(rear_fan_rpm_item)
        self.add_item(AdminIntValue.from_value("Rear fan RPM", self._temp, "fan3Rpm", 100))
        self.add_item(AdminBoolValue.from_value("UV LED", self, "uv_led"))
        self.add_item(AdminIntValue.from_value("UV LED PWM", self._temp, "uvPwm", 1))
        self.add_item(AdminIntValue.from_value("UV calib. warm-up [s]", self._temp, "uvWarmUpTime", 1))
        self.add_item(AdminIntValue.from_value("UV calib. intensity", self._temp, "uvCalibIntensity", 1))
        self.add_item(AdminIntValue.from_value("UV cal. min. int. edge", self._temp, "uvCalibMinIntEdge", 1))
        self.add_item(AdminAction("Save", self.save))
        self.add_item(AdminAction("Reset to defaults", self.reset_to_defaults))
        self.add_item(AdminAction("Save & save as defaults", self.save_as_defaults))
        self.add_item(AdminAction("Save to boostV2 board", self.save_to_booster))

    def on_leave(self):
        self._printer.hw.setFans(self._init_fans)
        self._printer.hw.uvLed(self._init_uv_led)

    @property
    def uv_led_fan(self) -> bool:
        return self._printer.hw.getFans()[0]

    @uv_led_fan.setter
    def uv_led_fan(self, value: bool):
        self._override_fans[0] = value
        self._printer.hw.setFans(self._override_fans)
        self._printer.runtime_config.fan_error_override = False

    @property
    def blower_fan(self) -> bool:
        return self._printer.hw.getFans()[1]

    @blower_fan.setter
    def blower_fan(self, value: bool):
        self._override_fans[1] = value
        self._printer.hw.setFans(self._override_fans)
        self._printer.runtime_config.fan_error_override = False

    @property
    def rear_fan(self) -> bool:
        return self._printer.hw.getFans()[2]

    @rear_fan.setter
    def rear_fan(self, value: bool):
        self._override_fans[2] = value
        self._printer.hw.setFans(self._override_fans)
        self._printer.runtime_config.fan_error_override = False

    @property
    def uv_led(self) -> bool:
        uv_led_state = self._printer.hw.getUvLedState()
        return uv_led_state[0]

    @uv_led.setter
    def uv_led(self, value: bool):
        if value:
            self._printer.hw.startFans()
            self._printer.hw.uvLedPwm = self._temp.uvPwm
        else:
            self._printer.hw.stopFans()
        self._printer.hw.uvLed(value)

    def save(self):
        self._printer.hw.saveUvStatistics()
        self._temp.commit(write=True)
        self._control.enter(Info(self._control, "Configuration saved"))

    def reset_to_defaults(self):
        self._control.enter(Confirm(self._control, self._do_reset_to_defaults, text="Reset to factory defaults?"))

    def _do_reset_to_defaults(self) -> None:
        self.logger.info("Fans&LEDs - Resetting to defaults")
        del self._printer.hw.config.uvCurrent  # remove old value too
        del self._printer.hw.config.uvPwm
        del self._printer.hw.config.fan1Rpm
        del self._printer.hw.config.fan2Rpm
        del self._printer.hw.config.fan3Rpm
        self._printer.hw.setFans(
            {0: self._printer.hw.config.fan1Rpm, 1: self._printer.hw.config.fan2Rpm, 2: self._printer.hw.config.fan3Rpm}
        )
        self._printer.hw.uvLedPwm = self._printer.hw.config.uvPwm
        self._temp.reset()
        try:
            self._printer.hw.config.write()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self._control.enter(Error(self._control, text="Cannot save configuration", pop=1))
            return
        self._control.enter(Info(self._control, "Configuration reset to defaults"))

    def save_as_defaults(self):
        self._control.enter(
            Confirm(self._control, self._do_save_as_defaults, text="Save current values as factory defaults?")
        )

    def _do_save_as_defaults(self):
        self.logger.info("Fans&LEDs - Saving factory defaults")
        self._temp.commit()
        self._printer.hw.config.write()

        try:
            with FactoryMountedRW():
                self._printer.hw.config.write_factory()
        except ConfigException:
            self._control.enter(Error(self._control, text="!!! Failed to save factory defaults !!!", pop=1))
            return
        self._control.enter(Info(self._control, "Configuration saved as default"))

    def save_to_booster(self):
        if self._printer.hw.printer_model == PrinterModel.SL1S:
            self._control.enter(
                Confirm(self._control, self._do_save_to_booster, text="Save current PWM to boosterV2 board?")
            )
        else:
            self._control.enter(Error(self._control, text="Works only on SL1S!", pop=1))

    def _do_save_to_booster(self):
        try:
            self._printer.hw.uvLedPwm = self._temp.uvPwm
            self._printer.hw.sl1s_booster.save_permanently()
        except Exception:
            self._control.enter(Error(self._control, text="!!! Failed to save PWM to boosterV2 board !!!", pop=1))

    def _uv_led_fan_changed(self):
        self.uv_led_fan = True
        self._printer.hw.fans[0].targetRpm = self._temp.fan1Rpm

    def _blower_fan_changed(self):
        self.blower_fan = True
        self._printer.hw.fans[1].targetRpm = self._temp.fan2Rpm

    def _rear_fan_changed(self):
        self.rear_fan = True
        self._printer.hw.fans[2].targetRpm = self._temp.fan3Rpm
