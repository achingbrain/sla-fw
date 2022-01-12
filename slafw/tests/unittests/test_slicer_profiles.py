#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from slafw.tests.base import SlafwTestCase
from slafw.slicer.slicer_profile import SlicerProfile
from slafw.slicer.profile_parser import ProfileParser
from slafw.slicer.profile_downloader import ProfileDownloader
from slafw.libNetwork import Network


class TestSlicerProfiles(SlafwTestCase):
    INI = SlafwTestCase.SAMPLES_DIR / "slicer_profiles.ini"
    CMP = SlafwTestCase.SAMPLES_DIR / "slicer_profiles.toml"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_load(self):
        profile = ProfileParser("SL1").parse(self.INI)
        self.assertTrue(profile.vendor)
        self.assertTrue(profile.printer)
        #profile.save(filename = "slicer_profiles_test.toml")
        profile2test = SlicerProfile(self.CMP)
        profile2test.load()
        self.assertEqual(profile.vendor, profile2test.vendor, "vendor")
        self.assertEqual(profile.printer, profile2test.printer, "printer")

        downloader = ProfileDownloader(Network("CZPX1234X123XC12345"), profile.vendor)
        new_version = downloader.checkUpdates()
        self.assertIsNotNone(new_version)
        new_profile = ProfileParser("SL1").parse(downloader.download(new_version))
        self.assertIsNotNone(new_profile)
        print(new_profile)


if __name__ == '__main__':
    unittest.main()
