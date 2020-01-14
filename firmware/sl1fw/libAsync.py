# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import shutil
import threading
from abc import ABC, abstractmethod

from sl1fw import defines
from sl1fw.libConfig import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.libNetwork import Network
from sl1fw.slicer.profile_downloader import ProfileDownloader
from sl1fw.slicer.profile_parser import ProfileParser
from sl1fw.slicer.slicer_profile import SlicerProfile


class BackgroundNetworkCheck(ABC):
    def __init__(self, inet: Network):
        self.logger = logging.getLogger(__name__)
        self.inet = inet
        self.first = True
        self.inet.register_net_change_handler(self.connection_changed)

    def connection_changed(self, value):
        if value and self.first:
            self.first = False
            self.logger.debug("Starting background network check thread")
            threading.Thread(target=self.check, daemon=True).start()

    @abstractmethod
    def check(self):
        ...


class AdminCheck(BackgroundNetworkCheck):
    def __init__(self, config: RuntimeConfig, hw: Hardware, inet: Network):
        self.config = config
        self.hw = hw
        super().__init__(inet)

    def check(self):
        self.logger.info("The network is available, querying admin enabled")
        query_url = defines.admincheckURL + "/?serial=" + self.hw.cpuSerialNo
        self.inet.download_url(query_url, defines.admincheckTemp)

        with open(defines.admincheckTemp, "r") as file:
            admin_check = json.load(file)
            if admin_check["result"]:
                self.config.show_admin = True
                self.logger.info("Admin enabled")
            else:
                self.logger.info("Admin not enabled")


class SlicerProfileUpdater(BackgroundNetworkCheck):
    def __init__(self, inet: Network, profile: SlicerProfile):
        self.profile = profile
        super().__init__(inet)

    def check(self):
        self.logger.info("The network is available, checking slicer profiles update")
        downloader = ProfileDownloader(self.inet, self.profile.vendor)
        newVersion = downloader.checkUpdates()
        if newVersion:
            f = downloader.download(newVersion)
            newProfile = ProfileParser().parse(f)
            if newProfile:
                try:
                    shutil.copyfile(f, defines.slicerProfilesFile)
                except Exception:
                    self.logger.exception("copyfile exception:")
                self.profile.update(newProfile)
            else:
                self.logger.info("Problem with new profile file, giving up")
        else:
            self.logger.info("No new version of slicer profiles available")
