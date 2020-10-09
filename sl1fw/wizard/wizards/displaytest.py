# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.libConfig import HwConfig, RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen
from sl1fw.states.wizard import WizardId
from sl1fw.wizard.groups.display import DisplayTestCheckGroup
from sl1fw.wizard.wizard import Wizard


class DisplayTestWizard(Wizard):
    def __init__(self, hw: Hardware, hw_config: HwConfig, screen: Screen, runtime_config: RuntimeConfig):
        super().__init__(WizardId.DISPLAY, [DisplayTestCheckGroup(hw, hw_config, screen, runtime_config)], hw)
