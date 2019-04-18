# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
from multiprocessing import Queue
from Queue import Empty


class VirtualDisplay(object):

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.commands = Queue()
        self.events = Queue()
        self.netActive = False
        self.items = dict()
    #enddef


    def setPage(self, page):
        self.items['page'] = page
    #enddef


    def setItems(self, items):
        if 'page' in self.items:
            self.items.update(items)
        else:
            self.logger.error("no actual page is set")
        #endif
    #enddef


    def showPage(self):
        self.items['net'] = self.netActive
        self.items['command'] = "showPage"
        try:
            self.commands.put_nowait(self.items)
        except Exception:
            self.logger.exception("put showPage exception")
        #endtry
        self.items = dict()
    #enddef


    def showItems(self, items):
        items['command'] = "showItems"
        try:
            self.commands.put_nowait(items)
        except Exception:
            self.logger.exception("put showItem exception")
        #endtry
    #enddef


    def assignNetActive(self, value):
        self.netActive = value
        try:
            self.commands.put_nowait({'command' : "showItems", 'net' : value })
        except Exception:
            self.logger.exception("put netActive exception")
        #endtry
    #enddef


    def getEventNoWait(self):
        try:
            return self.events.get_nowait()
        except Empty:
            pass
        except Exception:
            self.logger.exception("getEventNoWait exception")
        #endtry

        return { 'page' : None, 'id' : None, 'pressed' : None }
    #enddef


#endclass

