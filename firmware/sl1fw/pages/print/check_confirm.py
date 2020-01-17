# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from queue import Queue
from typing import TYPE_CHECKING

from sl1fw.exposure_state import (
    PrintingDirectlyWarning,
    AmbientTooCold,
    AmbientTooHot,
    ModelMismatchWarning,
    ResinNotEnoughWarning,
)
from sl1fw.pages import page
from sl1fw.pages.print.base import PagePrintBase

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PageCheckConfirm(PagePrintBase):
    Name = "checkconfirm"

    def __init__(self, display: Display):
        super().__init__(display)
        self.warnings_to_show = Queue()

    def prepare(self):
        for warning in self.display.expo.warnings:
            self.warnings_to_show.put(warning)
        return self.warn()

    def warn(self):
        if self.warnings_to_show.empty():
            self.display.expo.confirm_print_warnings()
        else:
            warning = self.warnings_to_show.get()

            if isinstance(warning, PrintingDirectlyWarning):
                self.display.pages["confirm"].setParams(
                    continueFce=self.warn,
                    backFce=self.cancel_print,
                    text=_(
                        "Loading the file into the printer's memory failed.\n\n"
                        "The project will be printed from USB drive.\n\n"
                        "DO NOT remove the USB drive!"
                    ),
                )
                return "confirm"
            elif isinstance(warning, AmbientTooCold):
                self.display.pages["yesno"].setParams(
                    pageTitle=N_("Continue?"),
                    yesFce=self.warn,
                    noFce=self.cancel_print,
                    text=_(
                        "Ambient temperature is under recommended value.\n\n"
                        "You should heat up the resin and/or increase the exposure times.\n\n"
                        "Do you want to continue?"
                    ),
                )
                return "yesno"
            elif isinstance(warning, AmbientTooHot):
                self.display.pages["yesno"].setParams(
                    pageTitle=N_("Continue?"),
                    yesFce=self.warn,
                    noFce=self.cancel_print,
                    text=_(
                        "Ambient temperature is over recommended value.\n\n"
                        "You should move the printer to a cooler place.\n\n"
                        "Do you want to continue?"
                    ),
                )
                return "yesno"
            elif isinstance(warning, ModelMismatchWarning):
                self.display.pages["yesno"].setParams(
                    pageTitle=N_("Wrong project printer"),
                    yesFce=self.warn,
                    noFce=self.cancel_print,
                    text=_(
                        "Project is for different printer model.\n\n"
                        "Actual printer: %(amodel)s/%(avariant)s\n"
                        "Project printer: %(pmodel)s/%(pvariant)s\n\n"
                        "Do you want to continue?"
                        % {
                            "amodel": warning.actual_model,
                            "avariant": warning.actual_variant,
                            "pmodel": warning.project_model,
                            "pvariant": warning.project_variant,
                        }
                    ),
                )
                return "yesno"
            elif isinstance(warning, ResinNotEnoughWarning):
                self.display.pages["confirm"].setParams(
                    continueFce=self.warn,
                    backFce=self.cancel_print,
                    text=_(
                        "Your resin volume is approx %(measured)d %%\n\n"
                        "For your project, %(requested)d %% is needed. A refill may be required during printing."
                    )
                    % {
                        "measured": self.display.hw.calcPercVolume(warning.measured_resin_ml),
                        "requested": self.display.hw.calcPercVolume(warning.required_resin_ml),
                    },
                )
                return "confirm"
            else:
                self.logger.error("Unknown exposure warning: %s", warning)

        return "checks"

    def cancel_print(self):
        self.display.expo.reject_print_warnings()
        return "checks"
