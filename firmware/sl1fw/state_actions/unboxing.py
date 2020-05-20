# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from threading import Thread
from time import sleep
from typing import Optional

from PySignal import Signal

from sl1fw.api.decorators import state_checked
from sl1fw.libConfig import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.states.unboxing import UnboxingState


class Unboxing(Thread):
    """
    The class responsible of unboxing process handling
    """

    def __init__(self, hw: Hardware, hw_config: HwConfig, kit_override: Optional[bool] = None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.hw = hw
        self.config = hw_config
        self._state = UnboxingState.INIT
        self.state_changed = Signal()
        self._kit_override = kit_override

    @property
    def state(self) -> UnboxingState:
        return self._state

    @state.setter
    def state(self, value: UnboxingState) -> None:
        self.logger.info("Unboxing state: %s", value)
        self._state = value
        self.state_changed.emit()

    @state_checked(UnboxingState.INIT)
    def start(self):
        self._state = UnboxingState.INIT
        super().start()

    @state_checked(UnboxingState.STICKER)
    def sticker_removed_cover_open(self):
        self.state = UnboxingState.COVER_CLOSED

    @state_checked(UnboxingState.SIDE_FOAM)
    def side_foam_removed(self):
        self.state = UnboxingState.MOVING_TO_TANK

    @state_checked(UnboxingState.TANK_FOAM)
    def tank_foam_removed(self):
        self.state = UnboxingState.DISPLAY_FOIL

    @state_checked(UnboxingState.DISPLAY_FOIL)
    def display_foil_removed(self):
        self.config.showUnboxing = False
        self.config.write()
        self.state = UnboxingState.FINISHED
        self._exit()

    def run(self):
        self.logger.info("Unboxing worker started")
        while self.state not in [UnboxingState.FINISHED, UnboxingState.CANCELED]:
            if self.state == UnboxingState.INIT:
                self.hw.beepRepeat(1)
                if self._kit_override or (self._kit_override is None and self.hw.isKit):
                    self.state = UnboxingState.DISPLAY_FOIL
                else:
                    self.state = UnboxingState.STICKER
            elif self.state == UnboxingState.COVER_CLOSED:
                self.hw.powerLed("warn")
                if self.config.coverCheck and self.hw.isCoverClosed():
                    self.hw.beepAlarm(3)
                else:
                    self.state = UnboxingState.MOVING_TO_FOAM
            elif self.state == UnboxingState.MOVING_TO_FOAM:
                self.hw.setTowerPosition(0)
                self.hw.setTowerProfile("homingFast")
                self.hw.towerMoveAbsolute(self.config.calcMicroSteps(30))
                while self.hw.isTowerMoving() and self.state != UnboxingState.CANCELED:
                    sleep(0.5)
                self.hw.motorsRelease()
                self.hw.powerLed("normal")
                self.state = UnboxingState.SIDE_FOAM
            elif self.state == UnboxingState.MOVING_TO_TANK:
                self.hw.powerLed("warn")
                self.hw.towerSyncWait(retries=3)  # Let this fail fast, allow for proper tower synced check
                self.hw.motorsRelease()
                self.hw.powerLed("normal")
                self.state = UnboxingState.TANK_FOAM
            sleep(0.5)
        self.logger.info("Unboxing worker ended")

    def cancel(self):
        self.state = UnboxingState.CANCELED
        self.config.showUnboxing = False
        self.config.write()
        self._exit()

    def _exit(self):
        self.join()
