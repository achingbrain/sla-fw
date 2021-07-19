# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List

from sl1fw import defines, test_runtime
from sl1fw.errors.errors import FanRPMOutOfTestRange, UVLEDHeatsinkFailed
from sl1fw.functions.checks import get_uv_check_pwms
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, DangerousCheck
from sl1fw.wizard.setup import Configuration, Resource


@dataclass
class CheckData:
    # fans RPM when using default PWM
    wizardFanRpm: list
    # UV LED temperature at the beginning of test (should be close to ambient)
    wizardTempUvWarm: float


class UVFansTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.UV_FANS, Configuration(None, None), [Resource.FANS, Resource.UV],
        )
        self._check_data: Optional[CheckData] = None

    async def async_task_run(self, actions: UserActionBroker):
        # pylint: disable=too-many-branches
        await self.wait_cover_closed()

        fan_diff = 200
        self._hw.startFans()
        self._hw.uvLed(True)
        rpm: List[List[int]] = [[], [], []]
        fans_wait_time = defines.fanWizardStabilizeTime + defines.fanStartStopTime

        # set UV LED to max PWM
        self._hw.uvLedPwm = get_uv_check_pwms(self._hw)[3]

        uv_temp = self._hw.getUvLedTemperature()
        fan_error = self._hw.getFansError()
        try: # check may be interrupted by another check or canceled
            for countdown in range(self._hw.config.uvWarmUpTime, 0, -1):
                self.progress = 1 - countdown / self._hw.config.uvWarmUpTime

                uv_temp = self._hw.getUvLedTemperature()
                fan_error = self._hw.getFansError()
                if uv_temp > defines.maxUVTemp:
                    self._logger.error("Skipping UV Fan check due to overheat")
                    break
                if any(fan_error.values()):
                    self._logger.error("Skipping UV Fan check due to fan failure")
                    break

                if fans_wait_time < self._hw.config.uvWarmUpTime - countdown:
                    actual_rpm = self._hw.getFansRpm()
                    for i in self._hw.fans:
                        rpm[i].append(actual_rpm[i])
                await sleep(1)
        finally:
            self._hw.uvLed(False)
            self._hw.stopFans()

        # evaluate fans data
        avg_rpms = list()
        if test_runtime.testing:
            fan_error = {0: False, 1: False, 2: False}

        for i, fan in self._hw.fans.items():  # iterate over fans
            if len(rpm[i]) == 0:
                rpm[i].append(fan.targetRpm)
            avg_rpm = sum(rpm[i]) / len(rpm[i])
            if not fan.targetRpm - fan_diff <= avg_rpm <= fan.targetRpm + fan_diff or fan_error[i]:
                self._logger.error("Fans raw RPM: %s", rpm)
                self._logger.error("Fans error: %s", fan_error)
                self._logger.error("Fans samples: %s", len(rpm[i]))
                raise (
                    FanRPMOutOfTestRange(
                        fan.name,
                        str(min(rpm[i])) + "-" + str(max(rpm[i])) if len(rpm[i]) > 1 else None,
                        round(avg_rpm) if len(rpm[i]) > 1 else None,
                        fan_error,
                    )
                )
            avg_rpms.append(avg_rpm)

        # evaluate UV LED data
        if uv_temp > defines.maxUVTemp:
            raise UVLEDHeatsinkFailed(uv_temp)

        self._check_data = CheckData(avg_rpms, uv_temp)

    def get_result_data(self) -> Dict[str, Any]:
        return asdict(self._check_data)
