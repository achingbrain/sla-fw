# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import numpy
from PIL import Image

from sl1fw.errors.errors import DisplayUsageError
from sl1fw.image.exposure_image import ExposureImage

def display_usage_heatmap(
        exposure_image: ExposureImage,
        data_filename: str,
        palette_filename: str,
        output_filename: str) -> None:
    dus = exposure_image.display_usage_size

    try:
        palette_bytes = bytes()
        with open(palette_filename, "r") as f:
            for line in f:
                palette_bytes += bytes.fromhex(line.strip()[1:])
        palette = list(palette_bytes)
    except Exception as e:
        raise DisplayUsageError("Load palette failed.") from e

    try:
        with numpy.load(data_filename) as npzfile:
            saved_data = npzfile["display_usage"]
    except Exception as e:
        raise DisplayUsageError("No display usage data to show.") from e

    if saved_data.shape != dus:
        raise DisplayUsageError("Wrong saved data shape: %s" % saved_data.shape)

    max_value = saved_data.max()
    saved_data = saved_data * 255 / max_value # 0-255 range
    image = Image.fromarray(saved_data.astype("int8"), "P").transpose(Image.ROTATE_270)
    # two pixels outline
    output = Image.new("P", (dus[0] + 4, dus[1] + 4), 255)
    output.putpalette(palette)
    output.paste(image, (2, 2))
    output.save(output_filename)
