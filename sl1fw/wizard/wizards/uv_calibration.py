# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Iterable

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
from sl1fw.wizard.wizard import Wizard, WizardDataPackage

# pylint: disable = too-many-arguments


class UVCalibrationPrepare(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.REMOVED, PlatformSetup.PRINT),
            [
                TowerHomeTest(package.hw, package.config_writer),
                TiltLevelTest(package.hw),
                DisplayTest(package.hw, package.exposure_image, package.runtime_config),
                SystemInfoTest(package.hw),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.uv_calibration_prepared, WizardState.UV_CALIBRATION_PREPARE)


class UVCalibrationPlaceUVMeter(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [
                CheckUVMeter(package.hw, package.uv_meter),
                UVWarmupCheck(package.hw, package.exposure_image, package.uv_meter),
                CheckUVMeterPlacement(package.hw, package.exposure_image, package.uv_meter),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.uv_meter_placed, WizardState.UV_CALIBRATION_PLACE_UV_METER)


class UVCalibrationCalibrate(CheckGroup):
    def __init__(
        self,
        package: WizardDataPackage,
        replacement: bool
    ):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [
                UVCalibrateCenter(package.hw, package.exposure_image, package.uv_meter, replacement, package.uv_result),
                UVCalibrateEdge(package.hw, package.exposure_image, package.uv_meter, replacement, package.uv_result),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        # No initial actions, connect to previous group?
        pass


class UVCalibrationFinish(CheckGroup):
    def __init__(
        self,
        package: WizardDataPackage,
        display_replaced: bool,
        led_module_replaced: bool
    ):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [
                UVRemoveCalibrator(package.hw, package.uv_meter),
                UVCalibrateApply(package.hw, package.runtime_config, package.uv_result, display_replaced, led_module_replaced),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        # No initial actions, connect to previous group?
        pass


class UVCalibrationWizard(Wizard):
    def __init__(
        self,
        hw: Hardware,
        exposure_image: ExposureImage,
        runtime_config: RuntimeConfig,
        display_replaced: bool,
        led_module_replaced: bool,
    ):
        #TODO: use config_writer instead
        self._package = WizardDataPackage(
            hw=hw,
            config_writer=hw.config.get_writer(),
            exposure_image=exposure_image,
            runtime_config=runtime_config,
            uv_meter = UvLedMeterMulti(),
            uv_result = UVCalibrationResult()
        )
        super().__init__(
            WizardId.UV_CALIBRATION,
            [
                UVCalibrationPrepare(self._package),
                UVCalibrationPlaceUVMeter(self._package),
                UVCalibrationCalibrate(
                    self._package, display_replaced or led_module_replaced
                ),
                UVCalibrationFinish(
                    self._package, display_replaced, led_module_replaced
                ),
            ],
            self._package
        )
        self._package.config_writer.uvPwm = 0
        self._package.config_writer.commit()

    @classmethod
    def get_alt_names(cls) -> Iterable[str]:
        names = ["uvcalib_data.toml"]
        names.extend(super().get_alt_names())
        return names

    @property
    def name(self) -> str:
        return "uv_calibration"
