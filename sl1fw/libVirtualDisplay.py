# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from multiprocessing import Queue
from queue import Empty


class VirtualDisplay:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.commands = Queue()
        self.events = Queue()
        self.netActive = False
        self.items = dict()
        self.server = None
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
        #endif
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
        if self.netActive != value:
            self.netActive = value
            try:
                self.commands.put_nowait({'command' : "showItems", 'net' : value })
            except Exception:
                self.logger.exception("put netActive exception")
            #endtry
        else:
            self.logger.debug("Net active update skipped, value has not changed")
        #endif
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
