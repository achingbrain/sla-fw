# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# import asyncio
import unittest
# from unittest import TestCase
# from unittest.mock import Mock
#
# from mock import MagicMock
#
# from sl1fw.states.wizard import WizardState
# from sl1fw.wizard.actions import UserActionBroker
# from sl1fw.wizard.checks.base import Check, WizardCheckType
# from sl1fw.wizard.groups.base import CheckGroup
# from sl1fw.wizard.setup import Configuration, PlatformSetup, TankSetup
# from sl1fw.wizard.wizard import Wizard

# Requires AsyncMock from python 3.8
# class TestGroup(CheckGroup):
#     setup = AsyncMock()
#     pass
#
#
# class TestWizardInfrastructure(TestCase):
#     # pylint: disable=no-self-use
#
#     def test_wizard_group_run(self):
#         group = AsyncMock()
#         group.checks = []
#         # group.setup.return_value = None
#
#         wizard = Wizard([group])
#         self.assertEqual(WizardState.INIT, wizard.state)
#         wizard.start()
#         wizard.join()
#
#         self.assertEqual(WizardState.DONE, wizard.state)
#         group.run.assert_called()
#         group.run.assert_awaited()
#
#     def test_wizard_failure(self):
#         # pylint: disable = too-many-ancestors
#         class Test(MagicMock, Check):
#             def __init__(self):
#                 MagicMock.__init__(self)
#                 Check.__init__(self, WizardCheckType.UNKNOWN, Mock(), [])
#
#             def task_run(self, actions: UserActionBroker):
#                 pass
#
#         check = Test()
#         exception = Exception("Synthetic fail")
#         check.task_run = Mock()
#         check.task_run.side_effect = exception
#         wizard = Wizard([TestGroup(Mock(), [check])])
#         wizard.start()
#         wizard.join()
#
#         self.assertEqual(WizardState.FAILED, wizard.state)
#         self.assertEqual(exception, wizard.exception)
#
#     def test_wizard_warning(self):
#         warning = Exception("Warning")
#
#         class Test(Check):
#             def __init__(self):
#                 super().__init__(WizardCheckType.UNKNOWN, Mock(), [])
#
#             def task_run(self, actions: UserActionBroker):
#                 self.add_warning(warning)
#
#         check = Test()
#         wizard = Wizard([TestGroup(Mock(), [check])])
#         wizard.start()
#         wizard.join()
#
#         self.assertEqual(WizardState.DONE, wizard.state)
#         self.assertIn(warning, wizard.warnings)
#
#     def test_group_setup(self):
#         test = TestGroup(Mock(), [])
#         actions = Mock()
#         asyncio.run(test.run(actions))
#         test.setup.assert_called()
#
#     def test_check_execution(self):
#         check = Mock()
#         actions = Mock()
#         group = TestGroup(Mock(), [check])
#         asyncio.run(group.run(actions))
#
#         check.run.assert_called()
#
#     def test_configuration_match(self):
#         check = Mock()
#         check.configuration = Configuration(TankSetup.UV, PlatformSetup.RESIN_TEST)
#
#         with self.assertRaises(ValueError):
#             TestGroup(Configuration(TankSetup.PRINT, PlatformSetup.PRINT), [check])


if __name__ == "__main__":
    unittest.main()
