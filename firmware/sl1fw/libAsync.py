# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import threading
from abc import ABC, abstractmethod

from sl1fw import defines
from sl1fw.libDisplay import Display
from sl1fw.libNetwork import Network


class BackgroundNetworkCheck(ABC):
    def __init__(self, inet: Network):
        self.logger = logging.getLogger(__name__)
        self.inet = inet
        self.first = True
        self.inet.register_net_change_handler(self.connection_changed)

    def connection_changed(self, value):
        if value and self.first:
            self.first = False
            self.logger.info("Starting background network check thread")
            threading.Thread(target=self.check, daemon=True).start()

    @abstractmethod
    def check(self):
        ...


class AdminCheck(BackgroundNetworkCheck):
    def __init__(self, display: Display, inet: Network):
        self.display = display
        super().__init__(inet)

    def check(self):
        self.logger.info("The network is available, querying admin enabled")
        query_url = defines.admincheckURL + "/?serial=" + self.display.hw.cpuSerialNo
        self.inet.download_url(query_url, defines.admincheckTemp, self.display.hw.cpuSerialNo)

        with open(defines.admincheckTemp, "r") as file:
            admin_check = json.load(file)
            if admin_check["result"]:
                self.display.show_admin = True
                self.logger.info("Admin enabled")
            else:
                self.logger.info("Admin not enabled")
