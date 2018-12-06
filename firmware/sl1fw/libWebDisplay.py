# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import logging
import jinja2

from libServer import SocketServer
from libVirtualDisplay import VirtualDisplay

import defines

class WebDisplayServer(SocketServer):

    def __init__(self, port, commands, events):
        self.logger = logging.getLogger(__name__)
        super(WebDisplayServer, self).__init__(port, commands, events)
        self.jinja = jinja2.Environment(loader = jinja2.FileSystemLoader(defines.templates))
    #enddef


    def formatMessage(self, data):
        #self.logger.debug("data: '%s'", str(data))
        output = dict()

        design = "dwarf3"   # TODO

        try:

            if data['command'] == "showPage":

                self.newClientData = data
                page = data['page']
                content = self.jinja.get_template("_%sC.html" % page).render(items = data, design = design)
                header = self.jinja.get_template("_%sH.html" % page).render(design = design)
                html = self.jinja.get_template('layout.html').render(content = content, header = header, design = design, page = page)
                #self.logger.debug("HTML: '%s'", html.replace("\n", " | "))
                output['type'] = "page"
                output['content'] = html

            elif data['command'] == "showItems":

                del data['command']
                self.newClientData.update(data)
                output['type'] = "items"
                output['content'] = data

#            elif data['command'] == "change":  TODO jako showItems?

            else:
                self.logger.warning("unknown command '%s'", data['command'])
            #endif

        except Exception:
            self.logger.exception("exception")
            output['type'] = "page"
            output['content'] = "SERVER ERROR!"
        #endtry

        return output
    #enddef
#endclass


class WebDisplay(VirtualDisplay):

    def __init__(self):
        super(WebDisplay, self).__init__()
        self.type = "Web Display"
        self.server = WebDisplayServer(defines.webDisplayPort, self.commands, self.events)
        self.server.start()
    #enddef

    def __del__(self):
        self.server.join()
    #enddef

#endclass
