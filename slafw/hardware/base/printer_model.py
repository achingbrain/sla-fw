# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from abc import ABC, abstractmethod

from slafw.hardware.printer_options import PrinterOptions


class PrinterModelBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def extensions(self) -> set[str]:
        # TODO: remove code related to handling projects.
        # Filemanager should be the only one who takes care about files
        return {self.extension}

    @property
    def extension(self) -> str:
        # TODO: remove code related to handling projects.
        # Filemanager should be the only one who takes care about files
        return "." + str(self.name).lower()

    @property
    @abstractmethod
    def options(self) -> PrinterOptions:
        ...

    @property
    @abstractmethod
    def value(self) -> int:
        ...
