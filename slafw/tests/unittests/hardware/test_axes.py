# This file is part of the SLA firmware
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import unittest
from abc import ABC, abstractmethod
from time import sleep
from typing import List, Tuple
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, PropertyMock, patch

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.errors.errors import TiltPositionFailed, TowerPositionFailed, \
    TowerMoveFailed, TiltMoveFailed, TowerHomeFailed, TiltHomeFailed
from slafw.hardware.axis import Axis, HomingStatus, AxisProfileBase

from slafw.hardware.sl1.tilt import TiltProfile, TiltSL1
from slafw.hardware.sl1.tower import TowerSL1, TowerProfile
from slafw.motion_controller.controller import MotionController
from slafw.tests.base import SlafwTestCase

# pylint: disable = protected-access
# pylint: disable = too-many-public-methods


class DoNotRunTestDirectlyFromBaseClass:
    # pylint: disable = too-few-public-methods
    class BaseSL1AxisTest(SlafwTestCase, IsolatedAsyncioTestCase, ABC):
        axis: Axis  # reference to axis object (TiltSL1, TowerSL1)
        pos: int  # arbitrary position used for testing moves
        fullstep_offset: Tuple[int]  # tower is set to 1/16 ustepping, tilt is set to 1/32

        def setUp(self) -> None:
            super().setUp()
            self.config = HwConfig()
            self.power_led = Mock()
            self.mcc = MotionController(defines.motionControlDevice)
            self.mcc.open()

        def tearDown(self) -> None:
            self.mcc.exit()
            super().tearDown()

        def test_position(self):
            positions = [self.pos, 0]
            for position in positions:
                self.axis.position = position
                self.assertEqual(position, self.axis.position)
            self.axis._move_api_max()
            with self.assertRaises((TiltPositionFailed, TowerPositionFailed)):
                self.axis.position = position

        def test_basic_movement(self):
            self.assertFalse(self.axis.moving)
            self.axis.position = 0
            self.axis.move(self.pos)
            self.assertTrue(self.axis.moving)
            while self.axis.moving:
                self.assertFalse(self.axis.on_target_position)
                sleep(0.1)
            self.assertFalse(self.axis.moving)
            self.assertTrue(self.axis.on_target_position)
            self.assertEqual(self.axis.position, self.pos)

        # TODO: use unit checking nm X ustep
        def test_ensure_position_async(self):
            path = "slafw.hardware.sl1." + self.axis.name + "." + self.axis.name.capitalize() + "SL1.position"
            pos = self.pos

            # normal behaviour
            self.axis.position = 0
            self.axis.move(pos)
            asyncio.run(self.axis.ensure_position_async())
            self.assertFalse(self.axis.moving)
            self.assertEqual(self.axis.position, pos)

            # successful retries 2
            self.axis.position = 0
            with patch(path, new_callable=PropertyMock) as mock_position:
                mock_position.side_effect = [1, 1, 1, 2, 2, 2, pos, pos]
                self.axis.move(pos)
                asyncio.run(self.axis.ensure_position_async(retries=2))
                self.assertFalse(self.axis.moving)
            self.assertEqual(self.axis.position, pos)

            # maximum tries reached
            self.axis.position = 0
            with patch(path, new_callable=PropertyMock) as mock_position:
                mock_position.side_effect = [1, 1, 1, 2, 2, 2, pos, pos]
                self.axis.move(pos)
                with self.assertRaises((TowerMoveFailed, TiltMoveFailed)):
                    asyncio.run(self.axis.ensure_position_async(retries=1))
                self.assertFalse(self.axis.moving)

        def test_move_ensure(self):
            self.axis.position = 0
            self.axis.move_ensure(self.pos)
            self.assertFalse(self.axis.moving)
            self.assertEqual(self.axis.position, self.pos)

        def test_move_api_stop(self):
            self.axis.position = 0
            current_profile = self.axis.profile_id
            self.axis.move_api(0)
            self.assertFalse(self.axis.moving)
            self.assertEqual(0, self.axis.position)
            self.assertEqual(current_profile, self.axis.profile_id)

        def _test_move_api_up_down(self, speed: int):
            self.axis.position = 0
            current_profile = self.axis.profile_id
            self.axis.move_api(speed)
            self.assertTrue(self.axis.moving)
            self.assertLess(0, self.axis.position)
            self.assertNotEqual(current_profile, self.axis.profile_id)
            current_profile = self.axis.profile_id
            self.axis.stop()
            self.axis.position = self.pos
            self.axis.move_api(-speed)
            self.assertTrue(self.axis.moving)
            self.assertGreater(self.pos, self.axis.position)
            self.assertEqual(current_profile, self.axis.profile_id)

        def test_move_api_slow_up_down(self):
            self._test_move_api_up_down(1)

        def test_move_api_fast_up_down(self):
            self._test_move_api_up_down(2)

        # TODO: fix mc-fw to mimic real HW accurately. Now moves tilt: +31 -32 steps, tower +-16 steps
        def test_move_api_goto_fullstep(self):
            # fullstep up
            self.axis.position = 0
            self.axis.move_api(2)
            sleep(0.1)
            self.axis.stop()
            position = self.axis.position
            self.axis.move_api(0, fullstep=True)
            while self.axis.moving:
                sleep(0.1)
            self.assertEqual(position + self.fullstep_offset[0], self.axis.position)

            #fullstep down
            self.axis.position = self.pos
            self.axis.move_api(-2)
            sleep(0.1)
            self.axis.stop()
            position = self.axis.position
            self.axis.move_api(0, fullstep=True)
            while self.axis.moving:
                sleep(0.1)
            self.assertEqual(position + self.fullstep_offset[1], self.axis.position)

        def stop(self) -> None:
            self.axis.position = 0
            self.axis.move(1000)
            while self.axis.moving:
                self.axis.stop()
                self.assertFalse(self.axis.moving)
                self.assertGreater(0, self.axis.position)

        def test_release(self):
            self.axis.sync_wait()
            self.axis.position = 0
            self.axis.move_api(2)
            self.axis.release()
            self.assertFalse(self.axis.synced)

        # TODO: fix mc-fw to mimic real HW accurately. Now moves tilt: +31 -32 steps, tower +-16 steps
        def test_go_to_fullstep(self):
            self.axis.position = 0
            self.axis.go_to_fullstep(go_up=True)
            self.assertEqual(self.axis.position, self.fullstep_offset[0])
            self.axis.position = 0
            self.axis.go_to_fullstep(go_up=False)
            self.assertEqual(self.axis.position, self.fullstep_offset[1])

        def test_sync(self):
            self.assertEqual(HomingStatus.UNKNOWN, self.axis.homing_status)
            self.axis.sync()
            self.assertLess(HomingStatus.SYNCED.value, self.axis.homing_status.value)
            while self.axis.moving:
                sleep(0.1)
            self.assertEqual(HomingStatus.SYNCED, self.axis.homing_status)
            self.assertTrue(self.axis.synced)
            self.axis.release()
            self.assertFalse(self.axis.synced)
            self.assertEqual(HomingStatus.UNKNOWN, self.axis.homing_status)

        def sync_wait(self):
            self.axis.sync_wait()
            self.assertEqual(HomingStatus.SYNCED, self.axis.homing_status)

        def test_sync_wait_async(self):
            path = "slafw.hardware.sl1." + self.axis.name + "." + self.axis.name.capitalize() + "SL1.homing_status"
            # successful rehome
            with patch(path, new_callable=PropertyMock) as mock_status:
                mock_status.side_effect = [HomingStatus.BLOCKED_AXIS, HomingStatus.BLOCKED_AXIS, HomingStatus.SYNCED]
                asyncio.run(self.axis.sync_wait_async(retries=2))
                self.assertFalse(self.axis.moving)
            self.assertTrue(self.axis.synced)

            # maximum tries reached
            with patch(path, new_callable=PropertyMock) as mock_status:
                mock_status.side_effect = [HomingStatus.BLOCKED_AXIS, HomingStatus.BLOCKED_AXIS, HomingStatus.SYNCED]
                with self.assertRaises((TiltHomeFailed, TowerHomeFailed)):
                    asyncio.run(self.axis.sync_wait_async(retries=1))
                self.assertFalse(self.axis.moving)


        def test_home_calibrate_wait(self):
            self.assertEqual(HomingStatus.UNKNOWN, self.axis.homing_status)
            self.axis.home_calibrate_wait()
            self.assertEqual(HomingStatus.SYNCED, self.axis.homing_status)
            # TODO: improve mc-code to test the result of calibration

        async def test_verify_async_unknown(self) -> None:
            self.assertEqual(HomingStatus.UNKNOWN, self.axis.homing_status)
            task = asyncio.create_task(self.axis.verify_async())
            self.assertLess(self.axis.homing_status.value, HomingStatus.SYNCED.value)
            await task
            self.assertEqual(self.axis.config_height_position, self.axis.position)

        async def test_verify_async_already_synced(self) -> None:
            await self.axis.sync_wait_async()
            self.assertEqual(HomingStatus.SYNCED, self.axis.homing_status)
            task = self.axis.verify_async()
            self.assertEqual(HomingStatus.SYNCED, self.axis.homing_status)
            await task
            self.assertEqual(self.axis.config_height_position, self.axis.position)
            # already home axis does not home. Just move to top position

        def profile_names(self) -> List[str]:
            """list of all profile names of given axis"""

        @abstractmethod
        def _test_profile_id(self) -> List[AxisProfileBase]:
            """get list of profiles"""

        def test_profile_id(self):
            profiles = self._test_profile_id()
            for profile in profiles:
                self.axis.profile_id = profile
                self.assertEqual(profile, self.axis.profile_id)

        def test_profile(self):
            test_profile = [12345, 23456, 234, 345, 28, 8, 1234]
            self.assertNotEqual(test_profile, self.axis.profile)
            self.axis.profile = test_profile
            self.assertEqual(test_profile, self.axis.profile)

        def test_profiles(self):
            profiles = self.axis.profiles
            self.assertEqual(type([]), type(profiles))
            self.assertEqual(8, len(profiles))  # all except temp
            for profile in profiles:
                self.assertEqual(7, len(profile))
                self.assertEqual(type([int]), type(profile))


class TestTilt(DoNotRunTestDirectlyFromBaseClass.BaseSL1AxisTest):

    def setUp(self):
        super().setUp()
        tower = TowerSL1(self.mcc, self.config, self.power_led)
        self.axis = TiltSL1(self.mcc, self.config, self.power_led, tower)
        self.pos = self.axis.config_height_position / 4 # aprox 1000 usteps
        self.fullstep_offset = (31, -32)

    def test_name(self) -> str:
        self.assertEqual(self.axis.name, "tilt")

    def test_home_position(self) -> int:
        self.assertEqual(self.axis.home_position, 0)

    def test_config_height_position(self) -> int:
        self.assertEqual(self.axis.config_height_position, self.config.tiltHeight)

    def test_raise_move_failed(self):
        with self.assertRaises(TiltMoveFailed):
            self.axis._raise_move_failed()

    def test_raise_home_failed(self):
        with self.assertRaises(TiltHomeFailed):
            self.axis._raise_home_failed()

    def test_move_api_min(self) -> None:
        self.axis.position = 1000
        self.axis._move_api_min()
        self.assertTrue(self.axis.moving)
        self.assertEqual(self.axis._target_position, self.axis.home_position)

    def test_move_api_max(self) -> None:
        self.axis._move_api_max()
        self.assertTrue(self.axis.moving)
        self.assertEqual(self.axis._target_position, self.config.tiltMax)

    def test_move_api_get_profile(self):
        self.assertEqual(self.axis._move_api_get_profile(1), TiltProfile.moveSlow)
        self.assertEqual(self.axis._move_api_get_profile(2), TiltProfile.homingFast)

    def _test_profile_id(self):
        return [TiltProfile.moveFast, TiltProfile.moveSlow]

    def test_profile_names(self):
        self.assertEqual(
            [
                "temp",
                "homingFast",
                "homingSlow",
                "moveFast",
                "moveSlow",
                "layerMoveSlow",
                "layerRelease",
                "layerMoveFast",
                "reserved2",
            ],
            self.axis.profile_names,
        )

    def test_sensitivity(self):
        self.assertEqual(self.axis.sensitivity, self.config.tiltSensitivity)

    # TODO: test better
    def test_layer_up(self):
        self.axis.layer_up_wait()
        self.assertAlmostEqual(self.axis.config_height_position, self.axis.position)

    # TODO test better
    def test_layer_down(self):
        asyncio.run(self.axis.layer_down_wait_async())
        self.assertLessEqual(abs(self.axis.position), defines.tiltHomingTolerance)

    def test_stir_resin(self):
        asyncio.run(self.axis.stir_resin_async())
        self.assertTrue(self.axis.synced)
        self.assertEqual(0, self.axis.position)


class TestTower(DoNotRunTestDirectlyFromBaseClass.BaseSL1AxisTest):

    def setUp(self):
        super().setUp()
        self.axis = TowerSL1(self.mcc, self.config, self.power_led)
        self.pos = self.axis.resin_start_pos_nm
        self.fullstep_offset = (self.config.tower_microsteps_to_nm(16), self.config.tower_microsteps_to_nm(-16))

    def test_name(self) -> str:
        self.assertEqual(self.axis.name, "tower")

    def test_home_position(self) -> int:
        self.assertEqual(self.axis.home_position, self.config.tower_height_nm)

    def test_config_height_position(self) -> int:
        self.assertEqual(self.axis.home_position, self.config.tower_height_nm)

    def test_raise_move_failed(self):
        with self.assertRaises(TowerMoveFailed):
            self.axis._raise_move_failed()

    def test_raise_home_failed(self):
        with self.assertRaises(TowerHomeFailed):
            self.axis._raise_home_failed()

    def test_move_api_min(self) -> None:
        self.axis._move_api_min()
        self.assertTrue(self.axis.moving)
        self.assertEqual(self.axis._target_position, self.config.calib_tower_offset_nm)

    def test_move_api_max(self) -> None:
        self.axis._move_api_max()
        self.assertTrue(self.axis.moving)
        self.assertEqual(self.axis._target_position, self.config.tower_height_nm)

    def test_move_api_get_profile(self):
        self.assertEqual(self.axis._move_api_get_profile(1), TowerProfile.moveSlow)
        self.assertEqual(self.axis._move_api_get_profile(2), TowerProfile.homingFast)

    def _test_profile_id(self):
        return [TowerProfile.moveFast, TowerProfile.moveSlow]

    def test_profile_names(self):
        self.assertEqual(
            [
                "temp",
                "homingFast",
                "homingSlow",
                "moveFast",
                "moveSlow",
                "layer",
                "layerMove",
                "superSlow",
                "resinSensor",
            ],
            self.axis.profile_names,
        )

    def test_sensitivity(self):
        self.assertEqual(self.axis.sensitivity, self.config.tiltSensitivity)

if __name__ == "__main__":
    unittest.main()
