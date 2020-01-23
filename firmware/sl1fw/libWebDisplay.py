# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import jinja2
import jinja2.exceptions

from sl1fw.libServer import SocketServer
from sl1fw.libVirtualDisplay import VirtualDisplay

from sl1fw import defines

class WebDisplayServer(SocketServer):

    def __init__(self, port, commands, events):
        super(WebDisplayServer, self).__init__(port, commands, events)
        self.logger = logging.getLogger(__name__)
        self.jinja = jinja2.Environment(loader = jinja2.FileSystemLoader(defines.templates))
        self.newClientData['command'] = "showPage"
        self.newClientData['page'] = "home"
    #enddef

    def _onMessageReceived(self, client, server, message):
        pass
    #enddef

    def formatMessage(self, data):
        #self.logger.debug("data: '%s'", str(data))
        output = dict()

        try:

            if data['command'] == "showPage":

                output['type'] = "page"
                # output['content'] = "page"

            elif data['command'] == "showItems":

                del data['command']
                self.newClientData.update(data)
                output['type'] = "items"
                output['content'] = data

            else:
                self.logger.warning("unknown command '%s'", data['command'])
            #endif

        except Exception:
            self.logger.exception("exception")
            output['type'] = "page"
            output['content'] = _("SERVER ERROR!")
        #endtry

        return output
    #enddef
#endclass


class WebDisplay(VirtualDisplay):

    def __init__(self):
        super(WebDisplay, self).__init__()
        self.type = "Web Display"
        self.server = WebDisplayServer(defines.webDisplayPort, self.commands, self.events)
    #enddef

#endclass
