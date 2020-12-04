# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from sl1fw import defines
from sl1fw.project.project import Project, LayerCalibrationType
from sl1fw.errors.errors import ProjectErrorCalibrationInvalid
from sl1fw.utils.bounding_box import BBox
from sl1fw.screen.printer_model import PrinterModel
from sl1fw.errors.warnings import PrintedObjectWasCropped


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
    def __init__(self, printer_model: PrinterModel):
        self.areas = []
        self._logger = logging.getLogger(__name__)
        self._printer_model = printer_model

    def new_project(self, project: Project):
        if project.calibrate_regions:
            project.analyze()
            bbox = project.bbox if project.calibrate_compact else None
            self.create_areas(project.calibrate_regions, bbox)
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
            raise ProjectErrorCalibrationInvalid
        divide = areaMap[regions]
        if self._printer_model.screen_width_px > self._printer_model.screen_height_px:
            x = 0
            y = 1
        else:
            x = 1
            y = 0
        if bbox:
            size = list(bbox.size)
            if size[0] * divide[x] > self._printer_model.screen_width_px:
                size[0] = self._printer_model.screen_width_px // divide[x]
            if size[1] * divide[y] > self._printer_model.screen_height_px:
                size[1] = self._printer_model.screen_height_px // divide[y]
            self._areas_loop(
                    ((self._printer_model.screen_width_px - divide[x] * size[0]) // 2, (self._printer_model.screen_height_px - divide[y] * size[1]) // 2),
                    (size[0], size[1]),
                    (divide[x], divide[y]),
                    Area)
        else:
            self._areas_loop(
                    (0, 0),
                    (self._printer_model.screen_width_px // divide[x], self._printer_model.screen_height_px // divide[y]),
                    (divide[x], divide[y]),
                    AreaWithLabelStripe if regions == 10 else AreaWithLabel)

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
            project.warnings.add(PrintedObjectWasCropped())
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
            raise ProjectErrorCalibrationInvalid
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
