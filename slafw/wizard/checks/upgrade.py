# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.configs.hw import HwConfig
from slafw.hardware.base.hardware import BaseHardware
from slafw.configs.writer import ConfigWriter
from slafw.functions.system import set_configured_printer_model, set_factory_uvpwm
from slafw.hardware.base.uv_led import UVLED
from slafw.hardware.printer_model import PrinterModel

from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import Check, WizardCheckType


class ResetUVPWM(Check):
    def __init__(self, writer: ConfigWriter, uv_led: UVLED):
        super().__init__(WizardCheckType.ERASE_UV_PWM)
        self._writer = writer
        self._uv_led = uv_led

    async def async_task_run(self, actions: UserActionBroker):
        del self._writer.uvCurrent
        del self._writer.uvPwmTune
        pwm = self._uv_led.parameters.safe_default_pwm
        self._writer.uvPwm = pwm
        set_factory_uvpwm(pwm)


class ResetSelfTest(Check):
    def __init__(self, writer: ConfigWriter):
        super().__init__(WizardCheckType.RESET_SELF_TEST)
        self._writer = writer

    async def async_task_run(self, actions: UserActionBroker):
        self._writer.showWizard = True


class ResetMechanicalCalibration(Check):
    def __init__(self, writer: ConfigWriter):
        super().__init__(WizardCheckType.RESET_MECHANICAL_CALIBRATION)
        self._writer = writer

    async def async_task_run(self, actions: UserActionBroker):
        del self._writer.tower_height_nm
        del self._writer.towerHeight
        del self._writer.tiltHeight
        self._writer.calibrated = False


class ResetHwCounters(Check):
    def __init__(self, hw: BaseHardware):
        super().__init__(WizardCheckType.RESET_HW_COUNTERS)
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.uv_led.clear_usage()
        self._hw.display.clear_usage()


class MarkPrinterModel(Check):
    def __init__(self, model: PrinterModel, config: HwConfig):
        super().__init__(WizardCheckType.MARK_PRINTER_MODEL)
        self._model = model
        self._config = config

    async def async_task_run(self, actions: UserActionBroker):
        self._logger.info("Setting printer model to %s", self._model)
        set_configured_printer_model(self._model)
        self._config.vatRevision = self._model.options.vat_revision
