# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2020 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.states.unboxing import UnboxingState

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


class PageUnboxingBase(Page):
    def __init__(self, display: Display):
        super().__init__(display)
        self.callbackPeriod = 0.1

    def callback(self):
        self._unboxing_state_switch()

    def _unboxing_state_switch(self):
        mapping = {
            UnboxingState.STICKER: "unboxing-sticker",
            UnboxingState.COVER_CLOSED: "unboxing-cover-closed",
            UnboxingState.MOVING_TO_FOAM: "unboxing-moving",
            UnboxingState.SIDE_FOAM: "unboxing-side-foam",
            UnboxingState.MOVING_TO_TANK: "unboxing-moving",
            UnboxingState.TANK_FOAM: "unboxing-tank-foam",
            UnboxingState.DISPLAY_FOIL: "unboxing-display-foil",
            UnboxingState.FINISHED: "unboxing-finished",
        }
        state = self.display.action_manager.unboxing.state
        page_name = self.display.actualPage.Name
        if state in mapping and page_name != mapping[state] and page_name != "unboxing-confirm":
            self.logger.debug(
                "Unboxing state: %s, current page: %s, switching to: %s",
                state,
                self.display.actualPage.Name,
                mapping[state],
            )
            self.display.forcePage(mapping[state])
        if state == UnboxingState.CANCELED:
            self.display.leave_menu()

    def backButtonRelease(self):
        return "unboxing-confirm"

    @staticmethod
    def _EXIT_():
        return "_EXIT_"


@page
class PageUnboxing(PageUnboxingBase):
    Name = "unboxing"


@page
class PageUnboxingSticker(PageUnboxingBase):
    Name = "unboxing-sticker"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing step 1/4")

    def show(self):
        self.items.update(
            {
                "imageName": "unboxing-sticker_open_cover.jpg",
                "text": _("Please remove the safety sticker on the right and open the orange cover."),
            }
        )
        super().show()

    def contButtonRelease(self):
        self.display.action_manager.unboxing.sticker_removed_cover_open()


@page
class PageUnboxingCoverClosed(PageUnboxingBase):
    Name = "unboxing-cover-closed"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"

    def show(self):
        self.setItems(
            line1=_("The cover is closed!"), line2=_("Please remove the safety sticker and open the orange cover.")
        )
        super().show()


@page
class PageUnboxingMoving(PageUnboxingBase):
    Name = "unboxing-moving"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "wait"

    def show(self):
        self.setItems(text=_("The printer is moving to allow for easier manipulation"))
        super().show()


@page
class PageUnboxingSideFoam(PageUnboxingBase):
    Name = "unboxing-side-foam"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing step 2/4")

    def show(self):
        self.items.update(
            {
                "imageName": "unboxing-remove_foam.jpg",
                "text": _("Remove the black foam from both sides of the platform."),
            }
        )
        super().show()

    def contButtonRelease(self):
        self.display.action_manager.unboxing.side_foam_removed()


@page
class PageUnboxingTankFoam(PageUnboxingBase):
    Name = "unboxing-tank-foam"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing step 3/4")

    def show(self):
        self.items.update(
            {
                "imageName": "unboxing-remove_bottom_foam.jpg",
                "text": _("Unscrew and remove the resin tank and remove the black foam underneath it."),
            }
        )
        super().show()

    def contButtonRelease(self):
        self.display.action_manager.unboxing.tank_foam_removed()


@page
class PageUnboxingDisplayFoil(PageUnboxingBase):
    Name = "unboxing-display-foil"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing step 4/4")

    def show(self):
        self.items.update(
            {
                "imageName": "unboxing-remove_sticker_screen.jpg",
                "text": _("Carefully peel off the orange protective sticker from the exposition display."),
            }
        )
        super().show()

    def contButtonRelease(self):
        self.display.action_manager.unboxing.display_foil_removed()


@page
class PageUnboxingFinished(PageUnboxingBase):
    Name = "unboxing-finished"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Unboxing done")

    def show(self):
        self.items.update({
            "text": _("The printer is fully unboxed and ready for the selftest."),
            "no_back" : True })
        super().show()

    @staticmethod
    def contButtonRelease():
        return "_EXIT_"


@page
class PageUnboxingCancel(PageUnboxingBase):
    Name = "unboxing-confirm"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Skip unboxing?")
        self.checkPowerbutton = False

    def show(self):
        self.items.update(
            {
                "text": _(
                    "Do you really want to skip the unboxing wizard?\n\n"
                    "Press 'Yes' only in case you went through this wizard "
                    "previously and the printer is unpacked."
                )
            }
        )
        super().show()

    def yesButtonRelease(self):
        self.display.action_manager.unboxing.cancel()
        return "_EXIT_"

    @staticmethod
    def noButtonRelease():
        return "_NOK_"
