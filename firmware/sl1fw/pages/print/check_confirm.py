# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from sl1fw.errors.warnings import (
    AmbientTooHot,
    AmbientTooCold,
    PrintingDirectlyFromMedia,
    ModelMismatch,
    ResinNotEnough,
    ProjectSettingsModified,
)
from sl1fw.pages import page
from sl1fw.pages.print.base import PagePrintBase


@page
class PageCheckConfirm(PagePrintBase):
    Name = "checkconfirm"

    def prepare(self):
        # pylint: disable = too-many-return-statements
        warning = self.display.expo.warning
        self.logger.info("Displaying pre-print warning: %s", warning)

        if isinstance(warning, PrintingDirectlyFromMedia):
            self.display.pages["confirm"].setParams(
                continueFce=self.confirm_print,
                backFce=self.cancel_print,
                text=_(
                    "Loading the file into the printer's memory failed.\n\n"
                    "The project will be printed from USB drive.\n\n"
                    "DO NOT remove the USB drive!"
                ),
            )
            return "confirm"
        if isinstance(warning, AmbientTooCold):
            self.display.pages["yesno"].setParams(
                pageTitle=N_("Continue?"),
                yesFce=self.confirm_print,
                noFce=self.cancel_print,
                text=_(
                    "Ambient temperature is under recommended value.\n\n"
                    "You should heat up the resin and/or increase the exposure times.\n\n"
                    "Do you want to continue?"
                ),
            )
            return "yesno"
        if isinstance(warning, AmbientTooHot):
            self.display.pages["yesno"].setParams(
                pageTitle=N_("Continue?"),
                yesFce=self.confirm_print,
                noFce=self.cancel_print,
                text=_(
                    "Ambient temperature is over recommended value.\n\n"
                    "You should move the printer to a cooler place.\n\n"
                    "Do you want to continue?"
                ),
            )
            return "yesno"
        if isinstance(warning, ModelMismatch):
            self.display.pages["yesno"].setParams(
                pageTitle=N_("Wrong project printer"),
                yesFce=self.confirm_print,
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
        if isinstance(warning, ResinNotEnough):
            self.display.pages["confirm"].setParams(
                continueFce=self.confirm_print,
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
        if isinstance(warning, ProjectSettingsModified):
            self.display.pages["confirm"].setParams(
                continueFce=self.confirm_print,
                backFce=self.cancel_print,
                text=_("Project settings has been modified by printer constraints:\n %(changes)s")
                % {"changes": "\n".join([f"{key}: {val[1]} -> {val[0]}" for key, val in warning.changes.items()])},
            )
            return "confirm"

        self.logger.error("Unknown exposure warning: %s", warning)
        return "checks"

    def confirm_print(self):
        self.display.expo.confirm_print_warning()
        return "checks"

    def cancel_print(self):
        self.display.expo.reject_print_warning()
        return "checks"
