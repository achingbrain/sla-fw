# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional

from sl1fw.errors.errors import DisplayTestFailed
from sl1fw.functions import display_test
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker, PushState
from sl1fw.wizard.checks.base import WizardCheckType, DangerousCheck
from sl1fw.wizard.setup import Configuration, TankSetup, Resource


class DisplayTest(DangerousCheck):
    def __init__(
        self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig,
    ):
        super().__init__(
            hw,
            WizardCheckType.DISPLAY,
            Configuration(TankSetup.REMOVED, None),
            [Resource.UV, Resource.TILT, Resource.TOWER_DOWN, Resource.TOWER],
        )
        self.hw = hw
        self.exposure_image = exposure_image
        self.runtime_config = runtime_config

        self.result: Optional[bool] = None

    def reset(self):
        self.result = None

    async def async_task_run(self, actions: UserActionBroker):
        self.reset()

        self._logger.debug("Setting hardware positions for display test")
        await self.wait_cover_closed()
        self.hw.tower_home()
        await self.wait_cover_closed()
        self.hw.tilt_home()
        await self.wait_cover_closed()
        display_test.start(self.hw, self.exposure_image, self.runtime_config)

        self._logger.debug("Registering display test user resolution callback")
        actions.report_display.register_callback(self.user_callback)
        display_check_state = PushState(WizardState.TEST_DISPLAY)
        actions.push_state(display_check_state)
        try:
            while self.result is None:
                display_test.cover_check(self.hw, self.hw.printer_model)
        finally:
            actions.report_display.unregister_callback()
            actions.drop_state(display_check_state)
            self._logger.debug("Finishing display test")
            display_test.end(self.hw, self.exposure_image, self.runtime_config)
            self.hw.motorsRelease()

        if not self.result:
            self._logger.error("Display test failed")
            # TODO: Register error for this
            raise DisplayTestFailed()

    def user_callback(self, result: bool):
        self.result = result
        self._logger.info("Use reported display status: %s", result)
