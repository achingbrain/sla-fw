# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Iterable

from slafw.configs.runtime import RuntimeConfig
from slafw.errors.errors import PrinterError
from slafw.functions.system import get_configured_printer_model
from slafw.hardware.base.hardware import BaseHardware
from slafw.image.exposure_image import ExposureImage
from slafw.libUvLedMeterMulti import UvLedMeterMulti, UVCalibrationResult
from slafw.states.wizard import WizardId
from slafw.states.wizard import WizardState
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.display import DisplayTest
from slafw.wizard.checks.sysinfo import SystemInfoTest
from slafw.wizard.checks.uv_calibration import (
    CheckUVMeter,
    UVWarmupCheck,
    CheckUVMeterPlacement,
    UVCalibrateCenter,
    UVCalibrateEdge,
    UVCalibrateApply,
    UVRemoveCalibrator,
)
from slafw.wizard.checks.uvleds import UVLEDsTest
from slafw.wizard.group import CheckGroup
from slafw.wizard.setup import Configuration, TankSetup, PlatformSetup
from slafw.wizard.wizard import Wizard, WizardDataPackage


# pylint: disable = too-many-arguments


class UVCalibrationPrepare(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            Configuration(TankSetup.REMOVED, PlatformSetup.PRINT),
            [
                UVLEDsTest(package.hw),
                DisplayTest(package.hw, package.exposure_image, package.runtime_config),
                SystemInfoTest(package.hw),
            ],
        )
        self._package = package

    async def setup(self, actions: UserActionBroker):
        printer_model = get_configured_printer_model()
        if not printer_model.options.has_UV_calibration:  # type: ignore[attr-defined]
            raise PrinterError("UV calibration does not work on this printer model")
        await self.wait_for_user(actions, actions.uv_calibration_prepared, WizardState.UV_CALIBRATION_PREPARE)


class UVCalibrationPlaceUVMeter(CheckGroup):
    # TODO: Checks are run in parallel within the group. This group would make a use of strict serial execution.
    # TODO: Currently this is achieved as a side effect of locking the resources. Explicit serial execution is
    # TODO: appreciated.
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
    # TODO: Checks are run in parallel within the group. This group would make a use of strict serial execution.
    # TODO: Currently this is achieved as a side effect of locking the resources. Explicit serial execution is
    # TODO: appreciated.
    def __init__(self, package: WizardDataPackage, replacement: bool):
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
    def __init__(self, package: WizardDataPackage, display_replaced: bool, led_module_replaced: bool):
        super().__init__(
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [
                UVRemoveCalibrator(package.hw, package.uv_meter),
                UVCalibrateApply(
                    package.hw, package.runtime_config, package.uv_result, display_replaced, led_module_replaced
                ),
            ],
        )

    async def setup(self, actions: UserActionBroker):
        # No initial actions, connect to previous group?
        pass


class UVCalibrationWizard(Wizard):
    def __init__(
        self,
        hw: BaseHardware,
        exposure_image: ExposureImage,
        runtime_config: RuntimeConfig,
        display_replaced: bool,
        led_module_replaced: bool,
    ):
        # TODO: use config_writer instead
        self._package = WizardDataPackage(
            hw=hw,
            config_writer=hw.config.get_writer(),
            exposure_image=exposure_image,
            runtime_config=runtime_config,
            uv_meter=UvLedMeterMulti(),
            uv_result=UVCalibrationResult(),
        )
        super().__init__(
            WizardId.UV_CALIBRATION,
            [
                UVCalibrationPrepare(self._package),
                UVCalibrationPlaceUVMeter(self._package),
                UVCalibrationCalibrate(self._package, display_replaced or led_module_replaced),
                UVCalibrationFinish(self._package, display_replaced, led_module_replaced),
            ],
            self._package,
        )

    @classmethod
    def get_alt_names(cls) -> Iterable[str]:
        names = ["uvcalib_data.toml"]
        names.extend(super().get_alt_names())
        return names

    @classmethod
    def get_name(cls) -> str:
        return "uv_calibration"

    def run(self):
        try:
            super().run()
        finally:
            self._package.hw.uv_led.off()
            self._package.hw.stop_fans()
            self._package.uv_meter.close()
