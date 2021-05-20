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
from sl1fw.image.exposure_image import ExposureImage
from sl1fw import defines
from sl1fw.errors.errors import (
    NotUVCalibrated,
    ResinTooLow,
    WarningEscalation,
    ProjectErrorCantRead,
    TiltHomeFailed,
)
from sl1fw.errors.warnings import PrintingDirectlyFromMedia, ResinNotEnough
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.exposure.exposure import Exposure
from sl1fw.states.exposure import ExposureState
from sl1fw.tests.mocks.hardware import Hardware


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
        super().setUp()
        defines.factoryConfigPath = str(
            self.SL1FW_DIR / ".." / "factory" / "factory.toml"
        )
        defines.statsData = str(self.TEMP_DIR / "stats.toml")
        defines.previousPrints = str(self.TEMP_DIR)
        defines.lastProjectHwConfig = self._change_dir(defines.lastProjectHwConfig)
        defines.lastProjectFactoryFile = self._change_dir(
            defines.lastProjectFactoryFile
        )
        defines.lastProjectConfigFile = self._change_dir(defines.lastProjectConfigFile)
        defines.lastProjectPickler = self._change_dir(defines.lastProjectPickler)

        self.hw = self.setupHw()
        self._fake_calibration(self.hw)
        self.runtime_config = RuntimeConfig()
        self.exposure_image = Mock()
        self.exposure_image.__class__ = ExposureImage
        self.exposure_image.__reduce__ = lambda x: (Mock, ())
        self.exposure_image.sync_preloader.return_value = 100

    @staticmethod
    def setupHw() -> Hardware:
        hw = Hardware()
        hw.connect()
        hw.start()
        return hw

    def tearDown(self):
        self.hw.exit()
        super().tearDown()

    def test_exposure_init_not_calibrated(self):
        with self.assertRaises(NotUVCalibrated):
            exposure = Exposure(0, self.setupHw(), self.exposure_image, self.runtime_config)
            exposure.read_project(TestExposure.PROJECT)

    def test_exposure_init(self):
        exposure = Exposure(0, self.hw, self.exposure_image, self.runtime_config)
        exposure.read_project(TestExposure.PROJECT)

    def test_exposure_load(self):
        exposure = Exposure(0, self.hw, self.exposure_image, self.runtime_config)
        exposure.read_project(TestExposure.PROJECT)
        exposure.startProject()

    def test_exposure_start_stop(self):
        exposure = self._run_exposure(self.hw)
        self.assertNotEqual(exposure.state, ExposureState.FAILURE)
        self.assertIsNone(exposure.warning)

    def test_resin_enough(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.get_resin_volume.return_value = defines.resinMaxVolume
        exposure = self._run_exposure(hw)
        self.assertNotEqual(exposure.state, ExposureState.FAILURE)
        self.assertIsNone(exposure.warning)

    def test_resin_warning(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.get_resin_volume.return_value = defines.resinMinVolume + 0.1
        exposure = self._run_exposure(hw)
        self.assertIsInstance(exposure.exception, WarningEscalation)
        # pylint: disable=no-member
        self.assertIsInstance(exposure.exception.warning, ResinNotEnough)

    def test_resin_error(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.get_resin_volume.return_value = defines.resinMinVolume - 0.1
        exposure = self._run_exposure(hw)
        self.assertIsInstance(exposure.exception, ResinTooLow)

    def test_broken_empty_project(self):
        exposure = Exposure(0, self.hw, self.exposure_image, self.runtime_config)
        exposure.read_project(self.BROKEN_EMPTY_PROJECT)
        self.assertIsInstance(exposure.exception, ProjectErrorCantRead)

    def test_stuck_recovery_success(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.tilt.layer_down_wait.side_effect = TiltHomeFailed()
        exposure = Exposure(0, hw, self.exposure_image, self.runtime_config)
        exposure.read_project(TestExposure.PROJECT)
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
                self._exposure_check(exposure)
                self.assertEqual(exposure.state, ExposureState.FINISHED)
                return
            if exposure.state == ExposureState.STUCK:
                hw.tilt.layer_down_wait = None
                exposure.doContinue()
            sleep(1)

        raise TimeoutError("Waiting for exposure failed")

    def test_stuck_recovery_fail(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.tilt.layer_down_wait.side_effect = TiltHomeFailed()
        exposure = Exposure(0, hw, self.exposure_image, self.runtime_config)
        exposure.read_project(TestExposure.PROJECT)
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
                self._exposure_check(exposure)
                self.assertEqual(exposure.state, ExposureState.FAILURE)
                return
            if exposure.state == ExposureState.STUCK:
                hw.tilt.sync_wait.side_effect = TiltHomeFailed()
                exposure.doContinue()
            sleep(1)

        raise TimeoutError("Waiting for exposure failed")

    def _run_exposure(self, hw) -> Exposure:
        exposure = Exposure(0, hw, self.exposure_image, self.runtime_config)
        exposure.read_project(TestExposure.PROJECT)
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
    def _fake_calibration(hw: Hardware):
        hw.config.uvPwm = 250
        hw.config.calibrated = True


if __name__ == "__main__":
    unittest.main()
