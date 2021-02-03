# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.screen.screen import Screen
from sl1fw.state_actions.manager import ActionManager
from sl1fw.wizard.wizard import Wizard
from sl1fw.wizard.wizards.calibration import CalibrationWizard
from sl1fw.wizard.wizards.displaytest import DisplayTestWizard
from sl1fw.wizard.wizards.unboxing import KitUnboxingWizard, CompleteUnboxingWizard
from sl1fw.wizard.wizards.wizard import TheWizard


def displaytest_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, screen: Screen, runtime_config: RuntimeConfig
) -> Wizard:
    return action_manager.start_wizard(DisplayTestWizard(hw, hw_config, screen, runtime_config))


def unboxing_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig
) -> Wizard:
    return action_manager.start_wizard(CompleteUnboxingWizard(hw, hw_config, runtime_config))


def kit_unboxing_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig
) -> Wizard:
    return action_manager.start_wizard(KitUnboxingWizard(hw, hw_config, runtime_config))


def the_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, screen: Screen, runtime_config: RuntimeConfig
) -> Wizard:
    return action_manager.start_wizard(TheWizard(hw, hw_config, screen, runtime_config))


def calibration_wizard(
    action_manager: ActionManager, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig
) -> Wizard:
    return action_manager.start_wizard(CalibrationWizard(hw, hw_config, runtime_config))
