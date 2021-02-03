# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardId
from sl1fw.wizard.groups.calibration import (
    PlatformInsertCheckGroup,
    TankPlacementCheckGroup,
    TiltAlignCheckGroup,
    PlatformAlignCheckGroup,
    CalibrationFinishCheckGroup,
)
from sl1fw.wizard.wizard import Wizard


class CalibrationWizard(Wizard):
    def __init__(self, hw: Hardware, hw_config: HwConfig, runtime_config: RuntimeConfig):
        super().__init__(
            WizardId.CALIBRATION,
            [
                PlatformInsertCheckGroup(hw),
                TankPlacementCheckGroup(hw),
                TiltAlignCheckGroup(hw, hw_config),
                PlatformAlignCheckGroup(hw, hw_config),
                CalibrationFinishCheckGroup(hw, hw_config),
            ],
            hw,
            runtime_config,
        )

    def run(self):
        try:
            super().run()
        except Exception:
            self._hw.motorsRelease()
            raise

    @property
    def name(self) -> str:
        return "calibration"
