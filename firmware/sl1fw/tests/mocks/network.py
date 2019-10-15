# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

class Network:
    def __init__(self):
        self.ip = "1.2.3.4"
        self.devices = {
            'eth0': "1.2.3.4"
        }
        self.hostname = "test_hostname"

    def start_net_monitor(self):
        pass

    def register_net_change_handler(self, _):
        pass
