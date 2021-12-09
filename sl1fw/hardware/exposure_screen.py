# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
import logging
import mmap
from time import monotonic, sleep
from threading import Thread, Event
from typing import Optional, Any, List, Tuple
from dataclasses import dataclass, field
from PIL import Image

from pywayland.client import Display
from pywayland.protocol.wayland import WlCompositor, WlSubcompositor, WlShm, WlOutput
from pywayland.protocol.xdg_shell import XdgWmBase
from pywayland.protocol.presentation_time import WpPresentation
from pywayland.utils import AnonymousFile

from sl1fw.hardware.printer_model import PrinterModel, ExposurePanel, ExposureScreenParameters
from sl1fw.errors.errors import UnknownPrinterModel


@dataclass(eq=False)
class Bindings:
    compositor: Any = field(init=False, default=None)
    subcompositor: Any = field(init=False, default=None)
    wm_base: Any = field(init=False, default=None)
    shm: Any = field(init=False, default=None)
    output: Any = field(init=False, default=None)
    presentation: Any = field(init=False, default=None)
    shm_format: int = field(init=False, default=None)


class Layer:
    def __init__(self, bindings: Bindings, width: int, height: int, bytes_per_pixel: int):
        self.bindings = bindings
        self.width = width
        self.height = height
        self.bytes_per_pixel = bytes_per_pixel
        self.pool = None
        self.shm_data = None
        self.surfaces: List[Surface] = []

    @property
    def base_wl_surface(self):
        return self.surfaces[0].wl_surface

    @property
    def base_wl_subsurface(self):
        return self.surfaces[0].wl_subsurface

    def add_surface(self, compositor, subcompositor = None, parent = None, position: Tuple[int, int] = (0,0)):
        surface = Surface(compositor)
        surface.set_opaque(self.width, self.height, compositor)
        if subcompositor:
            surface.set_subsurface(subcompositor, parent, position)
        surface.commit()
        self.surfaces.append(surface)

    def init_surfaces(self):
        self._create_pool()
        for surface in self.surfaces:
            surface.wl_surface.attach(self._create_buffer(), 0, 0)
            surface.wl_surface.commit()

    def delete_surfaces(self):
        for surface in self.surfaces:
            if surface.wl_subsurface:
                surface.wl_subsurface.destroy()
            surface.wl_surface.destroy()
        self.surfaces = []
        self.pool.destroy()

    def redraw(self):
        surface = self.base_wl_surface
        surface.attach(self._create_buffer(), 0, 0)
        surface.damage_buffer(0, 0, self.width, self.height)

    def _create_pool(self):
        size = self.width * self.height * self.bytes_per_pixel
        if self.pool:
            self.pool.destroy()
        with AnonymousFile(size) as fd:
            self.shm_data = mmap.mmap(
                fd, size, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED
            )
            self.pool = self.bindings.shm.create_pool(fd, size)

    def _create_buffer(self):
        stride = self.width * self.bytes_per_pixel
        buffer = self.pool.create_buffer(0, self.width, self.height, stride, self.bindings.shm_format)
        buffer.dispatcher["release"] = self._buffer_release_handler
        return buffer

    @staticmethod
    def _buffer_release_handler(buffer):
        buffer.destroy()


class Surface:
    def __init__(self, compositor):
        self.wl_surface = compositor.create_surface()
        self.wl_subsurface = None

    def set_subsurface(self, subcompositor, parent, position: Tuple[int, int]):
        self.wl_subsurface = subcompositor.get_subsurface(self.wl_surface, parent)
        self.wl_subsurface.set_position(*position)
        self.wl_subsurface.set_sync()
        self.wl_subsurface.place_above(parent)

    def set_opaque(self, width, height, compositor):
        # optimalization: set whole surface opaque
        region = compositor.create_region()
        region.add(0, 0, width, height)
        self.wl_surface.set_opaque_region(region)

    def commit(self):
        self.wl_surface.commit()


def sync_call(function):
    @functools.wraps(function)
    def inner(self, sync: bool, *args):
        main_surface = self.main_layer.base_wl_surface
        if sync:
            feedback = self.bindings.presentation.feedback(main_surface)
            feedback.dispatcher["presented"] = self.feedback_presented_handler
            feedback.dispatcher["discarded"] = self.feedback_discarded_handler
        function(self, main_surface, *args)
        main_surface.commit()
        # show immediately
        self.display.flush()
        if sync:
            self.logger.debug("waiting for video sync event")
            start_time = monotonic()
            if not self.video_sync_event.wait(timeout=2):
                self.logger.error("video sync event timeout")
                # TODO this shouldn't happen, need better handling if yes
                raise RuntimeError("video sync timeout")
            self.video_sync_event.clear()
            self.logger.debug("video sync done in %f ms", 1e3 * (monotonic() - start_time))
            delay = self.parameters.refresh_delay_ms / 1e3
            if delay > 0:
                self.logger.debug("waiting %f ms for display refresh", self.parameters.refresh_delay_ms)
                sleep(delay)
    return inner


class Wayland:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=unused-argument
    # pylint: disable=too-many-arguments
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._thread = Thread(target=self._event_loop)
        self.video_sync_event = Event()
        self.display = Display()
        self.bindings = Bindings()
        self.main_layer: Optional[Layer] = None
        self.blank_layer: Optional[Layer] = None
        self.calibration_layer: Optional[Layer] = None
        self.parameters: Optional[ExposureScreenParameters] = None
        self.format_available = False
        self._stopped = False

    def start(self, parameters: ExposureScreenParameters, shm_format: int):
        self.parameters = parameters
        self.bindings.shm_format = shm_format
        self.display.connect()
        self.logger.debug("connected to display")
        registry = self.display.get_registry()
        registry.dispatcher["global"] = self._registry_global_handler
        registry.dispatcher["global_remove"] = self._registry_global_remover
        self.display.dispatch(block=True)
        self.display.roundtrip()
        if not self.bindings.compositor:
            raise RuntimeError("no wl_compositor found")
        if not self.bindings.subcompositor:
            raise RuntimeError("no wl_subcompositor found")
        if not self.bindings.wm_base:
            raise RuntimeError("no xdg_wm_base found")
        if not self.bindings.shm:
            raise RuntimeError("no wl_shm found")
        if not self.bindings.output:
            raise RuntimeError("no wl_output found")
        if not self.bindings.presentation:
            raise RuntimeError("no wp_presentation found")
        if not self.format_available:
            raise RuntimeError("no suitable shm format available")
        self.main_layer = Layer(
                self.bindings,
                parameters.width_px // parameters.bytes_per_pixel,
                parameters.height_px,
                parameters.bytes_per_pixel)
        self.main_layer.add_surface(self.bindings.compositor)
        main_surface = self.main_layer.base_wl_surface
        xdg_surface = self.bindings.wm_base.get_xdg_surface(main_surface)
        xdg_surface.dispatcher["configure"] = self._xdg_surface_configure_handler
        xdg_toplevel = xdg_surface.get_toplevel()
        xdg_toplevel.set_title("SLA-FW Exposure Output")
        xdg_toplevel.set_app_id("cz.prusa3d.slafw")
        xdg_toplevel.dispatcher["configure"] = self._xdg_toplevel_configure_handler
        xdg_toplevel.dispatcher["close"] = self._xdg_toplevel_close_handler
        self.blank_layer = Layer(
                self.bindings,
                self.main_layer.width,
                self.main_layer.height,
                parameters.bytes_per_pixel)
        self.blank_layer.add_surface(self.bindings.compositor, self.bindings.subcompositor, main_surface)
        main_surface.commit()
        self.display.dispatch(block=True)
        self.display.roundtrip()
        self._thread.start()

    def exit(self):
        self.logger.debug("stopped")
        self._stopped = True
        if self._thread:
            self._thread.join()
        self.main_layer.pool.destroy()
        self.blank_layer.pool.destroy()
        if self.calibration_layer:
            self.calibration_layer.pool.destroy()
        self.display.disconnect()
        self.logger.debug("disconnected from display")

    def _event_loop(self):
        while self.display.dispatch(block=True) != -1 and not self._stopped:
            pass

    def _registry_global_handler(self, registry, id_, interface, version):
        if interface == "wl_compositor":
            self.logger.debug("got wl_compositor")
            self.bindings.compositor = registry.bind(id_, WlCompositor, version)
        elif interface == "wl_subcompositor":
            self.logger.debug("got wl_subcompositor")
            self.bindings.subcompositor = registry.bind(id_, WlSubcompositor, version)
        elif interface == "xdg_wm_base":
            self.logger.debug("got xdg_wm_base")
            self.bindings.wm_base = registry.bind(id_, XdgWmBase, version)
            self.bindings.wm_base.dispatcher["ping"] = self._wm_base_ping_handler
        elif interface == "wl_shm":
            self.logger.debug("got wl_shm")
            self.bindings.shm = registry.bind(id_, WlShm, version)
            self.bindings.shm.dispatcher["format"] = self._shm_format_handler
        elif interface == "wl_output":
            self.logger.debug("got wl_output")
            self.bindings.output = registry.bind(id_, WlOutput, version)
            self.bindings.output.dispatcher["mode"] = self._output_mode_handler
        elif interface == "wp_presentation":
            self.logger.debug("got wp_presentation")
            self.bindings.presentation = registry.bind(id_, WpPresentation, version)

    def _registry_global_remover(self, registry, id_):
        self.logger.debug("got a registry losing event for %d", id_)

    def _wm_base_ping_handler(self, wm_base, serial):
        wm_base.pong(serial)
        self.logger.debug("pinged/ponged")

    def _shm_format_handler(self, shm, shm_format):
        if shm_format == self.bindings.shm_format:
            self.logger.debug("got shm_format")
            self.format_available = True

    def _output_mode_handler(self, wl_output, flags, width, height, refresh):
        self.logger.debug("got output mode - flags:%d width:%d height:%d refresh:%d", flags, width, height, refresh)

    def _xdg_toplevel_configure_handler(self, xdg_toplevel, width, height, states):
        if width != self.main_layer.width or height != self.main_layer.height:
            self.logger.error("Invalid resolution request (%dx%d)", width, height)

    def _xdg_toplevel_close_handler(self, xdg_toplevel):
        self.logger.warning("closed")
        self._stopped = True

    def _xdg_surface_configure_handler(self, xdg_surface, serial):
        xdg_surface.ack_configure(serial)
        self.logger.debug("xdg_surface configure")
        self.blank_layer.init_surfaces()
        self.main_layer.init_surfaces()

    def feedback_presented_handler(self, feedback, tv_sec_hi, tv_sec_lo, tv_nsec, refresh, seq_hi, seq_lo, flags):
        self.logger.debug("presented feedback (%d, %d, %d, %d, %d, %d, %d)", tv_sec_hi, tv_sec_lo, tv_nsec, refresh, seq_hi, seq_lo, flags)
        self.video_sync_event.set()

    def feedback_discarded_handler(self, feedback):
        self.logger.warning("discarded feedback")

    @sync_call
    def show(self, main_surface, image: bytes):
        self.main_layer.shm_data.seek(0)   # type: ignore
        self.main_layer.shm_data.write(image)  # type: ignore
        self.main_layer.redraw()
        self.blank_layer.base_wl_subsurface.place_below(main_surface)
        if self.calibration_layer:
            for surface in self.calibration_layer.surfaces:
                surface.wl_subsurface.place_below(main_surface)

    @sync_call
    def blank_screen(self, main_surface):
        self.blank_layer.base_wl_subsurface.place_above(main_surface)

    def create_areas(self, areas):
        if self.calibration_layer:
            self.calibration_layer.delete_surfaces()
            self.calibration_layer = None
        if areas:
            width, height = areas[0].size
            self.calibration_layer = Layer(
                    self.bindings,
                    width // self.parameters.bytes_per_pixel,
                    height,
                    self.parameters.bytes_per_pixel)
            main_surface = self.main_layer.base_wl_surface
            for area in areas:
                self.calibration_layer.add_surface(
                        self.bindings.compositor,
                        self.bindings.subcompositor,
                        main_surface,
                        (area.x1 // self.parameters.bytes_per_pixel, area.y1))
            self.calibration_layer.init_surfaces()

    @sync_call
    def blank_area(self, main_surface, area_index: int):
        self.calibration_layer.surfaces[area_index].wl_subsurface.place_above(main_surface)


class ExposureScreen:
    def __init__(self):
        self.parameters = PrinterModel.NONE.exposure_screen_parameters
        self.panel: Optional[ExposurePanel] = None
        self.logger = logging.getLogger(__name__)
        self._wayland = Wayland()

    def start(self) -> PrinterModel:
        model = self._detect_model()
        if model == PrinterModel.NONE:
            raise UnknownPrinterModel()
        self._wayland.start(self.parameters, self._find_format())
        return model

    def exit(self):
        self._wayland.exit()

    def _find_format(self):
        if self.parameters.bytes_per_pixel == 1:
            return WlShm.format.r8.value
        if self.parameters.bgr_pixels:
            return WlShm.format.bgr888.value
        return WlShm.format.rgb888.value

    def _detect_model(self):
        self.panel = ExposurePanel
        model = self.panel.printer_model()
        self.parameters = model.exposure_screen_parameters
        if model == PrinterModel.NONE:
            self.logger.error("Unknown printer model (panel name: '%s')", self.panel.panel_name())
        else:
            self.logger.info("Detected printer model: %s", model.name)
            self.logger.info("Exposure panel serial number: %s", self.panel.serial_number())
            self.logger.info("Exposure panel transmittance: %s", self.panel.transmittance())
        return model

    def show(self, image: Image, sync: bool = True):
        if image.size != self.parameters.size_px:
            self.logger.error("Invalid image size %s. Output is %s", str(image.size), str(self.parameters.size_px))
            return
        if image.mode != "L":
            self.logger.error("Invalid pixel format %s. 'L' is required.", image.mode)
            return
        self._wayland.show(sync, image.tobytes())

    def blank_screen(self, sync: bool = True):
        self._wayland.blank_screen(sync)

    def create_areas(self, areas):
        self._wayland.create_areas(areas)

    def blank_area(self, area_index: int, sync: bool = True):
        self._wayland.blank_area(sync, area_index)
