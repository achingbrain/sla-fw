from mock import Mock


class SystemBus:
    def __call__(self):
        return self

    def get(self, service, *args, **kwargs):
        if service == "de.pengutronix.rauc":
            rauc = Rauc()

            return {
                'de.pengutronix.rauc.Installer': rauc
            }
        else:
            raise Exception("Cannot provide fake service for unknown service name %s" % service)


class Rauc(Mock):
    def __init__(self):
        super().__init__()

        self.Operation = 'idle'
        self.Progress = (0, '', 0)
        self.BootSlot = 'A'
        self.Compatible = 'prusa64-sl1--prusa'
        self.LastError = ''

    def GetSlotStatus(self):
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
