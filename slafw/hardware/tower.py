# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from functools import cached_property

from slafw.configs.unit import Nm
from slafw.errors.errors import TowerMoveFailed, TowerHomeFailed
from slafw.hardware.axis import Axis


class Tower(Axis):

    @property
    def name(self) -> str:
        return "tower"

    @cached_property
    def sensitivity(self) -> int:
        return self._config.towerSensitivity

    @cached_property
    def home_position(self) -> Nm:
        return self._config.tower_height_nm

    @cached_property
    def config_height_position(self) -> Nm:
        return self.home_position

    # FIXME: move to the config
    @cached_property
    def min_nm(self) -> Nm:
        return -(self._config.max_tower_height_mm + Nm(5)) * 1_000_000

    # FIXME: move to the config
    @cached_property
    def above_surface_nm(self) -> Nm:
        return -(self._config.max_tower_height_mm - Nm(5)) * 1_000_000

    # FIXME: move to the config
    @cached_property
    def max_nm(self) -> Nm:
        return 2 * self._config.max_tower_height_mm * 1_000_000

    # FIXME: move to the config
    @cached_property
    def end_nm(self) -> Nm:
        return self._config.max_tower_height_mm * 1_000_000

    # FIXME: move to the config
    @cached_property
    def calib_pos_nm(self) -> Nm:  # pylint: disable=no-self-use
        return Nm(1_000_000)

    # FIXME: move to the config
    @cached_property
    def resin_start_pos_nm(self) -> Nm:  # pylint: disable=no-self-use
        return Nm(36_000_000)

    # FIXME: move to the config
    @cached_property
    def resin_end_pos_nm(self) -> Nm:  # pylint: disable=no-self-use
        return Nm(1_000_000)

    def _move_api_min(self) -> None:
        self.move(self._config.calib_tower_offset_nm)

    def _move_api_max(self) -> None:
        self.move(self._config.tower_height_nm)

    @staticmethod
    def _raise_move_failed():
        raise TowerMoveFailed()

    @staticmethod
    def _raise_home_failed():
        raise TowerHomeFailed()
