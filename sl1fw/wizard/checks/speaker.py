# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Event
from typing import Optional

from sl1fw.errors.errors import SoundTestFailed
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.actions import UserActionBroker, PushState
from sl1fw.wizard.checks.base import SyncCheck, WizardCheckType
from sl1fw.wizard.setup import Configuration


class SpeakerTest(SyncCheck):
    def __init__(self):
        super().__init__(
            WizardCheckType.MUSIC, Configuration(None, None), [],
        )
        self.result: Optional[bool] = None
        self._user_event = Event()

    def task_run(self, actions: UserActionBroker):
        self.result = None
        self._user_event.clear()

        actions.report_audio.register_callback(self.user_callback)
        push_state = PushState(WizardState.TEST_AUDIO)
        actions.push_state(push_state)

        self._user_event.wait()

        actions.drop_state(push_state)
        actions.report_audio.unregister_callback()
        if not self.result:
            self._logger.error("Sound test failed")
            raise SoundTestFailed()

    def user_callback(self, result: bool):
        self.result = result
        self._user_event.set()
