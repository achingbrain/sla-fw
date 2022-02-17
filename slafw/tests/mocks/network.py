# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=too-few-public-methods

from pathlib import Path
from shutil import copyfile
from typing import Optional, Callable
from unittest.mock import Mock
import re

from PySignal import Signal

from slafw import defines
from slafw.functions.system import printer_model_regex
from slafw.tests import samples


class Network:
    def __init__(self, *_, **__):
        self.ip = "1.2.3.4"
        self.devices = {"eth0": "1.2.3.4"}
        self.net_change = Signal()
        self.online = True

    def register_events(self):
        pass

    def start_net_monitor(self):
        pass

    @staticmethod
    def download_url(
        url: str,
        destination: str,
        progress_callback: Optional[Callable[[float], None]] = None,
    ):
        dld_regex = re.compile(defines.examplesURL.replace("{PRINTER_MODEL}", printer_model_regex(True)))
        if not dld_regex.match(url):
            raise ValueError(f"Unsupported mock url value: {url}")
        mini_examples = Path(samples.__file__).parent / "mini_examples.tar.gz"
        progress_callback(0)
        progress_callback(1)
        copyfile(mini_examples, destination)
        progress_callback(99)
        progress_callback(100)

    def force_refresh_state(self):
        pass


def fake_network_system_bus():
    mock = Mock()
    get_mock = Mock()
    get_mock.AddressData = [{"address": "1.2.3.4"}]
    mock.get.return_value = get_mock
    return mock
