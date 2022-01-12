# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime, timedelta

from PySignal import Signal

from slafw.states.exposure import ExposureState, ExposureCheck, ExposureCheckResult
from slafw.tests.mocks.hardware import Hardware
from slafw.tests.mocks.project import Project


class Exposure:
    # pylint: disable = too-many-instance-attributes
    def __init__(self):
        self.state = ExposureState.PRINTING
        self.instance_id = 1
        self.change = Signal()
        self.hw = Hardware()
        self.project = Project()
        self.progress = 0
        self.exception = None
        self.low_resin = False
        self.resin_volume = 42
        self.remain_resin_ml = 142
        self.resin_count = 4
        self.warn_resin = False
        self.estimated_total_time_ms = 123456
        self.actual_layer = 42
        self.remaining_wait_sec = 4242
        self.printStartTime = datetime.utcnow()
        self.printEndTime = datetime.utcnow() + timedelta(hours=10)
        self.tower_position_nm = 424242
        self.warning = None
        self.exposure_end = self.printEndTime
        self.check_results = {
            ExposureCheck.FAN: ExposureCheckResult.RUNNING,
            ExposureCheck.PROJECT: ExposureCheckResult.RUNNING,
            ExposureCheck.RESIN: ExposureCheckResult.SCHEDULED,
            ExposureCheck.COVER: ExposureCheckResult.DISABLED,
            ExposureCheck.START_POSITIONS: ExposureCheckResult.SUCCESS,
        }

    def expected_finish_timestamp(self):
        return datetime.utcnow() + timedelta(milliseconds=self.estimate_remain_time_ms())

    def estimate_remain_time_ms(self):
        return self.project.exposure_time_ms * (self.project.total_layers - self.actual_layer)

    def set_state(self, state):
        self.state = state
        self.change.emit("state", state)
        self.change.emit("check_results", self.check_results)
