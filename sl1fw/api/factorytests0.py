import logging

from sl1fw.api.decorators import dbus_api, state_checked, auto_dbus
from sl1fw.functions.system import hw_all_off
from sl1fw.libPrinter import Printer
from sl1fw.states.display import DisplayState
from sl1fw.states.printer import Printer0State


@dbus_api
class FactoryTests0:
    __INTERFACE__ = "cz.prusa3d.sl1.factorytests0"

    def __init__(self, printer: Printer):
        self._logger = logging.getLogger(__name__)
        self._printer = printer
        self._publication = None
        printer.runtime_config.factory_mode_changed.connect(self._factory_mode_changed)
        self._factory_mode_changed(printer.runtime_config.factory_mode)

    def _factory_mode_changed(self, factory_mode: bool) -> None:
        if factory_mode and self._publication is None:
            self._logger.info("registering as dbus interface")
            self._publication = self._printer.system_bus.publish(FactoryTests0.__INTERFACE__, self)
        elif not factory_mode and self._publication is not None:
            self._logger.info("deregistering the dbus interface")
            self.leave_test_mode()
            self._publication.unpublish()
            self._publication = None

    @property
    def state(self) -> int:
        state = self._printer.state.to_state0()
        if not state:
            state = self._printer.display.state.to_state0()
        if not state:
            state = Printer0State.IDLE

        return state

    @auto_dbus
    @state_checked(Printer0State.IDLE)
    def enter_test_mode(self) -> None:
        self._printer.display.state = DisplayState.DISPLAY_TEST

    @auto_dbus
    def get_uv(self) -> bool:
        return self._printer.hw.getUvLedState()[0]

    @auto_dbus
    @state_checked(Printer0State.DISPLAY_TEST)
    def set_uv(self, enable: bool) -> None:
        if enable:
            self._printer.hw.startFans()
            self._printer.hw.uvLedPwm = self._printer.hwConfig.uvPwm
        else:
            self._printer.hw.stopFans()

        self._printer.hw.uvLed(enable)

    @auto_dbus
    @state_checked(Printer0State.DISPLAY_TEST)
    def display_image(self, filename: str) -> None:
        self._printer.screen.show_system_image(filename)

    @auto_dbus
    @state_checked(Printer0State.DISPLAY_TEST)
    def blank_screen(self) -> None:
        self._printer.screen.blank_screen()

    @auto_dbus
    @state_checked(Printer0State.DISPLAY_TEST)
    def invert_screen(self) -> None:
        self._printer.screen.inverse()

    @auto_dbus
    def leave_test_mode(self) -> None:
        if self._printer.display.state != DisplayState.DISPLAY_TEST:
            return
        hw_all_off(self._printer.hw, self._printer.screen)
        self._printer.display.state = DisplayState.IDLE
