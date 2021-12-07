# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock

from sl1fw import defines
from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.wizard.wizards.self_test import SelfTestWizard
from sl1fw.tests.mocks.hardware import Hardware


class TestSelfTestWizardDataPresent(Sl1fwTestCase):
    # pylint: disable = protected-access
    def setUp(self) -> None:
        super().setUp()
        defines.factoryMountPoint = self.TEMP_DIR / "wizard_data_present"
        try:
            defines.factoryMountPoint.rmdir()
        except FileNotFoundError:
            pass
        defines.factoryMountPoint.mkdir(parents=True)
        self.wizard = SelfTestWizard(Hardware(), Mock(), Mock())

    def tearDown(self) -> None:
        del self.wizard
        super().tearDown()

    def test_data_nothing(self):
        self.assertFalse(self.wizard._data_present_in_factory())

    def test_garbage(self):
        garbage = defines.factoryMountPoint / "garbage.xyz"
        garbage.touch()
        self.assertFalse(self.wizard._data_present_in_factory())
        garbage.unlink()

    def present(self):
        present = defines.factoryMountPoint / self.wizard.get_data_filename()
        present.touch()
        self.assertTrue(self.wizard._data_present_in_factory())
        present.unlink()

    def test_present_different(self):
        different_extension = defines.factoryMountPoint / "wizard_data.xyz"
        different_extension.touch()
        self.assertTrue(self.wizard._data_present_in_factory())
        different_extension.unlink()

    def test_alternative_name(self):
        alternative = defines.factoryMountPoint / "wizard_data.toml"
        alternative.touch()
        self.assertTrue(self.wizard._data_present_in_factory())
        alternative.unlink()
