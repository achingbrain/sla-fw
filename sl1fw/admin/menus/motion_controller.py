# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from functools import partial

from sl1fw import defines
from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction, AdminLabel
from sl1fw.admin.menus.dialogs import Info, Confirm, Wait
from sl1fw.admin.safe_menu import SafeAdminMenu
from sl1fw.errors.errors import NotConnected
from sl1fw.libPrinter import Printer
from sl1fw.states.printer import PrinterState


class MotionControllerMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_item(AdminAction("Flash MC", self.flash_mc))
        self.add_item(AdminAction("Erase MC EEPROM", self.erase_mc_eeprom))
        self.add_item(AdminAction("MC2Net (bootloader)", self.mc2net_boot))
        self.add_item(AdminAction("MC2Net (firmware)", self.mc2net_firmware))

    def flash_mc(self):
        self._control.enter(
            Confirm(self._control, self._do_flash_mc, text="This will overwrite the motion controller firmware.")
        )

    def _do_flash_mc(self):
        self._control.enter(Wait(self._control, self._do_flash_mc_body))

    def _do_flash_mc_body(self, status: AdminLabel):
        status.set("Forced update of the motion controller firmware")
        self._printer.state = PrinterState.UPDATING_MC
        self._printer.hw.flashMC()
        self._printer.hw.eraseEeprom()
        self._printer.hw.initDefaults()
        self._printer.state = PrinterState.RUNNING
        self._control.enter(Info(self._control, text="Motion controller flashed", pop=2))

    def erase_mc_eeprom(self):
        self._control.enter(
            Confirm(
                self._control,
                self._do_erase_mc_eeprom,
                text="This will erase all profiles and other motion controller settings.",
            )
        )

    def _do_erase_mc_eeprom(self):
        self._control.enter(Wait(self._control, self._do_erase_mc_eeprom_body))

    def _do_erase_mc_eeprom_body(self, status: AdminLabel):
        status.set("Erasing EEPROM")
        self._printer.state = PrinterState.UPDATING_MC
        self._printer.hw.eraseEeprom()
        self._printer.hw.initDefaults()
        self._printer.state = PrinterState.RUNNING
        self._control.enter(Info(self._control, text="Motion controller eeprom erased.", pop=2))

    def mc2net_boot(self):
        self._control.enter(
            Confirm(
                self._control,
                partial(self._do_mc2net, True),
                text="This will freeze the printer and connect the MC bootloader to TCP port.",
            )
        )

    def mc2net_firmware(self):
        self._control.enter(
            Confirm(
                self._control,
                partial(self._do_mc2net, False),
                text="This will connect the motion controller to TCP port.",
            )
        )

    @SafeAdminMenu.safe_call
    def _do_mc2net(self, bootloader=False):
        ip = self._printer.inet.ip
        if ip is None:
            raise NotConnected("Cannot start mc net connection when not connected")

        self._printer.hw.mcc.start_debugging(bootloader=bootloader)

        self._control.enter(
            Info(
                self._control,
                text="Listening for motion controller debugging connection.\n\n"
                f"Serial line is redirected to {ip}:{defines.mc_debug_port}.\n\n"
                "Press continue to use the printer. The debugging will begin with new connection"
                "and will end as soon as the connection terminates.",
                pop=2,
            )
        )
