# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.state_actions.manager import ActionManager
from sl1fw.wizard.wizard import Wizard
from sl1fw.wizard.wizards.calibration import CalibrationWizard
from sl1fw.wizard.wizards.displaytest import DisplayTestWizard
from sl1fw.wizard.wizards.factory_reset import PackingWizard, FactoryResetWizard
from sl1fw.wizard.wizards.unboxing import KitUnboxingWizard, CompleteUnboxingWizard
from sl1fw.wizard.wizards.self_test import SelfTestWizard
from sl1fw.wizard.wizards.uv_calibration import UVCalibrationWizard

# TODO: Get rid of this indirection

# pylint: disable = too-many-arguments


def displaytest_wizard(
    action_manager: ActionManager, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig,
) -> Wizard:
    return action_manager.start_wizard(DisplayTestWizard(hw, exposure_image, runtime_config))


def unboxing_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig,
) -> Wizard:
    return action_manager.start_wizard(CompleteUnboxingWizard(hw, hw_config, runtime_config))


def kit_unboxing_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig,
) -> Wizard:
    return action_manager.start_wizard(KitUnboxingWizard(hw, hw_config, runtime_config))


def self_test_wizard(
    action_manager: ActionManager,
    hw: Hardware,
    hw_config: HwConfig,
    exposure_image: ExposureImage,
    runtime_config: RuntimeConfig,
) -> Wizard:
    return action_manager.start_wizard(SelfTestWizard(hw, hw_config, exposure_image, runtime_config))


def calibration_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig,
) -> Wizard:
    return action_manager.start_wizard(CalibrationWizard(hw, hw_config, runtime_config))


def packing_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig,
) -> Wizard:
    return action_manager.start_wizard(PackingWizard(hw, hw_config, runtime_config))


def factory_reset_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig,
) -> Wizard:
    return action_manager.start_wizard(FactoryResetWizard(hw, hw_config, runtime_config))


def uv_calibration_wizard(
    action_manager: ActionManager,
    hw: Hardware,
    hw_config: HwConfig,
    exposure_image: ExposureImage,
    runtime_config: RuntimeConfig,
    display_replaced: bool,
    led_module_replaced: bool,
) -> Wizard:
    return action_manager.start_wizard(
        UVCalibrationWizard(
            hw,
            hw_config,
            exposure_image,
            runtime_config,
            display_replaced=display_replaced,
            led_module_replaced=led_module_replaced,
        )
    )
