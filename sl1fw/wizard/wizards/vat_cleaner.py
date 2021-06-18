# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import weakref

from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.libHardware import Hardware
from sl1fw.image.exposure_image import ExposureImage
from sl1fw.states.wizard import WizardId
from sl1fw.wizard.checks.vat_cleaner import VatCleanerCheck
from sl1fw.wizard.wizard import SingleCheckWizard, WizardDataPackage


class VatCleaner(SingleCheckWizard):
    def __init__(self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig):
        self._package = WizardDataPackage(
            hw=hw, exposure_image=weakref.proxy(exposure_image), runtime_config=runtime_config
        )
        super().__init__(
            WizardId.VAT_CLEANER,
            VatCleanerCheck(self._package.hw, self._package.exposure_image),
            self._package,
            show_results=False,
        )

    @classmethod
    def get_name(cls) -> str:
        return "vat_cleaner"
