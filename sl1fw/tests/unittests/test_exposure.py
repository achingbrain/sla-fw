# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
from time import sleep
from typing import Optional

from unittest.mock import Mock

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.libHardware import Hardware
from sl1fw.screen.screen import Screen
from sl1fw.screen.printer_model import PrinterModelTypes
from sl1fw import defines
from sl1fw.errors.errors import NotUVCalibrated, ResinTooLow, WarningEscalation, ProjectErrorCantRead
from sl1fw.errors.warnings import PrintingDirectlyFromMedia, ResinNotEnough
from sl1fw.libConfig import HwConfig, RuntimeConfig
from sl1fw.libExposure import Exposure
from sl1fw.states.exposure import ExposureState


class TestExposure(Sl1fwTestCase):
    PROJECT = str(Sl1fwTestCase.SAMPLES_DIR / "numbers.sl1")
    BROKEN_EMPTY_PROJECT = str(Sl1fwTestCase.SAMPLES_DIR / "empty_file.sl1")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exposure: Optional[Exposure] = None

    @staticmethod
    def _change_dir(path: str):
        return Path(defines.previousPrints) / Path(path).name

    def setUp(self):
        defines.factoryConfigPath = str(self.SL1FW_DIR / ".." / "factory" / "factory.toml")
        defines.statsData = str(self.TEMP_DIR / "stats.toml")
        defines.previousPrints = str(self.TEMP_DIR)
        defines.lastProjectHwConfig = self._change_dir(defines.lastProjectHwConfig)
        defines.lastProjectFactoryFile = self._change_dir(defines.lastProjectFactoryFile)
        defines.lastProjectConfigFile = self._change_dir(defines.lastProjectConfigFile)
        defines.lastProjectPickler = self._change_dir(defines.lastProjectPickler)

        self.hw_config = HwConfig()
        self.runtime_config = RuntimeConfig()
        self.screen = Mock()
        self.screen.__class__ = Screen
        self.screen.__reduce__ = lambda x: (Mock, ())
        self.screen.blit_image.return_value = 100
        self.screen.printer_model = PrinterModelTypes.SL1.parameters()

    def test_exposure_init_not_calibrated(self):
        with self.assertRaises(NotUVCalibrated):
            Exposure(0, self.hw_config, self._get_hw_mock(), self.screen, self.runtime_config, TestExposure.PROJECT)

    def test_exposure_init(self):
        self._fake_calibration()
        Exposure(0, self.hw_config, self._get_hw_mock(), self.screen, self.runtime_config, TestExposure.PROJECT)

    def test_exposure_load(self):
        self._fake_calibration()
        exposure = Exposure(
            0, self.hw_config, self._get_hw_mock(), self.screen, self.runtime_config, TestExposure.PROJECT
        )
        exposure.startProject()

    def test_exposure_start_stop(self):
        exposure = self._run_exposure(self._get_hw_mock())
        self.assertNotEqual(exposure.state, ExposureState.FAILURE)
        self.assertIsNone(exposure.warning)

    def test_resin_enough(self):
        hw = self._get_hw_mock()
        hw.getResinVolume.return_value = defines.resinMaxVolume
        exposure = self._run_exposure(hw)
        self.assertNotEqual(exposure.state, ExposureState.FAILURE)
        self.assertIsNone(exposure.warning)

    def test_resin_warning(self):
        hw = self._get_hw_mock()
        hw.getResinVolume.return_value = defines.resinMinVolume + 0.1
        exposure = self._run_exposure(hw)
        self.assertIsInstance(exposure.exception, WarningEscalation)
        # pylint: disable=no-member
        self.assertIsInstance(exposure.exception.warning, ResinNotEnough)

    def test_resin_error(self):
        hw = self._get_hw_mock()
        hw.getResinVolume.return_value = defines.resinMinVolume - 0.1
        exposure = self._run_exposure(hw)
        self.assertIsInstance(exposure.exception, ResinTooLow)

    def test_broken_empty_project(self):
        hw = self._get_hw_mock()
        self._fake_calibration()
        exposure = Exposure(0, self.hw_config, hw, self.screen, self.runtime_config, self.BROKEN_EMPTY_PROJECT)
        self.assertIsInstance(exposure.exception, ProjectErrorCantRead)

    def _run_exposure(self, hw) -> Exposure:
        self._fake_calibration()
        exposure = Exposure(0, self.hw_config, hw, self.screen, self.runtime_config, TestExposure.PROJECT)
        exposure.startProject()
        exposure.confirm_print_start()

        for i in range(30):
            print(f"Waiting for exposure {i}, state: ", exposure.state)
            if exposure.state == ExposureState.CHECK_WARNING:
                print(exposure.warning)
                if isinstance(exposure.warning, PrintingDirectlyFromMedia):
                    exposure.confirm_print_warning()
                else:
                    exposure.reject_print_warning()
            if exposure.state in ExposureState.finished_states():
                return self._exposure_check(exposure)
            sleep(1)

        raise TimeoutError("Waiting for exposure failed")

    @staticmethod
    def _exposure_check(exposure: Exposure):
        print("Running exposure check")
        if exposure.state not in ExposureState.finished_states():
            exposure.doExitPrint()
        exposure.waitDone()
        return exposure

    @staticmethod
    def _get_hw_mock():
        hw = Mock()
        hw.__class__ = Hardware
        hw.__reduce__ = lambda self: (Mock, ())
        hw.getMinPwm.return_value = defines.uvLedMeasMinPwm500k
        hw.getUvLedState.return_value = (False, 0)
        hw.getUvStatistics.return_value = (6912,)
        hw.isTiltOnPosition.return_value = True
        hw.isTiltMoving.return_value = False
        hw.getMcTemperatures.return_value = [42, 24, 0, 0]
        hw.getResinVolume.return_value = defines.resinMaxVolume
        hw.towerPositonFailed.return_value = False
        hw.getFansError.return_value = {0: False, 1: False, 2: False}
        return hw

    def _fake_calibration(self):
        self.hw_config.uvPwm = defines.uvLedMeasMinPwm500k
        self.hw_config.calibrated = True


if __name__ == "__main__":
    unittest.main()
