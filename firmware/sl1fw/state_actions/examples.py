# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix Pylint warnings
# pylint: disable=too-many-instance-attributes

import logging
import os
import shutil
import tarfile
import tempfile
from threading import Thread

from PySignal import Signal

from sl1fw import defines
from sl1fw.errors.errors import NotConnected, NotEnoughInternalSpace
from sl1fw.libNetwork import Network
from sl1fw.states.examples import ExamplesState
from sl1fw.functions.files import ch_mode_owner


class Examples(Thread):
    def __init__(self, network: Network):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._state = ExamplesState.INITIALIZING
        self._download_progress: float = 0
        self._unpack_progress: float = 0
        self._copy_progress: float = 0
        self._exception = None
        self._network = network
        self.change = Signal()

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value: ExamplesState) -> None:
        self._state = value
        self.change.emit("state", value)

    @property
    def exception(self) -> Exception:
        return self._exception

    @exception.setter
    def exception(self, value: Exception) -> None:
        self._exception = value
        self.change.emit("exception", value)

    @property
    def download_progress(self) -> float:
        return self._download_progress

    @download_progress.setter
    def download_progress(self, value: float) -> None:
        self._download_progress = value
        self.change.emit("download_progress", value)

    @property
    def unpack_progress(self) -> float:
        return self._unpack_progress

    @unpack_progress.setter
    def unpack_progress(self, value: float) -> None:
        self._unpack_progress = value
        self.change.emit("unpack_progress", value)

    @property
    def copy_progress(self) -> float:
        return self._copy_progress

    @copy_progress.setter
    def copy_progress(self, value: float):
        self._copy_progress = value
        self.change.emit("copy_progress", value)

    def run(self) -> None:
        try:
            self._examples()
        except Exception as exception:
            self.state = ExamplesState.FAILURE
            self._exception = exception
            raise exception

    def _examples(self):
        if not self._network.ip:
            raise NotConnected()

        statvfs = os.statvfs(defines.internalProjectPath)
        internal_available = statvfs.f_frsize * statvfs.f_bavail - defines.internalReservedSpace
        self._logger.info("Internal storage available space: %d bytes", internal_available)

        # if internal storage is full, quit immediately
        if internal_available < 0:
            raise NotEnoughInternalSpace()

        if not os.path.isdir(defines.internalProjectPath):
            os.makedirs(defines.internalProjectPath)

        with tempfile.NamedTemporaryFile() as archive:
            self.state = ExamplesState.DOWNLOADING
            self._logger.info("Downloading examples archive")
            self._network.download_url(defines.examplesURL, archive.name, progress_callback=self._download_callback)

            self.state = ExamplesState.UNPACKING
            self._logger.info("Extracting examples archive")
            with tempfile.TemporaryDirectory() as temp:
                extracted_size = 0
                with tarfile.open(fileobj=archive) as tar:
                    members = tar.getmembers()
                    for i, member in enumerate(members):
                        self._logger.debug("Found '%s' (%d bytes)", member.name, member.size)
                        self.unpack_progress = (i + 1) / len(members)
                        extracted_size += member.size
                        tar.extract(member, temp)

                if extracted_size > internal_available:
                    raise Exception("Not enough free space in the internal storage")

                self.state = ExamplesState.COPYING
                self._logger.info("Copying examples")
                items = os.listdir(temp)
                for i, item in enumerate(items):
                    destination = os.path.join(defines.internalProjectPath, item)
                    if os.path.exists(destination):
                        shutil.rmtree(destination)
                    shutil.copytree(os.path.join(temp, item), destination)
                    ch_mode_owner(destination)
                    self.copy_progress = (i + 1) / len(items)

                self.state = ExamplesState.CLEANUP
        self.state = ExamplesState.COMPLETED
        self._logger.info("Examples download finished")

    def _download_callback(self, progress):
        self.download_progress = progress
