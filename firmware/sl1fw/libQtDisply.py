# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import logging
from libServer import SocketServer
from libVirtualDisplay import VirtualDisplay

import defines

class QtDisplayServer(SocketServer):

    def __init__(self, port, commands, events):
        self.logger = logging.getLogger(__name__)
        super(QtDisplayServer, self).__init__(port, commands, events)
    #enddef

    # TODO formatMessage() pro updaty self.newClientData

#endclass


class QtDisplay(VirtualDisplay):

    def __init__(self):
        super(QtDisplay, self).__init__()
        self.type = "QT Display"
        self.server = QtDisplayServer(defines.qtDisplayPort, self.commands, self.events)
        self.server.start()
    #enddef

    def __del__(self):
        self.server.join()
    #enddef

#endclass
