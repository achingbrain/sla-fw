# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.hw import HwConfig

from sl1fw.libHardware import Hardware
from sl1fw.configs.writer import ConfigWriter
from sl1fw.functions.system import set_configured_printer_model, set_factory_uvpwm
from sl1fw.hardware.printer_model import PrinterModel

from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import Check, WizardCheckType


class ResetUVPWM(Check):
    def __init__(self, writer: ConfigWriter, model: PrinterModel):
        super().__init__(WizardCheckType.ERASE_UV_PWM)
        self._writer = writer
        self._model = model

    async def async_task_run(self, actions: UserActionBroker):
        del self._writer.uvCurrent
        del self._writer.uvPwmTune
        pwm = self._model.default_uvpwm()
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
        del self._writer.towerHeight
        del self._writer.tiltHeight
        self._writer.calibrated = False


class ResetHwCounters(Check):
    def __init__(self, hw: Hardware):
        super().__init__(WizardCheckType.RESET_HW_COUNTERS)
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        self._hw.clearUvStatistics()
        self._hw.clearDisplayStatistics()


class MarkPrinterModel(Check):
    def __init__(self, model: PrinterModel, config: HwConfig):
        super().__init__(WizardCheckType.MARK_PRINTER_MODEL)
        self._model = model
        self._config = config

    async def async_task_run(self, actions: UserActionBroker):
        self._logger.info("Setting printer model to %s", self._model)
        set_configured_printer_model(self._model)
        if self._model == PrinterModel.SL1:
            self._config.vatRevision = 0
        elif self._model == PrinterModel.SL1S:
            self._config.vatRevision = 1
        else:
            self._logger.warning('Not setting var revision as vat not defined for printer model: "%s"', self._model)
