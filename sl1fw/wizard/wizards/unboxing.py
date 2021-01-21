# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Iterable

from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardId, WizardState
from sl1fw.wizard.groups.base import CheckGroup
from sl1fw.wizard.groups.unboxing import (
    RemoveSafetyStickerCheckGroup,
    RemoveSideFoamCheckGroup,
    RemoveTankFoamCheckGroup,
    RemoveDisplayFoilCheckGroup,
)
from sl1fw.wizard.wizard import Wizard


class UnboxingWizard(Wizard):
    def __init__(self, identifier, groups: Iterable[CheckGroup], hw: Hardware, hw_config: HwConfig):
        super().__init__(identifier, groups, hw, cancelable=False)
        self._hw_config = hw_config

    def run(self):
        super().run()
        if self.state == WizardState.DONE:
            self._logger.info("Unboxing wizard finished without errors, setting show unboxing to false")
            writer = self._hw_config.get_writer()
            writer.showUnboxing = False
            writer.commit()


class CompleteUnboxingWizard(UnboxingWizard):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            WizardId.COMPLETE_UNBOXING,
            [
                RemoveSafetyStickerCheckGroup(hw, hw_config),
                RemoveSideFoamCheckGroup(hw, hw_config),
                RemoveTankFoamCheckGroup(),
                RemoveDisplayFoilCheckGroup(),
            ],
            hw,
            hw_config,
        )


class KitUnboxingWizard(UnboxingWizard):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(WizardId.KIT_UNBOXING, [RemoveDisplayFoilCheckGroup()], hw, hw_config)
