# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

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


    def formatMessage(self, data):
        #self.logger.debug("data: '%s'", str(data))
        output = dict()

        try:

            if data['command'] == "showPage":

                self.newClientData = data
                page = data['page']

                try:
                    content_template = self.jinja.get_template("_%sC.html" % page)
                except jinja2.exceptions.TemplateNotFound:
                    content_template = self.jinja.get_template("_default.html")
                content = content_template.render(items = data)

                for header_filename in ["_%sH.html" % page, "_head_common.html", "_head_default.html"]:
                    try:
                        header_template = self.jinja.get_template(header_filename)
                        break
                    except jinja2.exceptions.TemplateNotFound:
                        continue
                header = header_template.render(items = data, page = page)
                
                html = self.jinja.get_template('layout.html').render(content = content, header = header, page = page)
                #self.logger.debug("HTML: '%s'", html.replace("\n", " | "))
                output['type'] = "page"
                output['content'] = html

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

    def start(self):
        self.server.start()
    #enddef

    def __del__(self):
        self.exit()
    #enddef

    def exit(self):
        if self.server.is_alive():
            self.server.join()
        #nedif
    #enddef

#endclass
