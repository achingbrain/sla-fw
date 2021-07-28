# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from datetime import datetime
from typing import Optional
from asyncio import sleep, gather

from sl1fw import defines
from sl1fw.errors.errors import DisplayTestFailed
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.functions.system import FactoryMountedRW
from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker, PushState
from sl1fw.wizard.checks.base import WizardCheckType, DangerousCheck, Check
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
        self._exposure_image = exposure_image
        self._runtime_config = runtime_config

        self.result: Optional[bool] = None

    def reset(self):
        self.result = None

    async def async_task_run(self, actions: UserActionBroker):
        self.reset()
        await self.wait_cover_closed()
        await gather(self.verify_tower(), self.verify_tilt())
        old_state = False     # turn LEDs on for first time
        self._hw.startFans()
        self._runtime_config.fan_error_override = True
        self._exposure_image.show_system_image("logo.png")
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
                        self._hw.uvLedPwm = self._hw.printer_model.calibration_parameters(self._hw.is500khz).safe_default_pwm
                        self._hw.uvLed(True)
                    else:
                        self._hw.uvLed(False)
                await sleep(0.1)
        finally:
            actions.report_display.unregister_callback()
            actions.drop_state(display_check_state)
            self._logger.debug("Finishing display test")
            self._runtime_config.fan_error_override = False
            self._hw.saveUvStatistics()
            self._hw.uvLed(False)
            self._hw.stopFans()
            self._exposure_image.blank_screen()

        if not self.result:
            self._logger.error("Display test failed")
            # TODO: Register error for this
            raise DisplayTestFailed()

    def user_callback(self, result: bool):
        self.result = result
        self._logger.info("Use reported display status: %s", result)


class RecordExpoPanelLog(Check):
    def __init__(self, hw: Hardware):
        super().__init__(WizardCheckType.RECORD_EXPO_PANEL_LOG)
        self._hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        panel_sn = self._hw.exposure_screen.panel.serial_number()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(defines.expoPanelLogPath, "r") as f:
            log = json.load(f)
        last_key = list(log)[-1]
        log[last_key]["counter_s"] = \
            self._hw.getUvStatistics()[1]  # write display counter to the previous panel
        self._hw.clearDisplayStatistics()  # clear only UV statistics for display counter
        log[timestamp] = {"panel_sn": panel_sn}  # create new record

        with FactoryMountedRW():
            with open(defines.expoPanelLogPath, "w") as f:
                json.dump(log, f, indent=2)
            self._hw.config.showWizard = True  # force selftest and calibration with new display
            self._hw.config.calibrated = False
            self._hw.config.write()
