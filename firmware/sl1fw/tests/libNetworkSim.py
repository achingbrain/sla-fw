class Network(object):
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
