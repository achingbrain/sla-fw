# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw.hardware.base.display import PrintDisplay


class MockPrintDisplay(PrintDisplay):
    def __init__(self):
        super().__init__()
        self._usage_s = 3600

    def start_counting_usage(self):
        pass

    def stop_counting_usage(self):
        pass

    @property
    def usage_s(self) -> int:
        return self._usage_s

    def save_usage(self):
        pass

    def clear_usage(self):
        self._usage_s = 0
