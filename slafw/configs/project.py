# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-instance-attributes

from slafw.configs.ini import Config
from slafw.configs.value import FloatValue, IntValue, TextValue, BoolValue, FloatListValue
from slafw import defines


class ProjectConfig(Config):
    """
    Project configuration is read from config.ini located in the project zip file. Currently the content is parsed using
    a Toml parser with preprocessor that adjusts older custom configuration format if necessary. Members describe
    possible configuration options. These can be set using the

    key = value

    notation. For details see Toml format specification: https://en.wikipedia.org/wiki/TOML
    """

    def __init__(self):
        super().__init__(is_master=True)

    job_dir = TextValue("no project", key="jobDir", doc="Name of the directory containing layer images.")

    expTime = FloatValue(8.0, doc="Exposure time. [s]")
    expTimeFirst = FloatValue(35.0, doc="First layer exposure time. [s]")
    expUserProfile = IntValue(
        0,
        minimum=0,
        maximum=2,
        doc="Identifies set of exposure settings. 0 - DEFAULT, 1 - SAFE (slow tilt, delay before exposure), "
            "2 - HIGH_VISCOSITY (very slow, longer delay before exposure) [-]"
    )
    layerHeight = FloatValue(-1, doc="Layer height, if not equal to -1 supersedes stepNum. [mm]")
    stepnum = IntValue(40, doc="Layer height [microsteps]")
    layerHeightFirst = FloatValue(0.05)
    fadeLayers = IntValue(
        10,
        minimum=0,
        maximum=200,
        key="numFade",
        doc="Number of layers used for transition from first layer exposure time to standard exposure time.",
    )

    calibrateRegions = IntValue(0, doc="Number of calibration regions (2, 4, 6, 8, 9, 10), 0 = off")
    calibrateTime = FloatValue(
        1.0, doc="Time added to exposure per calibration region. [seconds]"
    )
    calibrateTimeExact = FloatListValue(
        [], doc="Force calibration times with these values, for all layers!"
    )
    calibrateCompact = BoolValue(
        False, doc="Do not generate labels and group regions in the center of the display if set to True."
    )
    calibrateTextSize = FloatValue(
        5.0, doc="Size of the text on calibration label. [millimeters]"
    )
    calibrateTextThickness = FloatValue(
        0.5, doc="Thickness of the text on calibration label. [millimeters]"
    )
    calibratePadSpacing = FloatValue(
        1.0, doc="Spacing of the pad around the text. [millimeters]"
    )
    calibratePadThickness = FloatValue(
        0.5, doc="Thickness of the pad of the calibration label. [millimeters]"
    )
    calibratePenetration = FloatValue(
        0.5, doc="How much to sink the calibration label into the object. [millimeters]"
    )

    usedMaterial = FloatValue(
        defines.resinMaxVolume - defines.resinMinVolume,
        doc="Resin necessary to print the object. Default is full tank. [milliliters]",
    )
    layersSlow = IntValue(0, key="numSlow", doc="Number of layers that require slow tear off.")
    layersFast = IntValue(0, key="numFast", doc="Number of layers that do not require slow tear off.")

    action = TextValue(doc="What to do with the project. Legacy value, currently discarded.")
    raw_modification_time = TextValue(
            None, key="fileCreationTimestamp", doc="Date and time of project creation [YYYY-MM-DD at HH:MM:SS TZ]")

    printProfile = TextValue(doc="Print settings used for slicing, currently discarded.")
    materialName = TextValue(doc="Material used for slicing, currently discarded.")
    printerProfile = TextValue(doc="Printer settings used for slicing, currently discarded.")
    printerModel = TextValue("SL1", doc="Printer model project is sliced for.")
    printerVariant = TextValue("default", doc="Printer variant project is sliced for.")
    printTime = FloatValue(0.0, doc="Project print time, currently discarded (calculated by fw) [seconds]")
    prusaSlicerVersion = TextValue(doc="Slicer used for slicing, currently discarded.")
