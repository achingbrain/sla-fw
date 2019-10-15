# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from mock import Mock

from PIL import Image, ImageChops

from sl1fw import defines
from sl1fw.tests import samples
import sl1fw.tests.mocks.mc_port
import sl1fw.tests.mocks.pydbus
from sl1fw.tests.mocks.gettext import fake_gettext

fake_gettext()
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.DEBUG)

sys.modules['pydbus'] = sl1fw.tests.mocks.pydbus
sys.modules['gpio'] = Mock()
sys.modules['sl1fw.libDebug'] = Mock()
sys.modules['serial'] = sl1fw.tests.mocks.mc_port


class Sl1fwTestCase(TestCase):
    SL1FW_DIR = Path(sl1fw.__file__).parent
    SAMPLES_DIR = Path(sl1fw.tests.samples.__file__).parent
    TEMP_DIR = Path(tempfile.gettempdir())
    EEPROM_FILE = Path.cwd() / "EEPROM.dat"

    def setUp(self) -> None:
        defines.testing = True

    def compareImages(self, path1: str, path2: str) -> bool:
        one = Image.open(path1)
        two = Image.open(path2)
        diff = ImageChops.difference(one, two)
        return diff.getbbox() != None
