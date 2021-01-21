# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.screen.screen import Screen
from sl1fw.states.wizard import WizardId
from sl1fw.wizard.groups.wizard import (
    WizardPart1CheckGroup,
    WizardPart2CheckGroup,
    WizardPart3CheckGroup,
)
from sl1fw.wizard.wizard import Wizard


class TheWizard(Wizard):
    def __init__(self, hw: Hardware, hw_config: HwConfig, screen: Screen, runtime_config: RuntimeConfig):
        super().__init__(
            WizardId.THE_WIZARD,
            [
                WizardPart1CheckGroup(hw, hw_config, screen, runtime_config),
                WizardPart2CheckGroup(hw, hw_config),
                WizardPart3CheckGroup(hw, hw_config),
            ],
            hw,
        )
