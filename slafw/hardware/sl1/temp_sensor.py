# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import abstractmethod
from typing import Optional, List

from slafw import defines

from slafw.configs.hw import HwConfig
from slafw.errors.errors import UVLEDTempSensorFailed, AmbientTempSensorFailed
from slafw.hardware.base.temp_sensor import TempSensor
from slafw.motion_controller.controller import MotionController


class SL1TempSensor(TempSensor):
    # pylint: disable = too-many-arguments
    def __init__(
        self,
        name: str,
        mcc: MotionController,
        index: int,
        minimal: Optional[float] = None,
        maximal: Optional[float] = None,
        critical: Optional[float] = None,
        hysteresis: float = 0,
    ):
        super().__init__(name=name, minimal=minimal, maximal=maximal, critical=critical, hysteresis=hysteresis)
        self._index = index
        self._value = None

        mcc.temps_changed.connect(self._on_mc_temps_changed)
        mcc.value_refresh_failed.connect(self._on_value_refresh_failed)

    @property
    @abstractmethod
    def value(self) -> float:
        ...

    def _on_mc_temps_changed(self, temperatures: List[int]):
        raw_value = temperatures[self._index]
        if raw_value is not None and raw_value < 0:
            # TODO: Can we check something else than "< 0" ?
            value = None
        else:
            value = raw_value

        if value != self._value:
            self._value = value
            self.value_changed.emit(self.value)

    def _on_value_refresh_failed(self):
        self.value_changed.emit(None)


class SL1XTempSensorUV(SL1TempSensor):
    def __init__(
        self,
        mcc: MotionController,
        index: int,
        config: HwConfig,
    ):
        super().__init__(
            name="UV LED",
            mcc=mcc,
            index=index,
            minimal=config.rpmControlUvLedMinTemp,
            maximal=config.rpmControlUvLedMaxTemp,
            critical=defines.maxUVTemp,
            hysteresis=defines.uv_temp_hysteresis,
        )

    @property
    def value(self) -> float:
        if self._value is None:
            raise UVLEDTempSensorFailed()
        return self._value


class SL1TempSensorUV(SL1XTempSensorUV):
    # pylint: disable = too-many-arguments
    def __init__(self, mcc: MotionController, config: HwConfig):
        super().__init__(mcc=mcc, index=0, config=config)


class SL1STempSensorUV(SL1XTempSensorUV):
    # pylint: disable = too-many-arguments
    def __init__(self, mcc: MotionController, config: HwConfig):
        super().__init__(mcc=mcc, index=2, config=config)


class SL1TempSensorAmbient(SL1TempSensor):
    # pylint: disable = too-many-arguments
    def __init__(self, mcc: MotionController):
        super().__init__(
            name="Ambient",
            mcc=mcc,
            index=1,
            minimal=defines.minAmbientTemp,
            maximal=defines.maxAmbientTemp,
        )

    @property
    def value(self) -> float:
        if self._value is None:
            raise AmbientTempSensorFailed()
        return self._value
