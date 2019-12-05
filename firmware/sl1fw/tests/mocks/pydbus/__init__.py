# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later


class SystemBus:
    def __call__(self):
        return self

    @staticmethod
    def get(service, *_, **__):
        if service == "de.pengutronix.rauc":
            return {
                'de.pengutronix.rauc.Installer': Rauc()
            }
        elif service == "org.freedesktop.timedate1":
            return TimeDate()
        elif service == "org.freedesktop.hostname1":
            return Hostname()
        elif service == "org.freedesktop.locale1":
            return Locale()
        elif service == "org.freedesktop.NetworkManager":
            return NetworkManager()
        else:
            raise Exception("Cannot provide fake service for unknown service name %s" % service)

    def publish(self, path, service):
        pass


class TimeDate:
    def __init__(self):
        self.NTP = True
        self.Timezone = 'America/Vancouver'

    def SetNTP(self, state, *_):
        self.NTP = state

    def SetTimezone(self, tz, *_):
        self.Timezone = tz


class Hostname:
    def __init__(self):
        self.StaticHostname = "prusa-sl1"

    def SetStaticHostname(self, hostname, _):
        self.StaticHostname = hostname

    def SetHostname(self, hostname, _):
        pass


class Rauc:
    def __init__(self):
        self.Operation = 'idle'
        self.Progress = (0, '', 0)
        self.BootSlot = 'A'
        self.Compatible = 'prusa64-sl1--prusa'
        self.LastError = ''

    @staticmethod
    def GetSlotStatus():
        return [('rootfs.0',
                 {'status': 'ok', 'bootname': 'A', 'bundle.build': '20190613111424',
                  'bundle.version': '1.0', 'bundle.compatible': 'prusa64-sl1--prusa',
                  'activated.count': 11, 'description': '',
                  'installed.timestamp': '2019-06-17T13:45:20Z', 'class': 'rootfs',
                  'boot-status': 'good', 'state': 'booted',
                  'bundle.description': 'sla-update-bundle version 1.0-r0',
                  'installed.count': 11, 'device': '/dev/mmcblk2p2',
                  'sha256': '1b7ad103c7f1216f351b93cd384ce5444288e6adb53ed40b81bd987b591fcbd1',
                  'type': 'ext4', 'activated.timestamp': '2019-06-17T13:45:25Z',
                  'size': 655414272}), ('bootloader.0',
                                        {'device': '/dev/mmcblk2', 'state': 'inactive',
                                         'type': 'boot-emmc', 'class': 'bootloader',
                                         'description': ''}), ('rootfs.1',
                                                               {'status': 'ok',
                                                                'bootname': 'B',
                                                                'bundle.build': '20190613111424',
                                                                'bundle.version': '1.0',
                                                                'bundle.compatible': 'prusa64-sl1--prusa',
                                                                'activated.count': 9,
                                                                'description': '',
                                                                'installed.timestamp': '2019-06-17T13:42:03Z',
                                                                'class': 'rootfs',
                                                                'boot-status': 'good',
                                                                'state': 'inactive',
                                                                'bundle.description': 'sla-update-bundle version 1.0-r0',
                                                                'installed.count': 8,
                                                                'device': '/dev/mmcblk2p3',
                                                                'sha256': '1b7ad103c7f1216f351b93cd384ce5444288e6adb53ed40b81bd987b591fcbd1',
                                                                'type': 'ext4',
                                                                'activated.timestamp': '2019-06-17T13:42:07Z',
                                                                'size': 655414272})]


class Locale:
    def __init__(self):
        self.PropertiesChanged = self
        self.Locale = "C"

    def connect(self, callback):
        pass

    def SetLocale(self, locale, *_):
        self.Locale = locale

class NetworkManager:
    def __init__(self):
        self.PropertiesChanged = self
        self.PrimaryConnection = "/"
        self.connections = list(('test1', 'test2', 'test3'))

    @staticmethod
    def state():
        return 0

    @staticmethod
    def GetAllDevices():
        return []

    def connect(self, callback):
        pass

    def ListConnections(self):
        return self.connections

    def Delete(self):
        self.connections.pop()
