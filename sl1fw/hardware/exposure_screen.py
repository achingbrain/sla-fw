# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import mmap
from time import time, sleep
from threading import Thread, Event
from typing import Optional
from PIL import Image

from pywayland.client import Display
from pywayland.protocol.wayland import WlCompositor, WlShm, WlOutput
from pywayland.protocol.xdg_shell import XdgWmBase
from pywayland.protocol.presentation_time import WpPresentation
from pywayland.utils import AnonymousFile

from sl1fw.hardware.printer_model import PrinterModel, ExposurePanel
from sl1fw.errors.errors import UnknownPrinterModel


class ExposureScreen:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=unused-argument
    # pylint: disable=too-many-arguments
    def __init__(self):
        self.parameters = PrinterModel.NONE.exposure_screen_parameters

        self._logger = logging.getLogger(__name__)
        self._compositor = None
        self._wm_base = None
        self._shm = None
        self._output = None
        self._presentation = None
        self._format_available = False
        self._resolution = (0, 0)
        self._referesh_delay_s = 0.0
        self._surface = None
        self._shm_data = None
        self._frame_callback = None
        self._buffer = None
        self._stopped = False
        self._image: Optional[bytes] = None
        self._new_image = True
        self._presentation_feedback = None
        self._video_sync_event = Event()
        self._thread: Optional[Thread] = None
        self._display = None
        self.panel: ExposurePanel = None


    def start(self) -> PrinterModel:
        model = self._detect_model()
        if model == PrinterModel.NONE:
            raise UnknownPrinterModel()

        self._display = Display()
        self._display.connect()
        self._logger.debug("connected to display")

        registry = self._display.get_registry()
        registry.dispatcher["global"] = self._registry_global_handler
        registry.dispatcher["global_remove"] = self._registry_global_remover

        self._display.dispatch(block=True)
        self._display.roundtrip()

        if not self._compositor:
            raise RuntimeError("no wl_compositor found")
        if not self._wm_base:
            raise RuntimeError("no xdg_wm_base found")
        if not self._shm:
            raise RuntimeError("no wl_shm found")
        if not self._output:
            raise RuntimeError("no wl_output found")
        if not self._presentation:
            raise RuntimeError("no wp_presentation found")
        if not self._format_available:
            raise RuntimeError("no suitable shm format available")

        self._thread = Thread(target=self._event_loop)
        self._thread.start()

        return model


    def exit(self):
        self._logger.debug("stopped")
        self._stopped = True
        if self._thread:
            self._thread.join()


    def _event_loop(self):
        self._surface = self._compositor.create_surface()

        xdg_surface = self._wm_base.get_xdg_surface(self._surface)
        xdg_surface.dispatcher["configure"] = self._xdg_surface_configure_handler

        xdg_toplevel = xdg_surface.get_toplevel()
        xdg_toplevel.set_title("SLA-FW Exposure Output")
        xdg_toplevel.set_app_id("cz.prusa3d.slafw")
        xdg_toplevel.dispatcher["configure"] = self._xdg_toplevel_configure_handler
        xdg_toplevel.dispatcher["close"] = self._xdg_toplevel_close_handler

        self._surface.commit()

        self._frame_callback = self._surface.frame()
        self._frame_callback.dispatcher["done"] = self._frame_callback_handler

        while self._display.dispatch(block=True) != -1 and not self._stopped:
            pass
        self._display.disconnect()
        self._logger.debug("disconnected from display")


    def _registry_global_handler(self, registry, id_, interface, version):
        if interface == "wl_compositor":
            self._logger.debug("got wl_compositor")
            self._compositor = registry.bind(id_, WlCompositor, version)
        elif interface == "xdg_wm_base":
            self._logger.debug("got xdg_wm_base")
            self._wm_base = registry.bind(id_, XdgWmBase, version)
            self._wm_base.dispatcher["ping"] = self._wm_base_ping_handler
        elif interface == "wl_shm":
            self._logger.debug("got wl_shm")
            self._shm = registry.bind(id_, WlShm, version)
            self._shm.dispatcher["format"] = self._shm_format_handler
        elif interface == "wl_output":
            self._logger.debug("got wl_output")
            self._output = registry.bind(id_, WlOutput, version)
            self._output.dispatcher["mode"] = self._output_mode_handler
        elif interface == "wp_presentation":
            self._logger.debug("got wp_presentation")
            self._presentation = registry.bind(id_, WpPresentation, version)


    def _registry_global_remover(self, registry, id_):
        self._logger.debug("got a registry losing event for %d", id_)


    def _wm_base_ping_handler(self, wm_base, serial):
        wm_base.pong(serial)
        self._logger.debug("pinged/ponged")


    def _shm_format_handler(self, shm, format_):
        if format_ == WlShm.format.xrgb8888.value:
            self._logger.debug("got shm format")
            self._format_available = True


    def _output_mode_handler(self, wl_output, flags, width, height, referesh):
        self._logger.debug("got output mode - flags:%d width:%d height:%d referesh:%d", flags, width, height, referesh)


    def _xdg_surface_configure_handler(self, xdg_surface, serial):
        self._logger.debug("xdg_surface configure")
        xdg_surface.ack_configure(serial)
        self._create_buffer()
        self._fill_buffer()
        # show immediately
        self._display.flush()


    def _xdg_toplevel_close_handler(self, xdg_toplevel):
        self._logger.warning("window closed")
        self._stopped = True


    def _xdg_toplevel_configure_handler(self, xdg_toplevel, width, height, states):
        self._logger.debug("resolution change request to %dx%d", width, height)
        if width != self._resolution[0] or height != self._resolution[1]:
            self._resolution = (width, height)


    def _detect_model(self):
        self.panel = ExposurePanel
        model = self.panel.printer_model()
        self.parameters = model.exposure_screen_parameters
        if model == PrinterModel.NONE:
            self._logger.error("Unknown printer model (panel name: '%s')", self.panel.panel_name())
        else:
            self._logger.info("Detected printer model: %s", model.name)
            self._logger.info("Exposure panel serial number: %s", self.panel.serial_number())
            self._logger.info("Exposure panel transmittance: %s", self.panel.transmittance())
            self._referesh_delay_s = self.parameters.referesh_delay_ms / 1000
        return model


    def _create_buffer(self):
        stride = self._resolution[0] * 4
        size = stride * self._resolution[1]
        with AnonymousFile(size) as fd:
            self._shm_data = mmap.mmap(fd, size, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED)
            pool = self._shm.create_pool(fd, size)
            self._buffer = pool.create_buffer(0, self._resolution[0], self._resolution[1], stride, WlShm.format.xrgb8888.value)
            pool.destroy()
        self._new_image = True


    def _fill_buffer(self):
        if self._new_image and self._image:
            self._shm_data.seek(0)
            self._shm_data.write(self._image)
            self._surface.damage_buffer(0, 0, self._resolution[0], self._resolution[1])
            self._presentation_feedback = self._presentation.feedback(self._surface)
            self._presentation_feedback.dispatcher["presented"] = self._feedback_presented_handler
            self._presentation_feedback.dispatcher["discarded"] = self._feedback_discarded_handler
            self._new_image = False
        self._surface.attach(self._buffer, 0, 0)
        self._surface.commit()


    def _frame_callback_handler(self, callback, calback_time):
        callback.destroy()
        self._frame_callback = self._surface.frame()
        self._frame_callback.dispatcher["done"] = self._frame_callback_handler
        self._fill_buffer()


    def _feedback_presented_handler(self, feedback, tv_sec_hi, tv_sec_lo, tv_nsec, refresh, seq_hi, seq_lo, flags):
        self._logger.debug("feedback_presented_handler(%d, %d, %d, %d, %d, %d, %d)", tv_sec_hi, tv_sec_lo, tv_nsec, refresh, seq_hi, seq_lo, flags)
        self._video_sync_event.set()


    def _feedback_discarded_handler(self, feedback):
        self._logger.warning("got discarded feedback")


    def show(self, image: Image, sync = True):
        if image.size != self.parameters.size_px:
            self._logger.error("Invalid image size %s. Output is %s", str(image.size), str(self.parameters.size_px))
            return
        if self.parameters.monochromatic:
            bit24 = Image.frombytes("RGB", self._resolution, image.tobytes())
            if self.parameters.backwards:
                bit32 = bit24.convert("BGR;32")
            else:
                bit32 = bit24.convert("RGBX")
        else:
            bit32 = image.convert("RGBX")
        self._image = bit32.tobytes()
        self._new_image = True
        if sync:
            self.sync()


    def sync(self):
        self._logger.debug("waiting for video sync event")
        start_time = time()
        if not self._video_sync_event.wait(timeout=2):
            self._logger.error("video sync event timeout")
            # TODO this shouldn't happen, need better handling if yes
            raise RuntimeError("video sync timeout")
        self._video_sync_event.clear()
        self._logger.debug("video sync done in %f secs", time() - start_time)
        if self._referesh_delay_s > 0:
            self._logger.debug("waiting %f secs for display referesh", self._referesh_delay_s)
            sleep(self._referesh_delay_s)
