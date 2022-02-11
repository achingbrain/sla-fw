# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from slafw import defines


class Fan:
    # pylint: disable = too-many-arguments
    # pylint: disable = too-many-instance-attributes
    def __init__(self, name: str, max_rpm: int, default_rpm: int,
                 enabled: bool, auto_control: bool = False):
        super().__init__()
        self.name = name
        self.__min_rpm = defines.fanMinRPM
        self.__max_rpm = max_rpm
        self.__default_rpm = default_rpm
        self.__target_rpm = default_rpm
        self.__enabled = enabled
        # TODO add periodic callback on the background
        # self.__error = False
        # self.__realRpm = 0
        self.__auto_control: bool = auto_control

    @property
    def target_rpm(self) -> int:
        return self.__target_rpm

    @target_rpm.setter
    def target_rpm(self, val):
        self.__enabled = True
        if val < self.__min_rpm:
            self.__target_rpm = self.__min_rpm
            self.__enabled = False
        elif val > self.__max_rpm:
            self.__target_rpm = self.__max_rpm
        else:
            self.__target_rpm = val

    @property
    def default_rpm(self) -> int:
        return self.__default_rpm

    @default_rpm.setter
    def default_rpm(self, value: int):
        self.__default_rpm = value

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @enabled.setter
    def enabled(self, value: bool):
        self.__enabled = value

    @property
    def auto_control(self):
        return self.__auto_control

    @auto_control.setter
    def auto_control(self, value: bool):
        self.__auto_control = value

    # TODO methods to save, load, reset to defaults
