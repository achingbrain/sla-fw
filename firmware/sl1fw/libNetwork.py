# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
import NetworkManager
import pydbus


class Network(object):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.assignActive = None

    def startNetMonitor(self, assignNetActive):
        self.assignActive = assignNetActive
        # TODO: networkmanager wrapper has some problem with events. Lets handle this manually
        #NetworkManager.NetworkManager.OnStateChanged(self.state_changed)
        pydbus.SystemBus().get("org.freedesktop.NetworkManager").PropertiesChanged.connect(self.state_changed)

        # Trigger property change on start to set initial connected state
        self.state_changed()

    def state_changed(self, *args, **kwargs):
        self.logger.debug("Networkmanager state changed")

        if self.assignActive:
            self.assignActive(NetworkManager.NetworkManager.State == NetworkManager.NM_STATE_CONNECTED_GLOBAL)

    @property
    def ip(self):
        return self._get_ip_safe(NetworkManager.NetworkManager.PrimaryConnection.Ip4Config)

    @property
    def devices(self):
        """
        Get network device dictionary
        :return: {interface_name: ip_address}
        """
        return {dev.Interface: self._get_ip_safe(dev.Ip4Config) for dev in NetworkManager.NetworkManager.GetDevices() if
                dev.Interface != "lo"}

    @staticmethod
    def _get_ip_safe(ipv4_config):
        try:
            return ipv4_config.Addresses[0][0]
        except:
            return None

    @property
    def hostname(self):
        # TODO: Unify hostname access
        return NetworkManager.Settings.Hostname
