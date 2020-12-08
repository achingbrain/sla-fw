# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from multiprocessing import Process, shared_memory, Value, Lock
from threading import Event
import os
from time import monotonic, time
from typing import Optional

from ctypes import c_uint32
import numpy
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydbus import SystemBus

from sl1fw import defines, test_runtime
from sl1fw.errors.errors import PreloadFailed
from sl1fw.project.project import Project
from sl1fw.states.project import ProjectErrors, ProjectWarnings, LayerCalibrationType
from sl1fw.project.functions import get_white_pixels
from sl1fw.utils.bounding_box import BBox


class Area(BBox):
    # pylint: disable=unused-argument
    def __init__(self, coords=None):
        super().__init__(coords)
        self._copy_position = 0, 0

    def set_copy_position(self, bbox: BBox):
        self._copy_position = self.x1, self.y1

    def set_label_text(self, font, text, text_padding, label_size):
        pass

    def set_label_position(self, label_size, project: Project):
        pass

    def paste(self, image: Image, source: Image, calibration_type: LayerCalibrationType):
        image.paste(source, box=self._copy_position)

class AreaWithLabel(Area):
    def __init__(self, coords=None):
        super().__init__(coords)
        self._text_layer: Optional[Image] = None
        self._pad_layer: Optional[Image] = None
        self._label_position = 0, 0

    def _transpose(self, image: Image):
        # pylint: disable=no-self-use
        return image.transpose(Image.FLIP_LEFT_RIGHT)

    def set_copy_position(self, bbox: BBox):
        bbox_size = bbox.size
        self_size = self.size
        self._copy_position = self.x1 + (self_size[0] - bbox_size[0]) // 2, self.y1 + (self_size[1] - bbox_size[1]) // 2
        self._logger.debug("copy position: %s", str(self._copy_position))

    def set_label_text(self, font, text, text_padding, label_size):
        self._logger.debug("calib. label size: %s  text padding: %s", str(label_size), str(text_padding))
        tmp = Image.new("L", label_size)
        tmp_draw = ImageDraw.Draw(tmp)
        tmp_draw.text(text_padding, text, fill=255, font=font, spacing=0)
        self._text_layer = self._transpose(tmp)
        self._pad_layer = self._transpose(Image.new("L", label_size, 255))

    def set_label_position(self, label_size, project: Project):
        first_padding = project.bbox - project.layers[0].bbox
        label_x = self.x1 + (self.size[0] - label_size[0]) // 2
        label_y = self._copy_position[1] + first_padding[1] - label_size[1] + project.calibrate_penetration_px
        if label_y < self.y1:
            label_y = self.y1
        self._label_position = label_x, label_y
        self._logger.debug("label position: %s", str(self._label_position))

    def paste(self, image: Image, source: Image, calibration_type: LayerCalibrationType):
        image.paste(source, box=self._copy_position)
        if calibration_type == LayerCalibrationType.LABEL_TEXT:
            image.paste(self._pad_layer, box=self._label_position, mask=self._text_layer)
        elif calibration_type == LayerCalibrationType.LABEL_PAD:
            image.paste(self._pad_layer, box=self._label_position)

class AreaWithLabelStripe(AreaWithLabel):
    def _transpose(self, image: Image):
        return image.transpose(Image.ROTATE_270).transpose(Image.FLIP_LEFT_RIGHT)

    def set_copy_position(self, bbox: BBox):
        bbox_size = bbox.size
        self_size = self.size
        self._copy_position = 0, self.y1 + (self_size[1] - bbox_size[1]) // 2
        self._logger.debug("copy position: %s", str(self._copy_position))

    def set_label_position(self, label_size, project: Project):
        first_size = project.layers[0].bbox.size
        label_x = first_size[0] - project.calibrate_penetration_px
        label_y = self.y1 + (self.size[1] - label_size[0]) // 2 # text is 90 degree rotated
        if label_y < 0:
            label_y = 0
        self._label_position = label_x, label_y
        self._logger.debug("label position: %s", str(self._label_position))

class Calibration:
    def __init__(self):
        self.areas = []
        self._logger = logging.getLogger(__name__)

    def new_project(self, project: Project):
        if project.calibrate_regions:
            project.analyze()
            if project.error == ProjectErrors.NONE:
                bbox = project.bbox if project.calibrate_compact else None
                if not self.create_areas(project.calibrate_regions, bbox):
                    project.error = ProjectErrors.CALIBRATION_INVALID
                    return
                self.create_overlays(project)

    def create_areas(self, regions, bbox: BBox):
        areaMap = {
                2 : (2, 1),
                4 : (2, 2),
                6 : (3, 2),
                8 : (4, 2),
                9 : (3, 3),
                10 : (10, 1),
                }
        if regions not in areaMap:
            self._logger.error("bad value regions (%d)", regions)
            return False
        divide = areaMap[regions]
        if defines.screenWidth > defines.screenHeight:
            x = 0
            y = 1
        else:
            x = 1
            y = 0
        if bbox:
            size = list(bbox.size)
            if size[0] * divide[x] > defines.screenWidth:
                size[0] = defines.screenWidth // divide[x]
            if size[1] * divide[y] > defines.screenHeight:
                size[1] = defines.screenHeight // divide[y]
            self._areas_loop(
                    ((defines.screenWidth - divide[x] * size[0]) // 2, (defines.screenHeight - divide[y] * size[1]) // 2),
                    (size[0], size[1]),
                    (divide[x], divide[y]),
                    Area)
        else:
            self._areas_loop(
                    (0, 0),
                    (defines.screenWidth // divide[x], defines.screenHeight // divide[y]),
                    (divide[x], divide[y]),
                    AreaWithLabelStripe if regions == 10 else AreaWithLabel)
        return True

    def _areas_loop(self, begin, step, rnge, area_type):
        for i in range(rnge[0]):
            for j in range(rnge[1]):
                x = i * step[0] + begin[0]
                y = j * step[1] + begin[1]
                area = area_type((x, y, x + step[0], y + step[1]))
                self._logger.debug("%d-%d: %s", i, j, area)
                self.areas.append(area)

    def _check_project_size(self, project: Project):
        orig_size = project.bbox.size
        self._logger.debug("project bbox: %s  project size: %dx%d", str(project.bbox), orig_size[0], orig_size[1])
        area_size = self.areas[0].size
        project.bbox.shrink(area_size)
        new_size = project.bbox.size
        if new_size != orig_size:
            self._logger.warning("project size %dx%d was reduced to %dx%d to fit area size %dx%d",
                    orig_size[0], orig_size[1], new_size[0], new_size[1], area_size[0], area_size[1])
            project.warnings.add(ProjectWarnings.CROPPED)
            first_layer_bbox = project.layers[0].bbox
            orig_size = first_layer_bbox.size
            first_layer_bbox.crop(project.bbox)
            new_size = first_layer_bbox.size
            if new_size != orig_size:
                self._logger.warning("project first layer bbox %s was cropped to project bbox %s",
                        str(first_layer_bbox), str(project.bbox))

    def create_overlays(self, project: Project):
        self._check_project_size(project)
        times = project.layers[-1].times_ms
        if len(times) != len(self.areas):
            self._logger.error("times != areas (%d, %d)", len(times), len(self.areas))
            project.error = ProjectErrors.CALIBRATION_INVALID
            return
        font = ImageFont.truetype(defines.fontFile, project.calibrate_text_size_px)
        actual_time_ms = 0
        for area, time_ms in zip(self.areas, times):
            area.set_copy_position(project.bbox)
            actual_time_ms += time_ms
            text = "%.1f" % (actual_time_ms / 1000)
            self._logger.debug("calib. text: '%s'", text)
            text_size = font.getsize(text)
            text_offset = font.getoffset(text)
            self._logger.debug("text_size: %s  text_offset: %s", str(text_size), str(text_offset))
            label_size = (text_size[0] + 2 * project.calibrate_pad_spacing_px - text_offset[0],
                    text_size[1] + 2 * project.calibrate_pad_spacing_px - text_offset[1])
            text_padding = ((label_size[0] - text_size[0] - text_offset[0]) // 2,
                    (label_size[1] - text_size[1] - text_offset[1]) // 2)
            area.set_label_text(font, text, text_padding, label_size)
            area.set_label_position(label_size, project)

class Screen:
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._project: Optional[Project] = None
        self._black_image = Image.new("L", defines.screen_size)
        self._overlays = {}
        self._calibration: Optional[Calibration] = None
        self._screen = None
        self._preloader: Optional[Process] = None
        self._last_preload_index: Optional[int] = None
        self._preloader_lock = Lock()
        self._next_image_1_shm = shared_memory.SharedMemory(create=True, size=defines.screenWidth * defines.screenHeight)
        self._next_image_2_shm = shared_memory.SharedMemory(create=True, size=defines.screenWidth * defines.screenHeight)
        temp_usage = numpy.zeros(defines.display_usage_size, dtype=numpy.float64, order='C')
        self._usage_shm = shared_memory.SharedMemory(create=True, size=temp_usage.nbytes)
        self._white_pixels = Value(c_uint32, 0)
        self._screen = self._black_image.copy()
        if not test_runtime.testing:
            self._logger.debug("event")
            self._video_sync_event = Event()
            self._logger.debug("connect")
            SystemBus().subscribe(
                    iface='cz.prusa3d.framebuffer1.Frame',
                    signal='Ready',
                    object='/cz/prusa3d/framebuffer1',
                    signal_fired=self._dbus_signal_handler)

    def __del__(self):
        self._next_image_1_shm.close()
        self._next_image_1_shm.unlink()
        self._next_image_2_shm.close()
        self._next_image_2_shm.unlink()
        self._usage_shm.close()
        self._usage_shm.unlink()

    def _dbus_signal_handler(self, *args):
        # pylint: disable=unused-argument
        self._video_sync_event.set()

    @staticmethod
    def _check_fb_service():
        name = "weston-framebuffer.service"
        if test_runtime.testing:
            return "Running inside a test environment."
        try:
            unit = SystemBus().get(".systemd1", SystemBus().get(".systemd1").GetUnit(name))
            state = "Unit {0} is {1}/{2}/{3}".format(name, unit.ActiveState, unit.SubState, unit.Result)
            if unit.ActiveState == "active" and unit.SubState == "running":
                running_for = monotonic() - unit.ExecMainStartTimestampMonotonic/1E6
                state += " and has been running for {0} s.".format(running_for)
            return state
        except Exception as e:
            return "Failed to read state of {}. ({})".format(name, e)

    def _writefb(self):
        try:
            # open fbFile for write without truncation (conv=notrunc equivalent in dd)
            with open(defines.fbFile, 'rb+') as fb:
                fb.write(self._screen.convert("RGBX").tobytes())
        except FileNotFoundError as e:
            service_state = self._check_fb_service()
            self._logger.error("framebuffer is not available (yet): %s; %s", e, service_state)
            raise PreloadFailed() from e
        if not test_runtime.testing:
            self._logger.debug("waiting for video sync event")
            start_time = time()
            if not self._video_sync_event.wait(timeout=2):
                self._logger.error("video sync event timeout")
                # TODO this shouldn't happen, need better handling if yes
                raise PreloadFailed()
            self._video_sync_event.clear()
            self._logger.debug("video sync done in %f secs", time() - start_time)

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
        usage = numpy.ndarray(defines.display_usage_size, dtype=numpy.float64, order='C', buffer=self._usage_shm.buf)
        usage.fill(0.0)
        if self._project.per_partes:
            try:
                self._overlays['ppm1'] = self._open_image(defines.perPartesMask)
                self._overlays['ppm2'] = ImageOps.invert(self._overlays['ppm1'])
            except Exception:
                self._logger.exception("per partes masks exception")
                self._project.warnings.add(ProjectWarnings.PER_PARTES_NOAVAIL)
                self._project.per_partes = False
        try:
            img = self._project.read_image(defines.maskFilename)
            self._overlays['mask'] = ImageOps.invert(img)
        except KeyError:
            self._logger.info("No mask picture in the project")
        except Exception:
            self._logger.exception("project mask exception")
            self._project.warnings.add(ProjectWarnings.MASK_NOAVAIL)
        self._calibration = Calibration()
        self._calibration.new_project(self._project)

    def blank_screen(self):
        self._screen = self._black_image.copy()
        self._writefb()

    def fill_area(self, area_index, color=0):
        if self._calibration and area_index < len(self._calibration.areas):
            self._logger.debug("fill area %d", area_index)
            self._screen.paste(color, self._calibration.areas[area_index].coords)
            self._writefb()
            self._logger.debug("fill area end")

    def show_image(self, filename):
        self._logger.debug("show of %s started", filename)
        start_time = time()
        self._screen = self._open_image(filename)
        self._writefb()
        self._logger.debug("show of %s done in %f secs", filename, time() - start_time)

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
            output_image = Image.frombuffer("L", defines.screen_size, self._next_image_1_shm.buf, "raw", "L", 0, 1)
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
            usage = numpy.ndarray(defines.display_usage_size, dtype=numpy.float64, order='C', buffer=self._usage_shm.buf)
            # 1500 layers on 0.1 mm layer height <0:255> -> <0.0:1.0>
            usage += numpy.reshape(pixels, defines.display_usage_shape).mean(axis=3).mean(axis=1) / 382500
            white_pixels = get_white_pixels(output_image)
            self._logger.debug("pixels manipulations done in %f secs, white pixels: %d",
                    time() - start_time, white_pixels)
            if self._project.per_partes and white_pixels > self._project.white_pixels_threshold:
                output_image_second = Image.frombuffer("L", defines.screen_size, self._next_image_2_shm.buf, "raw", "L", 0, 1)
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
            preview = image.resize(defines.livePreviewSize, Image.BICUBIC)
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
            self._logger.error("Preloader exit code: %s", str(self._preloader.exitcode))
            # TODO this shouldn't happen, need better handling if yes
            raise PreloadFailed()

    def blit_image(self, second=False):
        self._sync_preloader()
        start_time = time()
        self._logger.debug("blit started")
        source_shm = self._next_image_2_shm if second else self._next_image_1_shm
        self._screen = Image.frombuffer("L", defines.screen_size, source_shm.buf, "raw", "L", 0, 1).copy()
        self._writefb()
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
        self._screen = ImageOps.invert(self._screen)
        self._writefb()
        self._logger.debug("inverse done in %f secs", time() - start_time)

    def save_display_usage(self):
        self._sync_preloader()
        usage = numpy.ndarray(defines.display_usage_size, dtype=numpy.float64, order='C', buffer=self._usage_shm.buf)
        try:
            with numpy.load(defines.displayUsageData) as npzfile:
                saved_data = npzfile['display_usage']
                if saved_data.shape != defines.display_usage_size:
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
        return get_white_pixels(self._screen) == 0
