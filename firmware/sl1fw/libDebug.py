# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from collections import deque
import jinja2
from multiprocessing import Queue

from sl1fw.libServer import SocketServer

from sl1fw import defines

class DebugServer(SocketServer):

    def __init__(self, port, commands):
        super(DebugServer, self).__init__(port, commands)
        self.logger = logging.getLogger(__name__)
        self.jinja = jinja2.Environment(loader = jinja2.FileSystemLoader(defines.templates))
        self.newClientData['wholePage'] = True
    #enddef


    def formatMessage(self, data):
        #self.logger.debug("data: '%s'", str(data))
        output = dict()

        try:
            if data.get('wholePage', False):
                html = self.jinja.get_template('debug.html').render(items = data)
                #self.logger.debug("HTML: '%s'", html.replace("\n", " | "))
                output['type'] = "page"
                output['content'] = html
            else:
                self.newClientData.update(data)
                output['type'] = "items"
                output['content'] = data
            #endif
        except Exception:
            self.logger.exception("exception")
            output['type'] = "page"
            output['content'] = _("SERVER ERROR!")
        #endtry

        return output
    #enddef

#endclass


class Debug:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.commands = Queue()
        self.items = dict()
        self.server = DebugServer(defines.debugPort, self.commands)
        self.server.start()
        self.setup = {
                "towerProfile" : ("Actual tower profile: ", "line1"),
                "towerFailed" : ("Last failed tower profile: ", "line2"),
                "towerPositon" : ("Actual tower position: ", "line3"),
                "tiltProfile" : ("Actual tilt profile: ", "line4"),
                "tiltFailed" : ("Last failed tilt Profile: ", "line5"),
                "tiltPosition" : ("Actual tilt position: ", "line6"),
                }
        self.logLines = deque(maxlen = 30)
    #enddef


    def exit(self):
        self.server.join()
    #enddef


    def showItems(self, **kwargs):
        output = dict()
        for name, value in kwargs.items():
            item = self.setup.get(name, None)
            if item:
                output[item[1]] = "%s%s" % (item[0], value)
            else:
                self.logger.warning("Unknown item '%s', ignored", name)
            #endif
        try:
            self.commands.put_nowait(output)
        except Exception:
            self.logger.exception("put exception")
        #endtry
    #enddef


    def log(self, message):
        self.logLines.append(message)
        try:
            self.commands.put_nowait( { 'log' : "\n".join(self.logLines) } )
        except Exception:
            self.logger.exception("put log exception")
        #endtry
    #enddef

#endclass
