# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import pickle
from asyncio import Task
from pathlib import Path
from queue import Queue
from threading import Thread, Lock, Event
from zipfile import ZipFile

from PySignal import Signal

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.configs.project import ProjectConfig
from slafw.libHardware import Hardware
from slafw.image.exposure_image import ExposureImage
from slafw.utils.traceable_collections import TraceableDict, TraceableList


class ExposurePickler(pickle.Pickler):
    IGNORED_CLASSES = (
        Signal,
        Hardware,
        ExposureImage,
        Thread,
        TraceableDict,
        TraceableList,
        Queue,
        ZipFile,
        Event,
        type(Lock()),
        Task,
    )

    def persistent_id(self, obj):
        if isinstance(obj, self.IGNORED_CLASSES):
            return "ignore"
        if isinstance(obj, HwConfig):
            obj.write(Path(defines.lastProjectHwConfig))
            obj.write_factory(Path(defines.lastProjectFactoryFile))
            return "HwConfig"
        if isinstance(obj, ProjectConfig):
            obj.write(Path(defines.lastProjectConfigFile))
            return "ProjectConfig"
        return None


class ExposureUnpickler(pickle.Unpickler):
    def persistent_load(self, pid):
        if pid == "ignore":
            return None
        if pid == "HwConfig":
            hw_config = HwConfig(
                file_path=Path(defines.lastProjectHwConfig),
                factory_file_path=Path(defines.lastProjectFactoryFile),
                is_master=False,
            )
            hw_config.read_file()
            return hw_config
        if pid == "ProjectConfig":
            project_config = ProjectConfig()
            project_config.read_file(file_path=Path(defines.lastProjectConfigFile))
            return project_config
        raise pickle.UnpicklingError(f"unsupported persistent object {str(pid)}")
