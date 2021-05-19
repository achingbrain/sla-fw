# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from abc import abstractmethod
from asyncio import AbstractEventLoop, Task
from functools import partial
from typing import Iterable

from sl1fw.wizard.checks.sysinfo import SystemInfoTest

from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.functions.system import shut_down
from sl1fw.hardware.printer_model import PrinterModel
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardId, WizardState
from sl1fw.wizard.actions import UserActionBroker, PushState
from sl1fw.wizard.checks.upgrade import (
    ResetUVPWM,
    ResetSelfTest,
    ResetMechanicalCalibration,
    ResetHwCounters,
    MarkPrinterModel,
)
from sl1fw.wizard.group import CheckGroup
from sl1fw.wizard.wizard import Wizard, WizardDataPackage
from sl1fw.wizard.wizards.generic import ShowResultsGroup


class SL1SUpgradeCleanup(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            checks=(
                ResetUVPWM(package.config_writer),
                ResetSelfTest(package.config_writer),
                ResetMechanicalCalibration(package.config_writer),
                ResetHwCounters(package.hw),
            )
        )
        self._package = package

    async def setup(self, actions: UserActionBroker):
        done = asyncio.Event()
        wait_state = PushState(WizardState.SL1S_CONFIRM_UPGRADE)

        def accept(loop: AbstractEventLoop):
            self._logger.debug("The user has accepted SL1S upgrade")
            loop.call_soon_threadsafe(done.set)

        def reject(loop: AbstractEventLoop, task: Task):
            self._logger.info("Shutting down to let user remove SL1S components as the user has rejected upgrade")

            # TODO: This is commented out to let development printer to keep their configuration and be still usable
            # TODO: after installing the sl1s upgrade.
            # TODO: This should be uncommented in beta/public release
            # shut_down(self._package.hw, reboot=False)

            loop.call_soon_threadsafe(task.cancel)

        try:
            actions.sl1s_confirm_upgrade.register_callback(partial(accept, asyncio.get_running_loop()))
            actions.sl1s_reject_upgrade.register_callback(
                partial(reject, asyncio.get_running_loop(), asyncio.current_task())
            )
            actions.push_state(wait_state)
            self._logger.debug("Waiting for user to confirm SL1S upgrade")
            await done.wait()
        finally:
            actions.sl1s_confirm_upgrade.unregister_callback()
            actions.sl1s_reject_upgrade.unregister_callback()
            actions.drop_state(wait_state)


class SL1SUpgradePrepare(CheckGroup):
    """ Just save system info BEFORE any cleanups """
    def __init__(self, package: WizardDataPackage):
        super().__init__(
            checks=(
                SystemInfoTest(package.hw),
            )
        )

    async def setup(self, actions: UserActionBroker):
        pass


class SL1SUpgradeFinish(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(checks=(MarkPrinterModel(PrinterModel.SL1S, package.hw.config),))

    async def setup(self, actions: UserActionBroker):
        pass


class SL1DowngradeFinish(CheckGroup):
    def __init__(self, package: WizardDataPackage):
        super().__init__(checks=(MarkPrinterModel(PrinterModel.SL1, package.hw.config),))

    async def setup(self, actions: UserActionBroker):
        pass


class UpgradeWizardBase(Wizard):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(
            hw=hw, runtime_config=runtime_config, exposure_image=exposure_image, config_writer=hw.config.get_writer(),
        )

        super().__init__(
            self.get_id(), self.get_groups(), self._package, cancelable=False,
        )

    @abstractmethod
    def get_groups(self) -> Iterable[CheckGroup]:
        ...

    @abstractmethod
    def get_id(self):
        ...

    def run(self):
        super().run()
        if self.state == WizardState.DONE:
            self._logger.info("Rebooting after SL1S upgrade, the printer will autoconfigure on the next boot")
            shut_down(self._hw, reboot=True)


class SL1SUpgradeWizard(UpgradeWizardBase):
    def get_id(self):
        return WizardId.SL1S_UPGRADE

    def get_groups(self):
        return SL1SUpgradePrepare(self._package), SL1SUpgradeCleanup(self._package), ShowResultsGroup(), SL1SUpgradeFinish(self._package)


class SL1DowngradeWizard(UpgradeWizardBase):
    def get_id(self):
        return WizardId.SL1_DOWNGRADE

    def get_groups(self):
        return SL1SUpgradePrepare(self._package), SL1SUpgradeCleanup(self._package), ShowResultsGroup(), SL1DowngradeFinish(self._package)
