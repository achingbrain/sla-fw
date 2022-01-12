# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later


import unittest
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from slafw.libNetwork import Network
from slafw.tests import samples
from slafw.tests.base import SlafwTestCase
from slafw.tests.mocks.http_server import MockServer


class MockHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, directory=Path(samples.__file__).parent)


class TestExamples(SlafwTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.server = MockServer()
        self.server.start()

    def tearDown(self) -> None:
        self.server.stop()
        super().tearDown()

    def test_download(self):
        # pylint: disable = no-self-use
        network = Network("TEST")
        with TemporaryDirectory() as temp:
            target = Path(temp) / "examples.tar.gz"
            callback = Mock()
            network.download_url(
                "http://localhost:8000/mini_examples.tar.gz",
                str(target),
                progress_callback=callback,
            )
            callback.assert_called()


if __name__ == "__main__":
    unittest.main()
