from queue import Queue
from time import monotonic

from sl1fw.libVirtualDisplay import VirtualDisplay


class TestDisplay(VirtualDisplay):
    def __init__(self):
        super(TestDisplay, self).__init__()
        self.page = None
        self.items = {}
        self.page_queue = Queue()

    def start(self):
        pass

    def exit(self):
        pass

    def setPage(self, page):
        super(TestDisplay, self).setPage(page)
        self.page = page
        self.page_queue.put(page)
        self.items = {}
        print("Page: %s" % page)

    def setItems(self, items):
        super(TestDisplay, self).setItems(items)
        self.items.update(items)
        print("SetItems: %s" % items)

    def showItems(self, items):
        super(TestDisplay, self).showItems(items)
        self.items.update(items)
        print("ShowItems: %s" % items)

    def add_event(self, page, id, pressed, data):
        self.events.put({
            'page': page,
            'id': id,
            'pressed': pressed,
            'data': data
        })

    def read_page(self, timeout_sec = None):
        return self.page_queue.get(timeout=timeout_sec)

    def read_items(self, timeout_sec = None):
        start = monotonic()
        while True:
            if self.items:
                return self.items
            if timeout_sec and monotonic() - start > timeout_sec:
                raise TimeoutError()
