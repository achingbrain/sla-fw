# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, asdict
from threading import Thread
from time import sleep
from typing import Dict, Any

from sl1fw import defines
from sl1fw.functions.system import shut_down
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import SyncCheck, WizardCheckType
from sl1fw.wizard.setup import Configuration


@dataclass
class CheckData:
    # UV LED temperature at the beginning of test (should be close to ambient)
    wizardTempUvInit: float
    # ambient sensor temperature
    wizardTempAmbient: float
    # A64 temperature
    wizardTempA64: float


class TemperatureTest(SyncCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.TEMPERATURE, Configuration(None, None), [],
        )
        self._hw = hw
        self._check_data = None

    def task_run(self, actions: UserActionBroker):
        self._logger.debug("Checking temperatures")

        # A64 overheat check
        self._logger.info("Checking A64 for overheating")
        a64_temperature = self._hw.getCpuTemperature()
        if a64_temperature > defines.maxA64Temp:
            Thread(target=self._overheat, daemon=True).start()
            raise Exception(
                "A64 temperature is too high. Measured: %.1f °C!\n\n" "Shutting down in 10 seconds..." % a64_temperature
            )

        # Checking MC temperatures
        self._logger.info("Checking MC temperatures")
        temperatures = self._hw.getMcTemperatures()
        for i in (self._hw.led_temp_idx, self._hw.ambient_temp_idx):
            if temperatures[i] < 0:
                raise Exception(
                    "%s cannot be read.\n\nPlease check if temperature sensors are connected correctly."
                    % self._hw.getSensorName(i)
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
                    % {"sensor": self._hw.getSensorName(i), "temp": temperatures[i]}
                )

        self._check_data = CheckData(temperatures[0], temperatures[1], a64_temperature)

    def _overheat(self):
        for _ in range(10):
            self._hw.beepAlarm(3)
            sleep(1)
        shut_down(self._hw)

    def get_result_data(self) -> Dict[str, Any]:
        return asdict(self._check_data)
