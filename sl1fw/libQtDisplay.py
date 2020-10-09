# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from sl1fw.libServer import SocketServer
from sl1fw.libVirtualDisplay import VirtualDisplay

from sl1fw import defines

class QtDisplayServer(SocketServer):

    def __init__(self, port, commands, events):
        super(QtDisplayServer, self).__init__(port, commands, events)
        self.logger = logging.getLogger(__name__)
    #enddef


    def formatMessage(self, data):
        try:
            if data['command'] == "showPage":
                self.newClientData = data
            elif data['command'] == "showItems":
                self.newClientData.update({ x: data[x] for x in data if x != 'command' })
            else:
                self.logger.warning("unknown command '%s'", data['command'])
            #endif
        except Exception:
            self.logger.exception("exception")
        #endtry

        return data
    #enddef

#endclass


class QtDisplay(VirtualDisplay):

    def __init__(self):
        super(QtDisplay, self).__init__()
        self.type = "QT Display"
        self.server = QtDisplayServer(defines.qtDisplayPort, self.commands, self.events)
    #enddef

#endclass
