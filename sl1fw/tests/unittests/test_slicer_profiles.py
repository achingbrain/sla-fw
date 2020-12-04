#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.slicer.slicer_profile import SlicerProfile
from sl1fw.slicer.profile_parser import ProfileParser
from sl1fw.slicer.profile_downloader import ProfileDownloader
from sl1fw.libNetwork import Network
from sl1fw.screen.printer_model import PrinterModelTypes


class TestSlicerProfiles(Sl1fwTestCase):
    INI = Sl1fwTestCase.SAMPLES_DIR / "slicer_profiles.ini"
    CMP = Sl1fwTestCase.SAMPLES_DIR / "slicer_profiles.toml"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_load(self):
        printer_model = PrinterModelTypes.SL1.parameters()
        profile = ProfileParser(printer_model).parse(self.INI)
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
        new_profile = ProfileParser(printer_model).parse(downloader.download(new_version))
        self.assertIsNotNone(new_profile)
        print(new_profile)


if __name__ == '__main__':
    unittest.main()
