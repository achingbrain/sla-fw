# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from typing import Optional

from sl1fw.errors.errors import DisplayTestFailed
from sl1fw.functions import display_test
from sl1fw.configs.hw import HwConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.screen.screen import Screen
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker, PushState
from sl1fw.wizard.checks.base import Check, WizardCheckType
from sl1fw.wizard.setup import Configuration, TankSetup, Resource


class DisplayTest(Check):
    def __init__(self, hw: Hardware, hw_config: HwConfig, screen: Screen, runtime_config: RuntimeConfig):
        super().__init__(
            WizardCheckType.DISPLAY,
            Configuration(TankSetup.REMOVED, None),
            [Resource.UV, Resource.TILT, Resource.TOWER_DOWN, Resource.TOWER],
        )
        self.hw = hw
        self.hw_config = hw_config
        self.screen = screen
        self.runtime_config = runtime_config

        self.result: Optional[bool] = None

    async def async_task_run(self, actions: UserActionBroker):
        self.result = None

        self._logger.debug("Setting hardware positions for displaytest")
        await asyncio.sleep(0)
        self.hw.tower_home()
        await asyncio.sleep(0)
        self.hw.tilt_home()
        await asyncio.sleep(0)
        display_test.start(self.hw, self.screen, self.runtime_config)

        self._logger.debug("Registering display test user resolution callback")
        actions.report_display.register_callback(self.user_callback)
        display_check_state = PushState(WizardState.TEST_DISPLAY)
        actions.push_state(display_check_state)
        close_cover_state: Optional[PushState] = None
        try:
            while self.result is None:
                if display_test.cover_check(self.hw, self.hw_config, self.screen.printer_model):
                    if close_cover_state:
                        actions.drop_state(close_cover_state)
                        close_cover_state = None
                else:
                    if not close_cover_state:
                        close_cover_state = PushState(WizardState.CLOSE_COVER)
                        actions.push_state(close_cover_state)
                await asyncio.sleep(0.5)
        finally:
            actions.report_display.unregister_callback()
            actions.drop_state(display_check_state)
            if close_cover_state:
                actions.drop_state(close_cover_state)

        if not self.result:
            self._logger.error("Display test failed")
            # TODO: Register error for this
            raise DisplayTestFailed()

        self._logger.debug("Setting hardware")
        display_test.end(self.hw, self.screen, self.runtime_config)

    def user_callback(self, result: bool):
        self.result = result
        self._logger.info("Use reported display status: %s", result)
