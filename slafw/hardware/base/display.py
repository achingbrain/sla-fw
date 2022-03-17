# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import abstractmethod, ABC

from PySignal import Signal

from slafw.hardware.base.component import HardwareComponent


class PrintDisplay(HardwareComponent, ABC):
    def __init__(self):
        super().__init__("Print Display")
        self.usage_s_changed = Signal()

    @abstractmethod
    def start_counting_usage(self):
        """
        Start counting display usage
        """

    @abstractmethod
    def stop_counting_usage(self):
        """
        Stop counting UV display usage
        """

    @property
    @abstractmethod
    def usage_s(self) -> int:
        """
        How long has the UV LED been used
        """

    @abstractmethod
    def save_usage(self):
        """
        Store usage to permanent storage
        """

    @abstractmethod
    def clear_usage(self):
        """
        Clear usage

        Use this when UV LED is replaced
        """

    # TODO: Serial number property
