# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from sl1fw import defines
from sl1fw.exposure_state import ProjectFailure, ExposureState, ExposureException, TiltFailure, TowerMoveFailure, \
    TowerFailure, FanFailure, TempSensorFailure, ResinTooLow, ResinTooHigh, ResinFailure, WarningEscalation
from sl1fw.pages.base import Page
from sl1fw.project.project import ProjectState

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


class PagePrintBase(Page):
    def __init__(self, display: Display):
        super().__init__(display)
        self.callbackSkip = 5
        self.callbackPeriod = 0.1

    def callback(self):
        self._exposure_state_switch()

        self.callbackSkip += 1
        if self.callbackSkip >= 5:
            self.callbackSkip = 0
            return super().callback()

    def _exposure_state_switch(self):
        mapping = {
            ExposureState.READING_DATA: "reading",
            ExposureState.CONFIRM: "printpreviewswipe",
            ExposureState.CHECKS: "checks",
            ExposureState.PRINTING: "print",
            ExposureState.GOING_UP: "goingup",
            ExposureState.GOING_DOWN: "goingdown",
            ExposureState.WAITING: "waiting",
            ExposureState.STIRRING: "stirring",
            ExposureState.PENDING_ACTION: "printactionpending",
            ExposureState.COVER_OPEN: "printcoveropen",
            ExposureState.FINISHED: "finished",
            ExposureState.CANCELED: "finished",
            ExposureState.FEED_ME: "feedme",
            ExposureState.STUCK: "printstuck",
            ExposureState.STUCK_RECOVERY: "printstuckrecovery",
            ExposureState.TILTING_DOWN: "tiltingdown",
            ExposureState.RESIN_WARNING: "resinconfirm",
            ExposureState.CHECK_WARNING: "checkconfirm",
        }

        if self.display.expo.state in mapping and self.display.actualPage.Name != mapping[self.display.expo.state]:
            self.logger.debug(
                "Print state: %s, current page: %s, switching to: %s",
                self.display.expo.state,
                self.display.actualPage.Name,
                mapping[self.display.expo.state],
            )
            self.display.forcePage(mapping[self.display.expo.state])

        if self.display.expo.state == ExposureState.FAILURE:
            self._handle_exposure_failure(self.display.expo.exception)

    def _handle_exposure_failure(self, exception: ExposureException):
        if isinstance(exception, WarningEscalation):
            self.display.forcePage("home")
            return

        if isinstance(exception, TiltFailure):
            self.display.pages["error"].setParams(
                backFce=lambda: "home",
                text=_("Tilt homing failed!\n\n" "Check the printer's hardware.\n\n" "The print job was canceled."),
            )
        elif isinstance(exception, ProjectFailure):
            message = defaultdict(
                lambda: _("Unknown project error.\n\nCheck the project and try again."),
                {
                    ProjectState.NOT_FOUND: _("Project file not found.\n\nCheck it and try again."),
                    ProjectState.CANT_READ: _("Can't read project data.\n\nRe-export the project and try again."),
                    ProjectState.CORRUPTED: _("Project data is corrupted.\n\nRe-export the project and try again."),
                    ProjectState.NOT_ENOUGH_LAYERS: _("Not enough layers.\n\nRe-export the project and try again."),
                },
            )[self.display.expo.project.state]
            self.display.pages["error"].setParams(backFce=lambda: "home", text=message)
        elif isinstance(exception, TowerFailure):
            self.display.pages["error"].setParams(
                backFce=lambda: "home", text=_("Tower homing failed!\n\n" "Check the printer's hardware.")
            )
        elif isinstance(exception, TowerMoveFailure):
            self.display.pages["error"].setParams(
                text=_(
                    "The platform has failed to move to the correct position!\n\n"
                    "Clean any cured resin remains or other debris blocking the movement.\n\n"
                    "If everything is clean, the printer needs service. Please contact tech support."
                )
            )
        elif isinstance(exception, TempSensorFailure):
            self.display.pages["error"].setParams(
                backFce=lambda: "home",
                text=_("Can't read %s\n\n" "Please check if temperature sensors are connected correctly.")
                % str([self.display.hw.getSensorName(i) for i in exception.failed_sensors]),
            )
        elif isinstance(exception, ResinFailure):
            self.display.pages["error"].setParams(
                backFce=lambda: "home",
                text=_(
                    "Resin measuring failed!\n\n"
                    "Is there the correct amount of resin in the tank?\n\n"
                    "Is the tank secured with both screws?"
                ),
            )
        elif isinstance(exception, FanFailure):
            self.display.pages["error"].setParams(
                backFce=lambda: "home",
                text=_(
                    "Failed: %s\n\n"
                    "Check if fans are connected properly and can rotate without resistance."
                    % ", ".join([self.display.hw.fans[i].name for i in exception.failed_fans])
                ),
            )
        elif isinstance(exception, ResinTooLow):
            self.display.pages["error"].setParams(
                backFce=lambda: "home",
                text=_(
                    "Resin volume is too low!\n\n"
                    "Add enough resin so it reaches at least the %d %% mark and try again."
                )
                % self.display.hw.calcPercVolume(defines.resinMinVolume),
            )
        elif isinstance(exception, ResinTooHigh):
            self.display.pages["error"].setParams(
                backFce=lambda: "home",
                text=_("Resin volume is too high!\n\n" "Remove some resin from the tank and try again."),
            )
        else:
            self.display.pages["error"].setParams(
                backFce=lambda: "home",
                text=_(
                    "Print failed due to an unexpected error\n"
                    "\n"
                    "Please follow the instructions in Chapter 3.1 in the handbook to learn how "
                    "to save a log file. Please send the log to us and help us improve the  printer.\n"
                    "\n"
                    "Thank you!"
                ),
            )

        self.display.forcePage("error")
