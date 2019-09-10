from sl1fw.libVirtualDisplay import VirtualDisplay
from queue import Queue


class TestDisplay(VirtualDisplay):
    def __init__(self):
        super(TestDisplay, self).__init__()
        self.page = None
        self.page_queue = Queue()

    def start(self):
        pass

    def exit(self):
        pass

    def setPage(self, page):
        super(TestDisplay, self).setPage(page)
        self.page = page
        self.page_queue.put(page)
        print("Page: %s" % page)

    def setItems(self, items):
        super(TestDisplay, self).setItems(items)
        print("Items: %s" % items)

    def showItems(self, items):
        super(TestDisplay, self).showItems(items)
        print("Items: %s" % items)

    def add_event(self, page, id, pressed, data):
        self.events.put({
            'page': page,
            'id': id,
            'pressed': pressed,
            'data': data
        })

    def read_page(self, timeout_sec = None):
        return self.page_queue.get(timeout=timeout_sec)