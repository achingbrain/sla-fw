from subprocess import Popen, PIPE
import threading
from queue import Queue
import logging


class Serial(object):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)

        # Run MC simulator process
        self.process = Popen(["SLA-control-01.elf"], stdin=PIPE, stdout=PIPE, stderr=PIPE)

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
        self.process.wait(timeout=3)
        self.reader_thread.join()

    def write(self, data):
        """
        Write data to simualted MC serial port
        :param data: Data to be written to simualted serial port
        :return: None
        """
        self.logger.debug("MCSim: writting: %s", data)
        try:
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except:
            self.logger.exception("Failed to write to simulated port")

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
        self.logger.debug(f"Reading start from serial: {self.process.stdout.readline()}")
        # TODO: This pretends MC communication start has no weak places. In reality the MC "usually" starts before
        #       the libHardware. In such case the "start" is never actually read from MC. Therefore this also throws
        #       "start" away. In fact is may happen that the MC is initializing in paralel with the libHardware (resets)
        #       In such case the "start" can be read and libHardware will throw an exception. This is correct as
        #       working with uninitialized MC is not safe. Unfortunately we cannot wait for start/(future ready) as
        #       it may not come if the MC has initialized before we do so. Therefore we need to have a safe command
        #       that checks whenever the MC is ready.
        while self.process.poll() is None:
            line = self.process.stdout.readline()
            self.read_queue.put(line)
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.stderr.close()
