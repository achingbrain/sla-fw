# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Thread
from time import sleep
from typing import Optional

from sl1fw import defines
from sl1fw.functions.system import shut_down
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import SyncCheck, WizardCheckType
from sl1fw.wizard.setup import Configuration


class TemperatureTest(SyncCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.TEMPERATURE, Configuration(None, None), [],
        )
        self.hw = hw

        self.wizard_temp_a64: Optional[float] = None
        self.wizard_temp_uv_init: Optional[float] = None
        self.wizard_temp_ambient: Optional[float] = None

    def task_run(self, actions: UserActionBroker):
        self._logger.debug("Checking temperatures")

        # A64 overheat check
        self._logger.info("Checking A64 for overheating")
        a64_temperature = self.hw.getCpuTemperature()
        if a64_temperature > defines.maxA64Temp:
            Thread(target=self._overheat, daemon=True).start()
            raise Exception(
                "A64 temperature is too high. Measured: %.1f °C!\n\n" "Shutting down in 10 seconds..." % a64_temperature
            )

        # Checking MC temperatures
        self._logger.info("Checking MC temperatures")
        temperatures = self.hw.getMcTemperatures()
        for i in range(2):
            if temperatures[i] < 0:
                raise Exception(
                    "%s cannot be read.\n\nPlease check if temperature sensors are connected correctly."
                    % self.hw.getSensorName(i)
                )
            if i == 0:
                max_temp = defines.maxUVTemp
            else:
                max_temp = defines.maxAmbientTemp
            if not defines.minAmbientTemp < temperatures[i] < max_temp:
                raise Exception(
                    "%(sensor)s not in range!\n\n"
                    "Measured temperature: %(temp).1f °C.\n\n"
                    "Keep the printer out of direct sunlight at room temperature (18 - 32 °C)."
                    % {"sensor": self.hw.getSensorName(i), "temp": temperatures[i]}
                )

        self.wizard_temp_a64 = a64_temperature
        self.wizard_temp_uv_init = temperatures[0]
        self.wizard_temp_ambient = temperatures[1]

    def _overheat(self):
        for _ in range(10):
            self.hw.beepAlarm(3)
            sleep(1)
        shut_down(self.hw)
