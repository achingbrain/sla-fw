# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from datetime import datetime
from typing import Optional
from asyncio import sleep, gather

from slafw import defines
from slafw.configs.runtime import RuntimeConfig
from slafw.errors.errors import DisplayTestFailed
from slafw.functions.system import FactoryMountedRW
from slafw.hardware.base.hardware import BaseHardware
from slafw.image.exposure_image import ExposureImage
from slafw.image.cairo import draw_svg_expand
from slafw.states.wizard import WizardState
from slafw.wizard.actions import UserActionBroker, PushState
from slafw.wizard.checks.base import WizardCheckType, DangerousCheck, Check
from slafw.wizard.setup import Configuration, TankSetup, Resource


class DisplayTest(DangerousCheck):
    def __init__(self, hw: BaseHardware, exposure_image: ExposureImage,
                 runtime_config: RuntimeConfig):
        super().__init__(
            hw,
            WizardCheckType.DISPLAY,
            Configuration(TankSetup.REMOVED, None),
            [Resource.UV, Resource.TILT, Resource.TOWER_DOWN, Resource.TOWER],
        )
        self._exposure_image = exposure_image
        self._runtime_config = runtime_config

        self.result: Optional[bool] = None

    def reset(self):
        self.result = None

    async def async_task_run(self, actions: UserActionBroker):
        self.reset()
        await self.wait_cover_closed()
        await gather(self._hw.tower.verify_async(), self._hw.tilt.verify_async())
        old_state = False     # turn LEDs on for first time
        self._hw.start_fans()
        self._hw.exposure_screen.draw_pattern(draw_svg_expand, defines.prusa_logo_file, True)
        self._logger.debug("Registering display test user resolution callback")
        actions.report_display.register_callback(self.user_callback)
        display_check_state = PushState(WizardState.TEST_DISPLAY)
        actions.push_state(display_check_state)
        try:
            while self.result is None:
                actual_state = self._hw.isCoverVirtuallyClosed()
                if old_state != actual_state:
                    old_state = actual_state
                    if actual_state:
                        # TODO: create uv_led.set_default_pwm()
                        self._hw.uv_led.pwm = self._hw.uv_led.parameters.safe_default_pwm
                        self._hw.uv_led.on()
                    else:
                        self._hw.uv_led.off()
                await sleep(0.1)
        finally:
            actions.report_display.unregister_callback()
            actions.drop_state(display_check_state)
            self._logger.debug("Finishing display test")
            self._hw.uv_led.off()
            self._hw.uv_led.save_usage()
            self._hw.stop_fans()
            self._exposure_image.blank_screen()

        if not self.result:
            self._logger.error("Display test failed")
            # TODO: Register error for this
            raise DisplayTestFailed()

    def user_callback(self, result: bool):
        self.result = result
        self._logger.info("Use reported display status: %s", result)


class RecordExpoPanelLog(Check):
    def __init__(self, hw: BaseHardware):
        super().__init__(WizardCheckType.RECORD_EXPO_PANEL_LOG)
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        panel_sn = self._hw.exposure_screen.serial_number
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(defines.expoPanelLogPath, "r") as f:
            log = json.load(f)
        last_key = list(log)[-1]
        log[last_key]["counter_s"] = \
            self._hw.display.usage_s  # write display counter to the previous panel
        self._hw.display.clear_usage()  # clear only UV statistics for display counter
        log[timestamp] = {"panel_sn": panel_sn}  # create new record

        with FactoryMountedRW():
            with open(defines.expoPanelLogPath, "w") as f:
                json.dump(log, f, indent=2)
