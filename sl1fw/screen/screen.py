# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from multiprocessing import Process, shared_memory, Value, Lock
import os
from time import time
from typing import Optional

from ctypes import c_uint32
import numpy
from PIL import Image, ImageOps

from sl1fw import defines, test_runtime
from sl1fw.libConfig import HwConfig
from sl1fw.errors.errors import PreloadFailed
from sl1fw.project.project import Project
from sl1fw.project.functions import get_white_pixels
from sl1fw.screen.resin_calibration import Calibration
from sl1fw.screen.wayland import Wayland
from sl1fw.screen.printer_model import PrinterModel
from sl1fw.errors.warnings import PerPartesPrintNotAvaiable, PrintMaskNotAvaiable


class Screen:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, hw_config: HwConfig):
        self._logger = logging.getLogger(__name__)
        self._hw_config = hw_config
        self._project: Optional[Project] = None
        self._overlays = {}
        self._calibration: Optional[Calibration] = None
        self._output: Optional[Wayland] = None
        self._buffer: Optional[Image] = None
        self._preloader: Optional[Process] = None
        self._last_preload_index: Optional[int] = None
        self._next_image_1_shm: Optional[shared_memory.SharedMemory] = None
        self._next_image_2_shm: Optional[shared_memory.SharedMemory] = None
        self._usage_shm: Optional[shared_memory.SharedMemory] = None
        self._preloader_lock = Lock()

        self._output = Wayland()    # may throw exception
        # FIXME this is ugly but can't mock this :-(
        if test_runtime.testing:
            self._output.printer_model = PrinterModel.SL1
            self._output.exposure_screen = self._output.printer_model.exposure_screen
        self.live_preview_size_px = (self.exposure_screen.width_px // defines.thumbnail_factor, self.exposure_screen.height_px // defines.thumbnail_factor)
        # numpy uses reversed axis indexing
        self.display_usage_size = (self.exposure_screen.height_px // defines.thumbnail_factor, self.exposure_screen.width_px // defines.thumbnail_factor)
        self.display_usage_shape = (self.display_usage_size[0], defines.thumbnail_factor, self.display_usage_size[1], defines.thumbnail_factor)
        self._next_image_1_shm = shared_memory.SharedMemory(create=True, size=self.exposure_screen.width_px * self.exposure_screen.height_px)
        self._next_image_2_shm = shared_memory.SharedMemory(create=True, size=self.exposure_screen.width_px * self.exposure_screen.height_px)
        temp_usage = numpy.zeros(self.display_usage_size, dtype=numpy.float64, order='C')
        self._usage_shm = shared_memory.SharedMemory(create=True, size=temp_usage.nbytes)
        self._white_pixels = Value(c_uint32, 0)
        self._black_image = Image.new("L", self.exposure_screen.size_px)
        self._buffer = self._black_image.copy()

    def __del__(self):
        if self._next_image_1_shm:
            self._next_image_1_shm.close()
            self._next_image_1_shm.unlink()
        if self._next_image_2_shm:
            self._next_image_2_shm.close()
            self._next_image_2_shm.unlink()
        if self._usage_shm:
            self._usage_shm.close()
            self._usage_shm.unlink()
        if self._output:
            self._output.stop()

    def _open_image(self, filename):
        self._logger.debug("loading '%s'", filename)
        img = Image.open(filename)
        if img.mode != "L":
            self._logger.warning("Image '%s' is in '%s' mode, should be 'L' (grayscale without alpha)."
                                " Losing time in conversion.",
                                filename, img.mode)
            img = img.convert("L")
        return img

    def new_project(self, project: Project):
        # Remove live preview from last run
        if os.path.exists(defines.livePreviewImage):
            os.remove(defines.livePreviewImage)
        self._project = project
        self._overlays = {}
        self._calibration = None
        usage = numpy.ndarray(self.display_usage_size, dtype=numpy.float64, order='C', buffer=self._usage_shm.buf)
        usage.fill(0.0)
        if self._project.per_partes:
            try:
                self._overlays['ppm1'] = self._open_image(os.path.join(
                    defines.dataPath, self.printer_model.name, defines.perPartesMask))
                self._overlays['ppm2'] = ImageOps.invert(self._overlays['ppm1'])
            except Exception:
                self._logger.exception("per partes masks exception")
                self._project.warnings.add(PerPartesPrintNotAvaiable())
                self._project.per_partes = False
        try:
            img = self._project.read_image(defines.maskFilename)
            self._overlays['mask'] = ImageOps.invert(img)
        except KeyError:
            self._logger.info("No mask picture in the project")
        except Exception:
            self._logger.exception("project mask exception")
            self._project.warnings.add(PrintMaskNotAvaiable())
        self._calibration = Calibration(self.exposure_screen)
        self._calibration.new_project(self._project)

    def blank_screen(self):
        self._buffer = self._black_image.copy()
        self._output.show(self._buffer)

    def fill_area(self, area_index, color=0):
        if self._calibration and area_index < len(self._calibration.areas):
            self._logger.debug("fill area %d", area_index)
            self._buffer.paste(color, self._calibration.areas[area_index].coords)
            self._output.show(self._buffer)
            self._logger.debug("fill area end")

    def show_system_image(self, filename: str):
        self.show_image_with_path(os.path.join(defines.dataPath, self.printer_model.name, filename))

    def show_image_with_path(self, filename_with_path: str):
        self._logger.debug("show of %s started", filename_with_path)
        start_time = time()
        self._buffer = self._open_image(filename_with_path)
        self._output.show(self._buffer)
        self._logger.debug("show of %s done in %f secs", filename_with_path, time() - start_time)

    def preload_image(self, layer_index: int, second=False):
        if second:
            self._logger.debug("second part of image - no preloading")
            return
        if layer_index >= self._project.total_layers:
            self._logger.debug("layer_index is beyond the layers count - no preloading")
            return
        self._last_preload_index = layer_index
        if not self._preloader_lock.acquire(timeout=5):
            self._logger.error("preloader lock timeout")
            # TODO this shouldn't happen, need better handling if yes
            raise PreloadFailed()
        self._preloader = Process(target=self.preloader, args=(layer_index,))
        self._preloader.start()

    def preloader(self, layer_index: int):
        try:
            layer = self._project.layers[layer_index]
            self._logger.debug("preload of %s started", layer.image)
            startTimeFirst = time()
            input_image = self._project.read_image(layer.image)
            self._logger.debug("load of '%s' done in %f secs", layer.image, time() - startTimeFirst)
            output_image = Image.frombuffer("L", self.exposure_screen.size_px, self._next_image_1_shm.buf, "raw", "L", 0, 1)
            output_image.readonly = False
            if self._calibration.areas:
                start_time = time()
                crop = input_image.crop(self._project.bbox.coords)
                output_image.paste(self._black_image)
                for area in self._calibration.areas:
                    area.paste(output_image, crop, layer.calibration_type)
                self._logger.debug("multiplying done in %f secs", time() - start_time)
            else:
                output_image.paste(input_image)
            overlay = self._overlays.get('mask', None)
            if overlay:
                output_image.paste(self._black_image, mask=overlay)
            start_time = time()
            pixels = numpy.array(output_image)
            usage = numpy.ndarray(self.display_usage_size, dtype=numpy.float64, order='C', buffer=self._usage_shm.buf)
            # 1500 layers on 0.1 mm layer height <0:255> -> <0.0:1.0>
            usage += numpy.reshape(pixels, self.display_usage_shape).mean(axis=3).mean(axis=1) / 382500
            white_pixels = get_white_pixels(output_image)
            self._logger.debug("pixels manipulations done in %f secs, white pixels: %d",
                    time() - start_time, white_pixels)
            if self._project.per_partes and white_pixels > self.white_pixels_threshold:
                output_image_second = Image.frombuffer("L", self.exposure_screen.size_px, self._next_image_2_shm.buf, "raw", "L", 0, 1)
                output_image_second.readonly = False
                output_image_second.paste(output_image)
                output_image.paste(self._black_image, mask=self._overlays['ppm1'])
                output_image_second.paste(self._black_image, mask=self._overlays['ppm2'])
                self._screenshot(output_image_second, "2")
            self._screenshot(output_image, "1")
            self._white_pixels.value = white_pixels
            self._logger.debug("preload of %s done in %f secs", layer.image, time() - startTimeFirst)
        finally:
            self._preloader_lock.release()

    def _screenshot(self, image: Image, number: str):
        try:
            start_time = time()
            preview = image.resize(self.live_preview_size_px, Image.BICUBIC)
            self._logger.debug("resize done in %f secs", time() - start_time)
            start_time = time()
            preview.save(defines.livePreviewImage + "-tmp%s.png" % number)
            self._logger.debug("screenshot done in %f secs", time() - start_time)
        except Exception:
            self._logger.exception("Screenshot exception:")

    def _sync_preloader(self):
        self._logger.debug("sync preloader started")
        self._preloader.join(5)
        if self._preloader.exitcode != 0:
            if self._preloader.exitcode is None:
                self._logger.error("Preloader did not finish yet!")
            else:
                self._logger.error("Preloader exit code: %d (%s)", self._preloader.exitcode, os.strerror(self._preloader.exitcode))
            # TODO this shouldn't happen, need better handling if yes
            raise PreloadFailed()

    def blit_image(self, second=False):
        self._sync_preloader()
        start_time = time()
        self._logger.debug("blit started")
        source_shm = self._next_image_2_shm if second else self._next_image_1_shm
        self._buffer = Image.frombuffer("L", self.exposure_screen.size_px, source_shm.buf, "raw", "L", 0, 1).copy()
        self._output.show(self._buffer)
        self._logger.debug("get result and blit done in %f secs", time() - start_time)
        return self._white_pixels.value

    def screenshot_rename(self, second=False):
        self._sync_preloader()
        start_time = time()
        try:
            os.rename(defines.livePreviewImage + "-tmp%s.png" % ("2" if second else "1"), defines.livePreviewImage)
        except Exception:
            self._logger.exception("Screenshot rename exception:")
        self._logger.debug("rename done in %f secs", time() - start_time)

    def inverse(self):
        self._logger.debug("inverse started")
        start_time = time()
        self._buffer = ImageOps.invert(self._buffer)
        self._output.show(self._buffer)
        self._logger.debug("inverse done in %f secs", time() - start_time)

    def save_display_usage(self):
        self._sync_preloader()
        usage = numpy.ndarray(self.display_usage_size, dtype=numpy.float64, order='C', buffer=self._usage_shm.buf)
        try:
            with numpy.load(defines.displayUsageData) as npzfile:
                saved_data = npzfile['display_usage']
                if saved_data.shape != self.display_usage_size:
                    self._logger.warning("Wrong saved data shape: %s", saved_data.shape)
                else:
                    usage += saved_data
        except FileNotFoundError:
            self._logger.warning("File '%s' not found", defines.displayUsageData)
        except Exception:
            self._logger.exception("Load display usage failed")
        numpy.savez_compressed(defines.displayUsageData, display_usage=usage)

    @property
    def is_screen_blank(self) -> bool:
        return get_white_pixels(self._buffer) == 0

    @property
    def buffer(self):
        "read only"
        return self._buffer

    @property
    def exposure_screen(self):
        "read only"
        return self._output.exposure_screen

    @property
    def printer_model(self):
        "read only"
        return self._output.printer_model

    @property
    def white_pixels_threshold(self) -> int:
        return self.exposure_screen.width_px * self.exposure_screen.height_px * self._hw_config.limit4fast // 100
