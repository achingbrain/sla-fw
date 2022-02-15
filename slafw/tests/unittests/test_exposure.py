# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
from time import sleep
from typing import Optional

from unittest.mock import Mock

from slafw.tests.base import SlafwTestCase
from slafw.image.exposure_image import ExposureImage
from slafw import defines
from slafw.errors.errors import (
    NotUVCalibrated,
    ResinTooLow,
    ProjectErrorCantRead,
    TiltHomeFailed, WarningEscalation,
)
from slafw.errors.warnings import PrintingDirectlyFromMedia, ResinNotEnough
from slafw.configs.runtime import RuntimeConfig
from slafw.exposure.exposure import Exposure
from slafw.states.exposure import ExposureState
from slafw.tests.mocks.hardware import Hardware

from slafw.project.project import ExposureUserProfile
class TestExposure(SlafwTestCase):
    PROJECT = str(SlafwTestCase.SAMPLES_DIR / "numbers.sl1")
    PROJECT_LAYER_CHANGE = str(SlafwTestCase.SAMPLES_DIR / "layer_change.sl1")
    PROJECT_SUPERSLOW = str(SlafwTestCase.SAMPLES_DIR / "super_slow.sl1")
    PROJECT_LAYER_CHANGE_SAFE = str(SlafwTestCase.SAMPLES_DIR / "layer_change_safe_profile.sl1")
    PROJECT_RESIN_CALIB = str(SlafwTestCase.SAMPLES_DIR / "Resin_calibration_linear_object.sl1")
    BROKEN_EMPTY_PROJECT = str(SlafwTestCase.SAMPLES_DIR / "empty_file.sl1")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exposure: Optional[Exposure] = None

    @staticmethod
    def _change_dir(path: str):
        return Path(defines.previousPrints) / Path(path).name

    def setUp(self):
        super().setUp()
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
        hw.get_resin_volume_async.return_value = defines.resinMaxVolume
        exposure = self._run_exposure(hw)
        self.assertNotEqual(exposure.state, ExposureState.FAILURE)
        self.assertIsNone(exposure.warning)

    def test_resin_warning(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.get_resin_volume_async.return_value = defines.resinMinVolume + 0.1
        exposure = self._run_exposure(hw)
        self.assertIsInstance(exposure.fatal_error, WarningEscalation)
        self.assertIsInstance(exposure.fatal_error.warning, ResinNotEnough)  # pylint: disable=no-member

    def test_resin_error(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.get_resin_volume_async.return_value = defines.resinMinVolume - 0.1
        exposure = self._run_exposure(hw)
        self.assertIsInstance(exposure.fatal_error, ResinTooLow)

    def test_broken_empty_project(self):
        exposure = Exposure(0, self.hw, self.exposure_image, self.runtime_config)
        with self.assertRaises(ProjectErrorCantRead):
            exposure.read_project(self.BROKEN_EMPTY_PROJECT)
        self.assertIsInstance(exposure.fatal_error, ProjectErrorCantRead)

    def test_stuck_recovery_success(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.tilt.layer_down_wait.side_effect = TiltHomeFailed()
        exposure = self._start_exposure(hw)

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
            if exposure.state == ExposureState.POUR_IN_RESIN:
                exposure.confirm_resin_in()
            sleep(1)

        raise TimeoutError("Waiting for exposure failed")

    def test_stuck_recovery_fail(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        hw.tilt.layer_down_wait.side_effect = TiltHomeFailed()
        exposure = self._start_exposure(hw)

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
            if exposure.state == ExposureState.POUR_IN_RESIN:
                exposure.confirm_resin_in()
            sleep(1)

        raise TimeoutError("Waiting for exposure failed")

    def test_resin_refilled(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        fake_resin_volume = 100.0
        hw.get_resin_volume_async.return_value = fake_resin_volume
        exposure = self._start_exposure(hw)
        feedme_done = False

        for i in range(60):
            print(f"Waiting for exposure {i}, state: ", exposure.state)
            if exposure.state == ExposureState.PRINTING:
                if not feedme_done:
                    self.assertLess(exposure.resin_volume, defines.resinMaxVolume)
                    exposure.doFeedMe()
                    feedme_done = True
                else:
                    self.assertEqual(exposure.resin_volume, defines.resinMaxVolume)
            if exposure.state == ExposureState.FEED_ME:
                exposure.doContinue()
            if exposure.state in ExposureState.finished_states():
                self.assertNotEqual(exposure.state, ExposureState.FAILURE)
                return
            if exposure.state == ExposureState.POUR_IN_RESIN:
                exposure.confirm_resin_in()
            sleep(0.5)

        raise TimeoutError("Waiting for exposure failed")

    def test_resin_not_refilled(self):
        hw = self.setupHw()
        self._fake_calibration(hw)
        fake_resin_volume = 100.0
        hw.get_resin_volume.return_value = fake_resin_volume
        exposure = self._start_exposure(hw)
        feedme_done = False

        for i in range(60):
            print(f"Waiting for exposure {i}, state: ", exposure.state)
            if exposure.state == ExposureState.PRINTING:
                if not feedme_done:
                    exposure.doFeedMe()
                    feedme_done = True
                else:
                    self.assertLessEqual(fake_resin_volume, exposure.resin_volume)
            if exposure.state == ExposureState.FEED_ME:
                exposure.doBack()
            if exposure.state == ExposureState.POUR_IN_RESIN:
                exposure.confirm_resin_in()
            if exposure.state in ExposureState.finished_states():
                self.assertNotEqual(exposure.state, ExposureState.FAILURE)
                return
            sleep(0.5)

        raise TimeoutError("Waiting for exposure failed")

    def test_exposure_force_slow_tilt(self):
        defines.livePreviewImage = str(self.TEMP_DIR / "live.png")
        defines.displayUsageData = str(self.TEMP_DIR / "display_usage.npz")
        hw = self.setupHw()
        self._fake_calibration(hw)
        print(hw.config.limit4fast)
        hw.config.limit4fast = 45
        exposure_image = ExposureImage(hw)
        exposure_image.start()

        hw.config.forceSlowTiltHeight = 0  # do not force any extra slow tilts
        exposure = self._run_exposure(hw, TestExposure.PROJECT_LAYER_CHANGE, exposure_image)
        self.assertEqual(exposure.state, ExposureState.FINISHED)
        # 13 slow layers at beginning + 4 large layers in project
        self.assertEqual(exposure.slow_layers_done, 13 + 4)

        hw.config.forceSlowTiltHeight = 100000  # 100 um -> force 2 slow layers
        exposure = self._run_exposure(hw, TestExposure.PROJECT_LAYER_CHANGE, exposure_image)
        self.assertEqual(exposure.state, ExposureState.FINISHED)
        # 13 slow layers at beginning + 4 large layers in project + 4 layers after area change
        self.assertEqual(exposure.slow_layers_done, 13 + 4 + 4)

    def test_exposure_superslow_tilt(self):
        """Make sure that all superslow layers are counted and no other counters are incremented"""
        defines.livePreviewImage = str(self.TEMP_DIR / "live.png")
        defines.displayUsageData = str(self.TEMP_DIR / "display_usage.npz")
        hw = self.setupHw()
        self._fake_calibration(hw)
        print(hw.config.limit4fast)
        hw.config.limit4fast = 45
        exposure_image = ExposureImage(hw)
        exposure_image.start()

        hw.config.forceSlowTiltHeight = 0  # do not force any extra slow tilts
        exposure = self._run_exposure(hw, TestExposure.PROJECT_SUPERSLOW, exposure_image, timeout_s=200)
        self.assertEqual(exposure.state, ExposureState.FINISHED)
        self.assertEqual(exposure.project.exposure_user_profile, ExposureUserProfile.SUPERSLOW, "The project must have the SUPERSLOW profile selected.")
        self.assertEqual(exposure.super_slow_layers_done, exposure.project.total_layers, "All layers should be superslow")
        self.assertEqual(exposure.slow_layers_done, 0, "There should be no slow layers if SUPERSLOW profile is selected")
        t_first_estimate = exposure.estimated_total_time_ms

        # Assert that SUPERSLOW beats attempts to force slow layers
        hw.config.forceSlowTiltHeight = 100000  # 100 um -> force 2 slow layers
        exposure = self._run_exposure(hw, TestExposure.PROJECT_SUPERSLOW, exposure_image, timeout_s=200)
        self.assertEqual(exposure.state, ExposureState.FINISHED)
        self.assertEqual(exposure.project.exposure_user_profile, ExposureUserProfile.SUPERSLOW, "The project must have the SUPERSLOW profile selected.")
        self.assertEqual(exposure.super_slow_layers_done, exposure.project.total_layers)
        self.assertEqual(exposure.slow_layers_done, 0, "There should be no slow layers if SUPERSLOW profile is selected")
        t_second_estimate = exposure.estimated_total_time_ms

        self.assertEqual(t_first_estimate, t_second_estimate, "Estimated time should be the same - slow layers should be ignored")

    def test_superslow_time_estimate(self):
        """Make sure that SUPERSLOW time estimate are lower than default(with normal slow layers)"""
        defines.livePreviewImage = str(self.TEMP_DIR / "live.png")
        defines.displayUsageData = str(self.TEMP_DIR / "display_usage.npz")
        hw = self.setupHw()
        self._fake_calibration(hw)
        print(hw.config.limit4fast)
        hw.config.limit4fast = 45
        exposure_image = ExposureImage(hw)
        exposure_image.start()

        # Run SUPERSLOW project
        exposure_superslow = self._run_exposure(hw, TestExposure.PROJECT_SUPERSLOW, exposure_image, timeout_s=200)
        self.assertEqual(exposure_superslow.state, ExposureState.FINISHED)
        t_superslow = exposure_superslow.estimated_total_time_ms

        # It's the same project, but with default user profile, for comparison
        exposure = self._run_exposure(hw, TestExposure.PROJECT_LAYER_CHANGE, exposure_image, timeout_s=50)
        self.assertEqual(exposure.state, ExposureState.FINISHED)
        t_normal = exposure.estimated_total_time_ms
        self.assertLess(t_normal, t_superslow)
        self.assertEqual(exposure.super_slow_layers_done, 0, "There should be no superslow layers when printing with default user profile")

    def test_exposure_user_profile(self):
        self.hw.config.limit4fast = 100
        exposure = self._run_exposure(self.hw, TestExposure.PROJECT_LAYER_CHANGE)
        self.assertEqual(exposure.state, ExposureState.FINISHED)
        # 13 slow layers at beginning
        self.assertEqual(exposure.slow_layers_done, 13)
        self.assertEqual(205040, exposure.estimate_total_time_ms())

        defines.exposure_safe_delay_before = 0.1    # 0.01 s
        exposure = self._run_exposure(self.hw, TestExposure.PROJECT_LAYER_CHANGE_SAFE)
        self.assertEqual(exposure.state, ExposureState.FINISHED)
        self.assertEqual(exposure.slow_layers_done, exposure.project.total_layers)
        delay_time = exposure.project.total_layers * defines.exposure_safe_delay_before * 100
        force_slow_time = exposure.project._layers_fast * (self.hw.config.tiltSlowTime - self.hw.config.tiltFastTime)\
                          * 1000  # pylint: disable = protected-access
        self.assertEqual(201040 + delay_time + force_slow_time, exposure.estimate_total_time_ms())

    def _start_exposure(self, hw, project = None, expo_img = None) -> Exposure:
        if project is None:
            project = TestExposure.PROJECT
        if expo_img is None:
            expo_img = self.exposure_image
        exposure = Exposure(0, hw, expo_img, self.runtime_config)
        exposure.read_project(project)
        exposure.startProject()
        exposure.confirm_print_start()
        return exposure

    def _run_exposure(self, hw, project=None, expo_img=None, timeout_s=50) -> Exposure:
        exposure = self._start_exposure(hw, project, expo_img)

        for i in range(timeout_s):
            print(f"Waiting for exposure {i}, state: ", exposure.state)
            if exposure.state == ExposureState.CHECK_WARNING:
                print(exposure.warning)
                if isinstance(exposure.warning, PrintingDirectlyFromMedia):
                    exposure.confirm_print_warning()
                else:
                    exposure.reject_print_warning()
            if exposure.state in ExposureState.finished_states():
                return self._exposure_check(exposure)
            if exposure.state == ExposureState.POUR_IN_RESIN:
                exposure.confirm_resin_in()
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
