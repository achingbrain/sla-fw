# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import weakref

from slafw.configs.runtime import RuntimeConfig
from slafw.libHardware import Hardware
from slafw.image.exposure_image import ExposureImage
from slafw.wizard.checks.tank_surface_cleaner import HomeTower, TiltHome, TiltUp, TowerSafeDistance, TouchDown, \
    GentlyUp, ExposeDebris, Check
from slafw.wizard.group import SingleCheckGroup, CheckGroup
from slafw.wizard.wizard import WizardId, Wizard, WizardDataPackage, WizardState
from slafw.wizard.actions import UserActionBroker


class InitGroup(SingleCheckGroup):
    """ Dummy group to pause execution on init """
    def __init__(self, check: Check):
        super().__init__(check)

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.tank_surface_cleaner_init_done, WizardState.TANK_SURFACE_CLEANER_INIT)


class InsertCleaningAdaptorGroup(SingleCheckGroup):
    """ Group to pause execution on for cleaning adaptor insertion """
    def __init__(self, check: Check):
        super().__init__(check)

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.insert_cleaning_adaptor_done, WizardState.TANK_SURFACE_CLEANER_INSERT_CLEANING_ADAPTOR)


class RemoveCleaningAdaptorGroup(CheckGroup):
    """ Group to pause execution on for cleaning adaptor removal """
    def __init__(self):
        super().__init__()

    async def setup(self, actions: UserActionBroker):
        await self.wait_for_user(actions, actions.remove_cleaning_adaptor_done, WizardState.TANK_SURFACE_CLEANER_REMOVE_CLEANING_ADAPTOR)


class TankSurfaceCleaner(Wizard):
    """
    - init
    - home platform
    - home tank (down)
    - level tank
    - platform down to the safe distance
    - platform down until it touches the cleaning adaptor against the bottom of the tank(raise exception
      if cleaning adaptor is missing)
    - gently move the platform up to the safe distance so as to not tear the exposed film of resin
    - move the platform up so that the user can remove the garbage
    """

    def __init__(self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(
            hw=hw, exposure_image=weakref.proxy(exposure_image), runtime_config=runtime_config
        )
        super().__init__(
            WizardId.TANK_SURFACE_CLEANER,
            [
                InitGroup(HomeTower(self._package.hw)),
                SingleCheckGroup(TiltHome(self._package.hw)),
                SingleCheckGroup(TiltUp(self._package.hw)),
                InsertCleaningAdaptorGroup(TowerSafeDistance(self._package.hw)),
                SingleCheckGroup(TouchDown(self._package.hw)),
                SingleCheckGroup(ExposeDebris(self._package.hw, self._package.exposure_image)),
                SingleCheckGroup(GentlyUp(self._package.hw)),
                SingleCheckGroup(HomeTower(self._package.hw)),
                RemoveCleaningAdaptorGroup(),
            ],
            self._package,
        )

    @classmethod
    def get_name(cls) -> str:
        return "tank_surface_cleaner"
