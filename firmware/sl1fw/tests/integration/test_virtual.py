# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from multiprocessing import Process
from threading import Thread
from time import sleep
from unittest import TestCase

import psutil
import pydbus
from gi.repository import GLib
from psutil import NoSuchProcess

from sl1fw.api.printer0 import Printer0State
from sl1fw.virtual import Virtual


class TestVirtualPrinter(TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ok = False

    def test_virtual(self):
        virtual = Process(target=Virtual().run)
        virtual.start()

        # Wait for virtual printer to start
        for i in range(5):
            print(f"Attempt {i} to verify virtual printer is running")
            sleep(1)
            # Run checks in threads as the calls might block
            Thread(target=self.run_check, daemon=True).start()
            if self.started_ok or not virtual.is_alive():
                break

        children = psutil.Process().children(recursive=True)
        print("### Terminating virtual printer")
        virtual.terminate()
        sleep(1)
        for child in children:
            try:
                child.terminate()
                print(f"Terminated child: {child.pid}")
            except NoSuchProcess:
                pass  # Possibly the child was gracefully terminated
        print("### Killing virtual printer")
        virtual.kill()
        for child in children:
            try:
                child.kill()
                print(f"Killed child: {child.pid}")
            except NoSuchProcess:
                pass  # Possibly the child was gracefully terminated
        virtual.join()

        self.assertTrue(self.started_ok, "Virtual printer idle on DBus")

    def run_check(self):
        try:
            printer0 = pydbus.SystemBus().get("cz.prusa3d.sl1.printer0")
            state = Printer0State(printer0.state)
            print(f"Printer state on Dbus: {state}")
            if state == Printer0State.IDLE:
                print("Printer is up and running")
                self.started_ok = True

        except GLib.Error:
            print("Attempt to obtain virtual printer state ended up with exception")


if __name__ == "__main__":
    unittest.main()
