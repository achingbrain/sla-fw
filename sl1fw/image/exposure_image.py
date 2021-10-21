# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from logging.handlers import QueueListener
from multiprocessing import Process, shared_memory, Queue
import os
from time import monotonic
from typing import Optional

import numpy
from PIL import Image, ImageOps

from sl1fw import defines
from sl1fw.errors.errors import PreloadFailed
from sl1fw.libHardware import Hardware
from sl1fw.project.project import Project
from sl1fw.project.functions import get_white_pixels
from sl1fw.image.resin_calibration import Calibration
from sl1fw.image.preloader import Preloader, SLIDX, SHMIDX, ProjectFlags
from sl1fw.errors.errors import ProjectErrorCalibrationInvalid
from sl1fw.errors.warnings import PerPartesPrintNotAvaiable, PrintMaskNotAvaiable, PrintedObjectWasCropped


class ExposureImage:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, hardware: Hardware):
        self._hw = hardware
        self._logger = logging.getLogger(__name__)
        self._project: Optional[Project] = None
        self._calibration: Optional[Calibration] = None
        self._buffer: Optional[Image] = None
        self._sl: Optional[shared_memory.ShareableList] = None
        self._shm: Optional[list] = None
        self._preloader: Optional[Process] = None
        self._preloader_log_queue: Queue = Queue()
        self._preloader_log_listener: QueueListener = \
            QueueListener(self._preloader_log_queue, *logging.getLogger().handlers)
        self._start_preload: Queue = Queue()
        self._preload_result: Queue = Queue()

    def start(self):
        # numpy uses reversed axis indexing
        image_bytes_count = self._hw.exposure_screen.parameters.width_px * self._hw.exposure_screen.parameters.height_px
        temp_usage = numpy.zeros(self._hw.exposure_screen.parameters.display_usage_size_px, dtype=numpy.float64, order='C')
        # see SLIDX!!!
        self._sl = shared_memory.ShareableList(sequence=[
                0,
                0,
                0,
                0,
                0,
                0,
                0])
        shm_prefix = self._sl.shm.name
        # see SHMIDX!!!
        self._shm = [
                shared_memory.SharedMemory(create=True, size=image_bytes_count, name=shm_prefix+SHMIDX.PROJECT_IMAGE.name),
                shared_memory.SharedMemory(create=True, size=image_bytes_count, name=shm_prefix+SHMIDX.PROJECT_PPM1.name),
                shared_memory.SharedMemory(create=True, size=image_bytes_count, name=shm_prefix+SHMIDX.PROJECT_PPM2.name),
                shared_memory.SharedMemory(create=True, size=image_bytes_count, name=shm_prefix+SHMIDX.PROJECT_MASK.name),
                shared_memory.SharedMemory(create=True, size=image_bytes_count, name=shm_prefix+SHMIDX.OUTPUT_IMAGE1.name),
                shared_memory.SharedMemory(create=True, size=image_bytes_count, name=shm_prefix+SHMIDX.OUTPUT_IMAGE2.name),
                shared_memory.SharedMemory(create=True, size=temp_usage.nbytes, name=shm_prefix+SHMIDX.DISPLAY_USAGE.name),
                shared_memory.ShareableList(range(5), name=shm_prefix+SHMIDX.PROJECT_BBOX.name),
                shared_memory.ShareableList(range(5), name=shm_prefix+SHMIDX.PROJECT_FL_BBOX.name),
                shared_memory.ShareableList(range(11), name=shm_prefix+SHMIDX.PROJECT_TIMES_MS.name)]
        self._preloader = Preloader(self._hw.exposure_screen.parameters, self._start_preload, self._preload_result, shm_prefix,
                                    self._preloader_log_queue)
        self._preloader_log_listener.start()
        self._preloader.start()
        self._buffer = Image.new("L", self._hw.exposure_screen.parameters.size_px)

    def exit(self):
        if self._preloader:
            self._preloader.join()
            self._preloader_log_listener.stop()
        if self._sl:
            self._sl.shm.close()
            self._sl.shm.unlink()
        if self._shm:
            for shm in self._shm:
                if isinstance(shm, shared_memory.SharedMemory):
                    shm.close()
                    shm.unlink()
                else:
                    shm.shm.close()
                    shm.shm.unlink()

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
        # pylint: disable=too-many-statements
        # Remove live preview from last run
        if os.path.exists(defines.livePreviewImage):
            os.remove(defines.livePreviewImage)
        self._project = project
        self._calibration = None
        project_flags = ProjectFlags.NONE
        usage: numpy.ndarray = numpy.ndarray(
                self._hw.exposure_screen.parameters.display_usage_size_px,
                dtype=numpy.float64,
                order='C',
                buffer=self._shm[SHMIDX.DISPLAY_USAGE].buf)
        usage.fill(0.0)
        if self._project.per_partes:
            try:
                image1 = Image.frombuffer("L", self._hw.exposure_screen.parameters.size_px, self._shm[SHMIDX.PROJECT_PPM1].buf, "raw", "L", 0, 1)
                image1.readonly = False
                image1.paste(self._open_image(os.path.join(
                    defines.dataPath, self._hw.printer_model.name, defines.perPartesMask)))
                image2 = Image.frombuffer("L", self._hw.exposure_screen.parameters.size_px, self._shm[SHMIDX.PROJECT_PPM2].buf, "raw", "L", 0, 1)
                image2.readonly = False
                image2.paste(ImageOps.invert(image1))
                project_flags |= ProjectFlags.PER_PARTES
            except Exception:
                self._logger.exception("per partes masks exception")
                self._project.warnings.add(PerPartesPrintNotAvaiable())
                # reset the flag for Exposure
                self._project.per_partes = False
        try:
            mask = Image.frombuffer("L", self._hw.exposure_screen.parameters.size_px, self._shm[SHMIDX.PROJECT_MASK].buf, "raw", "L", 0, 1)
            mask.readonly = False
            mask.paste(ImageOps.invert(self._project.read_image(defines.maskFilename)))
            project_flags |= ProjectFlags.USE_MASK
        except KeyError:
            self._logger.info("No mask picture in the project")
        except Exception:
            self._logger.exception("project mask exception")
            self._project.warnings.add(PrintMaskNotAvaiable())
        if self._project.calibrate_regions:
            self._project.analyze()
            self._calibration = Calibration(self._hw.exposure_screen.parameters.size_px)
            if not self._calibration.new_project(
                    self._project.bbox,
                    self._project.layers[0].bbox,
                    self._project.calibrate_regions,
                    self._project.calibrate_compact,
                    self._project.layers[-1].times_ms,
                    self._project.calibrate_penetration_px,
                    self._project.calibrate_text_size_px,
                    self._project.calibrate_pad_spacing_px):
                raise ProjectErrorCalibrationInvalid
            if self._calibration.is_cropped:
                self._project.warnings.add(PrintedObjectWasCropped())
        if self._project.calibrate_compact:
            project_flags |= ProjectFlags.CALIBRATE_COMPACT
        self._sl[SLIDX.PROJECT_SERIAL] += 1
        self._sl[SLIDX.PROJECT_FLAGS] = project_flags.value
        self._write_SL(self._shm[SHMIDX.PROJECT_BBOX], self._project.bbox.coords)
        self._write_SL(self._shm[SHMIDX.PROJECT_FL_BBOX], self._project.layers[0].bbox.coords)
        self._write_SL(self._shm[SHMIDX.PROJECT_TIMES_MS], self._project.layers[-1].times_ms)
        self._sl[SLIDX.PROJECT_CALIBRATE_REGIONS] = self._project.calibrate_regions
        self._sl[SLIDX.PROJECT_CALIBRATE_PENETRATION_PX] = self._project.calibrate_penetration_px
        self._sl[SLIDX.PROJECT_CALIBRATE_TEXT_SIZE_PX] = self._project.calibrate_text_size_px
        self._sl[SLIDX.PROJECT_CALIBRATE_PAD_SPACING_PX] = self._project.calibrate_pad_spacing_px
        self._sl[SLIDX.WHITE_PIXELS_THRESHOLD] = self._hw.white_pixels_threshold

    @staticmethod
    def _write_SL(dst, src):
        # pylint: disable=consider-using-enumerate
        dst[0] = len(src)
        for i in range(len(src)):
            dst[i+1] = src[i]

    def blank_screen(self):
        self._logger.debug("blank started")
        start_time = monotonic()
        self._buffer.paste(0, (0, 0, self._hw.exposure_screen.parameters.width_px, self._hw.exposure_screen.parameters.height_px))
        self._hw.exposure_screen.show(self._buffer)
        self._logger.debug("blank done in %f secs", monotonic() - start_time)

    def fill_area(self, area_index, color=0):
        if self._calibration and area_index < len(self._calibration.areas):
            self._logger.debug("fill area %d", area_index)
            start_time = monotonic()
            self._buffer.paste(color, self._calibration.areas[area_index].coords)
            self._hw.exposure_screen.show(self._buffer)
            self._logger.debug("fill area done in %f secs", monotonic() - start_time)

    def show_system_image(self, filename: str):
        self.show_image_with_path(os.path.join(defines.dataPath, self._hw.printer_model.name, filename))

    def show_image_with_path(self, filename_with_path: str):
        self._logger.debug("show of %s started", filename_with_path)
        start_time = monotonic()
        self._buffer = self._open_image(filename_with_path)
        self._hw.exposure_screen.show(self._buffer)
        self._logger.debug("show of %s done in %f secs", filename_with_path, monotonic() - start_time)

    def preload_image(self, layer_index: int, second=False):
        if second:
            self._logger.debug("second part of image - no preloading")
            return
        if layer_index >= self._project.total_layers:
            self._logger.debug("layer_index is beyond the layers count - no preloading")
            return
        if not self._preloader.is_alive():
            self._logger.error("Preloader process is not running, exitcode: %d", self._preloader.exitcode)
            raise PreloadFailed()
        try:
            layer = self._project.layers[layer_index]
            self._logger.debug("read image %s from project started", layer.image)
            start_time = monotonic()
            input_image = self._project.read_image(layer.image)
            self._logger.debug("read of '%s' done in %f secs", layer.image, monotonic() - start_time)
        except Exception as e:
            self._logger.exception("read image exception:")
            raise PreloadFailed() from e
        image = Image.frombuffer("L", self._hw.exposure_screen.parameters.size_px, self._shm[SHMIDX.PROJECT_IMAGE].buf, "raw", "L", 0, 1)
        image.readonly = False
        image.paste(input_image)
        self._start_preload.put(layer.calibration_type.value)

    def sync_preloader(self) -> int:
        self._logger.debug("syncing preloader")
        try:
            return self._preload_result.get(timeout=5)
        except Exception as e:
            self._logger.exception("sync preloader exception:")
            raise PreloadFailed() from e

    def blit_image(self, second=False):
        self._logger.debug("blit started")
        start_time = monotonic()
        source_shm = self._shm[SHMIDX.OUTPUT_IMAGE2].buf if second else self._shm[SHMIDX.OUTPUT_IMAGE1].buf
        self._buffer = Image.frombuffer("L", self._hw.exposure_screen.parameters.size_px, source_shm, "raw", "L", 0, 1).copy()
        self._hw.exposure_screen.show(self._buffer)
        self._logger.debug("get result and blit done in %f secs", monotonic() - start_time)

    def screenshot_rename(self, second=False):
        start_time = monotonic()
        try:
            os.rename(defines.livePreviewImage + "-tmp%s.png" % ("2" if second else "1"), defines.livePreviewImage)
        except Exception:
            self._logger.exception("Screenshot rename exception:")
        self._logger.debug("rename done in %f secs", monotonic() - start_time)

    def inverse(self):
        self._logger.debug("inverse started")
        start_time = monotonic()
        self._buffer = ImageOps.invert(self._buffer)
        self._hw.exposure_screen.show(self._buffer)
        self._logger.debug("inverse done in %f secs", monotonic() - start_time)

    def save_display_usage(self):
        usage = numpy.ndarray(
                self._hw.exposure_screen.parameters.display_usage_size_px,
                dtype=numpy.float64,
                order='C',
                buffer=self._shm[SHMIDX.DISPLAY_USAGE].buf)
        try:
            with numpy.load(defines.displayUsageData) as npzfile:
                saved_data = npzfile['display_usage']
                if saved_data.shape != self._hw.exposure_screen.parameters.display_usage_size_px:
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
