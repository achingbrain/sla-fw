# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from queue import Queue
from threading import Lock
from time import monotonic

from sl1fw.libVirtualDisplay import VirtualDisplay


class TestDisplay(VirtualDisplay):
    def __init__(self):
        super().__init__()
        self.page = None
        self.items = {}
        self.items_lock = Lock()
        self.page_queue = Queue()

    def start(self):
        pass

    def exit(self):
        pass

    def setPage(self, page):
        super().setPage(page)
        self.page = page
        with self.items_lock:
            self.items = {}
        self.page_queue.put(page)
        print("Page: %s" % page)

    def setItems(self, items):
        super().setItems(items)
        with self.items_lock:
            self.items.update(items)
        print("SetItems: %s" % items)

    def showItems(self, items):
        super().showItems(items)
        with self.items_lock:
            self.items.update(items)
        print("ShowItems: %s" % items)

    def add_event(self, page, event_id, pressed, data):
        self.events.put({
            'page': page,
            'id': event_id,
            'pressed': pressed,
            'data': data
        })

    def read_page(self, timeout_sec = None):
        return self.page_queue.get(timeout=timeout_sec)

    def read_items(self, timeout_sec = None):
        start = monotonic()
        while True:
            with self.items_lock:
                if self.items:
                    return self.items
            if timeout_sec and monotonic() - start > timeout_sec:
                raise TimeoutError()
