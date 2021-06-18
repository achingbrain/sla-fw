# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep, gather

from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, DangerousCheck
from sl1fw.wizard.setup import Configuration, Resource


class VatCleanerCheck(DangerousCheck):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage):
        super().__init__(
            hw, WizardCheckType.VAT_CLEANER, Configuration(None, None), [Resource.FANS, Resource.UV],
        )
        self._exposure_image = exposure_image

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        with actions.led_warn:
            await gather(self.verify_tower(), self.verify_tilt())
            self._exposure_image.blank_screen()
            self._exposure_image.inverse()
            self._hw.uvLedPwm = self._hw.config.uvPwmPrint
            self._hw.startFans()
            self._hw.uvLed(True)
        try: # check may be canceled
            for countdown in range(self._hw.config.vatCleanerExposure, 0, -1):
                self.progress = 1 - countdown / self._hw.config.vatCleanerExposure
                await sleep(1)
        finally:
            self._hw.uvLed(False)
            self._hw.stopFans()
            self._exposure_image.blank_screen()
