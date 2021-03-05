# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Iterable

from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.libHardware import Hardware
from sl1fw.libUvLedMeterMulti import UvLedMeterMulti, UVCalibrationResult
from sl1fw.states.wizard import WizardId
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.display import DisplayTest
from sl1fw.wizard.checks.sysinfo import SystemInfoTest
from sl1fw.wizard.checks.tilt import TiltLevelTest
from sl1fw.wizard.checks.tower import TowerHomeTest
from sl1fw.wizard.checks.uv_calibration import (
    CheckUVMeter,
    UVWarmupCheck,
    CheckUVMeterPlacement,
    UVCalibrateCenter,
    UVCalibrateEdge,
    UVCalibrateApply,
    UVRemoveCalibrator,
)
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.setup import Configuration, TankSetup, PlatformSetup
from sl1fw.wizard.wizard import Wizard

# pylint: disable = too-many-arguments


class UVCalibrationPrepare(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        super().__init__(
            Configuration(TankSetup.REMOVED, PlatformSetup.PRINT),
            [
                DisplayTest(hw, exposure_image, runtime_config),
                TowerHomeTest(hw, hw_config),
                TiltLevelTest(hw),
                SystemInfoTest(hw),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.uv_calibration_prepared, WizardState.UV_CALIBRATION_PREPARE)


class UVCalibrationPlaceUVMeter(CheckGroup):
    def __init__(self, hw: Hardware, hw_config: HwConfig, exposure_image: ExposureImage, uv_meter: UvLedMeterMulti):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [
                CheckUVMeter(hw, uv_meter),
                UVWarmupCheck(hw, hw_config, exposure_image, uv_meter),
                CheckUVMeterPlacement(hw, hw_config, exposure_image, uv_meter),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.uv_meter_placed, WizardState.UV_CALIBRATION_PLACE_UV_METER)


class UVCalibrationCalibrate(CheckGroup):
    def __init__(
        self,
        hw: Hardware,
        hw_config: HwConfig,
        exposure_image: ExposureImage,
        uv_meter: UvLedMeterMulti,
        replacement: bool,
        result: UVCalibrationResult,
    ):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [
                UVCalibrateCenter(hw, hw_config, exposure_image, uv_meter, replacement, result),
                UVCalibrateEdge(hw, hw_config, exposure_image, uv_meter, replacement, result),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        # No initial actions, connect to previous group?
        pass


class UVCalibrationFinish(CheckGroup):
    def __init__(
        self,
        hw: Hardware,
        hw_config: HwConfig,
        runtime_config: RuntimeConfig,
        result: UVCalibrationResult,
        display_replaced: bool,
        led_module_replaced: bool,
        uv_meter: UvLedMeterMulti,
    ):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [
                UVRemoveCalibrator(hw, uv_meter),
                UVCalibrateApply(hw, hw_config, runtime_config, result, display_replaced, led_module_replaced),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        # No initial actions, connect to previous group?
        pass


class UVCalibrationWizard(Wizard):
    def __init__(
        self,
        hw: Hardware,
        hw_config: HwConfig,
        exposure_image: ExposureImage,
        runtime_config: RuntimeConfig,
        display_replaced: bool,
        led_module_replaced: bool,
    ):
        self._uv_meter = UvLedMeterMulti()
        self._result = UVCalibrationResult()
        super().__init__(
            WizardId.UV_CALIBRATION,
            [
                UVCalibrationPrepare(hw, hw_config, exposure_image, runtime_config),
                UVCalibrationPlaceUVMeter(hw, hw_config, exposure_image, self._uv_meter),
                UVCalibrationCalibrate(
                    hw, hw_config, exposure_image, self._uv_meter, display_replaced or led_module_replaced, self._result
                ),
                UVCalibrationFinish(
                    hw, hw_config, runtime_config, self._result, display_replaced, led_module_replaced, self._uv_meter
                ),
            ],
            hw,
            exposure_image,
            runtime_config,
        )
        self._display_replaced = display_replaced
        self._led_module_replaced = led_module_replaced
        self._hw = hw
        self._exposure_image = exposure_image

    def run(self):
        try:
            super().run()
        finally:
            self._hw.uvLed(False)
            self._hw.motorsRelease()
            self._hw.stopFans()
            self._exposure_image.blank_screen()

    @classmethod
    def get_alt_names(cls) -> Iterable[str]:
        names = ["uvcalib_data.toml"]
        names.extend(super().get_alt_names())
        return names

    @property
    def name(self) -> str:
        return "uv_calibration"
