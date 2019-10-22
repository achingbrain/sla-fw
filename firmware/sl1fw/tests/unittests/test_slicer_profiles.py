#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.slicer.profile_parser import ProfileParser
from sl1fw.slicer.profile_downloader import ProfileDownloader
from sl1fw.libNetwork import Network

from sl1fw import defines

class TestSlicerProfiles(Sl1fwTestCase):
    FILENAME = Sl1fwTestCase.SAMPLES_DIR / "slicer_profiles.ini"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_load(self):
        profile = ProfileParser().parse(self.FILENAME)
        self.assertIsNotNone(profile)
        print(profile)
        downloader = ProfileDownloader(Network("CZPX1234X123XC12345"), profile.vendor)
        newVersion = downloader.checkUpdates()
        self.assertIsNotNone(newVersion)
        newProfile = ProfileParser().parse(downloader.download(newVersion))
        self.assertIsNotNone(newProfile)
        print(newProfile)


if __name__ == '__main__':
    unittest.main()
