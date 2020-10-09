# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.libNetwork import Network
from sl1fw.state_actions.examples import Examples
from sl1fw.states.examples import ExamplesState
from sl1fw.tests.mocks.network import fake_network_system_bus


class TestExamples(Sl1fwTestCase):
    def setUp(self) -> None:
        self.download_happening = False
        self.unpack_happening = False
        self.copy_happening = False

    def test_examples_download(self):
        with TemporaryDirectory() as temp:
            chown = Mock()
            with patch("sl1fw.defines.internalProjectPath", temp), patch("os.chown", chown), patch(
                "shutil.chown", chown
            ), patch("pydbus.SystemBus", fake_network_system_bus):
                self._internal_examples_download()
            chown.assert_called()
            examples = list(Path(temp).rglob("*.sl1"))
            self.assertLess(3, len(examples))
            self.assertTrue(self.download_happening)
            self.assertTrue(self.unpack_happening)
            self.assertTrue(self.copy_happening)

    def _internal_examples_download(self):
        network = Network("TEST SERIAL")
        examples = Examples(network)
        examples.start()
        examples.change.connect(functools.partial(self.check_change, examples))
        examples.join(timeout=180)
        self.assertEqual(ExamplesState.COMPLETED, examples.state)

    def check_change(self, examples):
        self.assertTrue(0 <= examples.download_progress <= 100)
        self.assertTrue(0 <= examples.unpack_progress <= 100)
        self.assertTrue(0 <= examples.copy_progress <= 100)

        if 0 < examples.download_progress < 100:
            self.download_happening = True

        if 0 < examples.unpack_progress < 100:
            self.unpack_happening = True

        if 0 < examples.copy_progress < 100:
            self.copy_happening = True


if __name__ == "__main__":
    unittest.main()
