from subprocess import Popen, PIPE
import threading
from queue import Queue
import os
import logging


class Serial(object):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

        # Run MC simulator process
        self.process = Popen([os.path.join(os.path.dirname(__file__), "samples/SLA-control-01.elf")],
                             stdin=PIPE, stdout=PIPE, stderr=PIPE)

        # Start thread for reading lines from process output
        # It is necessary as inWaiting call should be able to tell how many items are pending
        self.read_queue = Queue()
        self.reader_thread = threading.Thread(target=self._reader)
        self.reader_thread.start()

    def close(self):
        self.stop()

    def stop(self):
        """
        Stop MS Port simulator
        Terminate simulator and output reading thread
        :return: None
        """
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except TypeError:
            # Python 2 code:
            self.process.wait()

        self.reader_thread.join()

    def write(self, data):
        """
        Write data to simualted MC serial port
        :param data: Data to be written to simualted serial port
        :return: None
        """
        self.logger.debug("MCSim: writting: %s", data)
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def readline(self):
        """
        Read line from simulated serial port
        :return: Line read from simulated serial port
        """
        line = self.read_queue.get()
        self.logger.debug("MCSim: reading: %s", line)
        return line

    def inWaiting(self):
        """
        Number if lines from MC waiting to be processed
        :return: NUmber of pending lines
        """
        return self.read_queue.qsize()

    def _reader(self):
        while self.process.poll() is None:
            line = self.process.stdout.readline()
            self.read_queue.put(line)
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.stderr.close()
