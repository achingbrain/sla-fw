# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.admin.control import AdminControl
from slafw.admin.items import AdminIntValue, AdminBoolValue, AdminAction
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.dialogs import Confirm, Error, Info
from slafw.errors.errors import ConfigException
from slafw.functions.system import FactoryMountedRW
from slafw.hardware.base.fan import FanState
from slafw.libPrinter import Printer


class FansAndUVLedMenu(AdminMenu):
    # pylint: disable=too-many-instance-attributes

    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer
        self._temp = self._printer.hw.config.get_writer()
        self._init_uv_led_fan = FanState(self._printer.hw.uv_led_fan)
        self._init_blower_fan = FanState(self._printer.hw.blower_fan)
        self._init_rear_fan = FanState(self._printer.hw.rear_fan)
        self._init_uv_led = self._printer.hw.uv_led.active and self._printer.hw.uv_led.pulse_remaining == 0
        self._uv_pwm_print = self._temp.uvPwmPrint

        self.add_back()

        uv_led_fan_rpm_item = AdminIntValue.from_value("UV LED fan RPM", self._temp, "fan1Rpm", 100)
        uv_led_fan_rpm_item.changed.connect(self._uv_led_fan_changed)
        blower_fan_rpm_item = AdminIntValue.from_value("Blower fan RPM", self._temp, "fan2Rpm", 100)
        blower_fan_rpm_item.changed.connect(self._blower_fan_changed)
        rear_fan_rpm_item = AdminBoolValue.from_value("Rear fan", self, "rear_fan")
        rear_fan_rpm_item.changed.connect(self._rear_fan_changed)
        uv_pwm_item = AdminIntValue.from_value("UV LED PWM", self._temp, "uvPwm", 1)
        uv_pwm_item.changed.connect(self._uv_pwm_changed)
        uv_pwm_tune_item = AdminIntValue.from_value("UV LED PWM fine tune", self._temp, "uvPwmTune", 1)
        uv_pwm_tune_item.changed.connect(self._uv_pwm_changed)
        self.add_items(
            (
                AdminBoolValue.from_value("UV LED fan", self, "uv_led_fan"),
                uv_led_fan_rpm_item,
                AdminBoolValue.from_value("Blower fan", self, "blower_fan"),
                blower_fan_rpm_item,
                rear_fan_rpm_item,
                AdminIntValue.from_value("Rear fan RPM", self._temp, "fan3Rpm", 100),
                AdminBoolValue.from_value("UV LED", self, "uv_led"),
                uv_pwm_item,
                uv_pwm_tune_item,
                AdminIntValue.from_value("UV calib. warm-up [s]", self._temp, "uvWarmUpTime", 1),
                AdminIntValue.from_value("UV calib. intensity", self._temp, "uvCalibIntensity", 1),
                AdminIntValue.from_value("UV cal. min. int. edge", self._temp, "uvCalibMinIntEdge", 1),
                AdminAction("Save", self.save),
                AdminAction("Reset to defaults", self.reset_to_defaults),
                AdminAction("Save & save as defaults", self.save_as_defaults),
                AdminAction("Save to boostV2 board", self.save_to_booster),
            )
        )

    def on_leave(self):
        self._init_uv_led_fan.restore()
        self._init_blower_fan.restore()
        self._init_rear_fan.restore()
        if self._init_uv_led:
            self._printer.hw.uv_led.on()
        else:
            self._printer.hw.uv_led.off()

    @property
    def uv_led_fan(self) -> bool:
        return self._printer.hw.uv_led_fan.enabled

    @uv_led_fan.setter
    def uv_led_fan(self, value: bool):
        self._printer.hw.uv_led_fan.enabled = value

    @property
    def blower_fan(self) -> bool:
        return self._printer.hw.blower_fan.enabled

    @blower_fan.setter
    def blower_fan(self, value: bool):
        self._printer.hw.blower_fan.enabled = value

    @property
    def rear_fan(self) -> bool:
        return self._printer.hw.rear_fan.enabled

    @rear_fan.setter
    def rear_fan(self, value: bool):
        self._printer.hw.rear_fan.enabled = value

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

    def save(self):
        self._printer.hw.uv_led.save_usage()
        self._temp.commit(write=True)
        self._control.enter(Info(self._control, "Configuration saved"))

    def reset_to_defaults(self):
        self._control.enter(Confirm(self._control, self._do_reset_to_defaults, text="Reset to factory defaults?"))

    def _do_reset_to_defaults(self) -> None:
        self.logger.info("Fans&LEDs - Resetting to defaults")
        del self._printer.hw.config.uvCurrent  # remove old value too
        del self._printer.hw.config.uvPwm
        del self._printer.hw.config.uvPwmTune
        del self._printer.hw.config.fan1Rpm
        del self._printer.hw.config.fan2Rpm
        del self._printer.hw.config.fan3Rpm
        for fan in self._printer.hw.fans.values():
            fan.target_rpm = fan.default_rpm
        self._printer.hw.uv_led.pwm = self._printer.hw.config.uvPwmPrint
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
        if self._printer.model.options.has_booster:
            self._control.enter(
                Confirm(self._control, self._do_save_to_booster, text="Save current PWM to boosterV2 board?")
            )
        else:
            self._control.enter(Error(self._control, text="Works only on printer with boosterV2 board!", pop=1))

    def _do_save_to_booster(self):
        try:
            self._printer.hw.uv_led.pwm = self._uv_pwm_print
            self._printer.hw.sl1s_booster.save_permanently()
        except Exception:
            self._control.enter(Error(self._control, text="!!! Failed to save PWM to boosterV2 board !!!", pop=1))

    def _uv_led_fan_changed(self):
        self.uv_led_fan = True
        self._printer.hw.fans[0].target_rpm = self._temp.fan1Rpm

    def _blower_fan_changed(self):
        self.blower_fan = True
        self._printer.hw.fans[1].target_rpm = self._temp.fan2Rpm

    def _rear_fan_changed(self):
        self.rear_fan = True
        self._printer.hw.fans[2].target_rpm = self._temp.fan3Rpm

    def _uv_pwm_changed(self):
        # TODO: simplify work with config and config writer
        self._uv_pwm_print = self._temp.uvPwm + self._temp.uvPwmTune
        self._printer.hw.uv_led.pwm = self._uv_pwm_print
