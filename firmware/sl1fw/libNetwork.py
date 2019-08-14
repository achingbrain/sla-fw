# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
from typing import Optional, Any, Callable

import pydbus


class Network(object):
    NETWORKMANAGER_SERVICE = "org.freedesktop.NetworkManager"
    HOSTNAME_SERVICE = "org.freedesktop.hostname1"
    NM_STATE_CONNECTED_GLOBAL = 70

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.assign_active = None
        self.net_change_handlers = []
        self.bus = pydbus.SystemBus()
        self.nm = self.bus.get(self.NETWORKMANAGER_SERVICE)
        self.hostname_service = self.bus.get(self.HOSTNAME_SERVICE)

    def start_net_monitor(self) -> None:
        """
        Start network monitoring
        Use register_net_change_handler to register for network updates
        :return: None
        """
        self.nm.PropertiesChanged.connect(self.state_changed)
        for device_path in self.nm.GetAllDevices():
            device = self.bus.get(self.NETWORKMANAGER_SERVICE, device_path)
            device.PropertiesChanged.connect(self.state_changed)

    def register_net_change_handler(self, handler: Callable[[bool], None]) -> None:
        """
        Register handler fo network change
        :param handler: Handler to call, global connectivity is passed as the only boolean argument
        :return: None
        """
        assert (handler is not None)
        self.net_change_handlers.append(handler)

        # Trigger property change on start to set initial connected state
        self.state_changed({'Connectivity': None})

    def state_changed(self, changed: map) -> None:
        events = {'Connectivity', 'Metered', 'ActiveConnections', 'WirelessEnabled'}
        if not events & set(changed.keys()):
            return

        for handler in self.net_change_handlers:
            handler(self.nm.state() == self.NM_STATE_CONNECTED_GLOBAL)

        self.logger.debug(f"NetworkManager state changed: {changed}, devices: {self.devices}")

    @property
    def ip(self) -> Optional[str]:
        connection_path = self.nm.PrimaryConnection

        if connection_path == "/":
            return None

        return self._get_ipv4(self._get_nm_obj(connection_path).Ip4Config)

    @property
    def devices(self) -> map:
        """
        Get network device dictionary
        :return: {interface_name: ip_address}
        """
        return {dev.Interface: self._get_ipv4(dev.Ip4Config) for dev in
                [self._get_nm_obj(dev_path) for dev_path in self.nm.GetAllDevices()] if
                dev.Interface != "lo" and dev.Ip4Config != "/"}

    @property
    def hostname(self) -> str:
        return self.hostname_service.StaticHostname

    @hostname.setter
    def hostname(self, hostname: str) -> None:
        self.hostname_service.SetStaticHostname(hostname, False)
        self.hostname_service.SetHostname(hostname, False)

    def _get_ipv4(self, ipv4_config_path: str) -> Optional[str]:
        """
        Resolves IPv4 address string from NetworkManager ipv4 configuration object path
        :param ipv4_config_path: D-Bus path to NetworkManager ipv4 configuration
        :return: IP address as string or None
        """
        if ipv4_config_path == "/":
            return None

        ipv4 = self._get_nm_obj(ipv4_config_path)

        if len(ipv4.AddressData) == 0:
            return None

        return ipv4.AddressData[0]['address']

    def _get_nm_obj(self, path: str) -> Any:
        """
        Get NetworkManager D-Bus object by path
        :param path:
        :return:
        """
        return self.bus.get(self.NETWORKMANAGER_SERVICE, path)
