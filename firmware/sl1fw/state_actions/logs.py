# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import json
import logging
import subprocess
import tempfile
from abc import ABC, abstractmethod
from asyncio import CancelledError
from io import BufferedReader
from pathlib import Path
from threading import Thread
from typing import Optional, Callable

import aiohttp
from PySignal import Signal

from sl1fw import defines
from sl1fw.functions.files import get_save_path, get_log_file_name, create_summary, usb_remount
from sl1fw.libHardware import Hardware
from sl1fw.states.logs import LogsState, StoreType


class LogsExport(ABC, Thread):
    # pylint: disable=too-many-instance-attributes
    def __init__(self, hw: Hardware):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._state = LogsState.IDLE
        self.state_changed = Signal()
        self._export_progress = 0
        self.export_progress_changed = Signal()
        self._store_progress = 0
        self.store_progress_changed = Signal()
        self._task: Optional[asyncio.Task] = None
        self._exception: Optional[Exception] = None
        self.exception_changed = Signal()
        self._hw = hw
        self._log_upload_identifier = None
        self.log_upload_identifier_changed = Signal()

    @property
    def state(self) -> LogsState:
        return self._state

    @state.setter
    def state(self, value: LogsState):
        if self._state != value:
            self._state = value
            self.state_changed.emit(value)

    @property
    @abstractmethod
    def type(self) -> StoreType:
        ...

    @property
    def export_progress(self) -> float:
        return self._export_progress

    @export_progress.setter
    def export_progress(self, value: float) -> None:
        if self._export_progress != value:
            self._export_progress = value
            self.export_progress_changed.emit(value)

    @property
    def store_progress(self) -> float:
        return self._store_progress

    @store_progress.setter
    def store_progress(self, value: float) -> None:
        if self._store_progress != value:
            self._store_progress = value
            self.store_progress_changed.emit(value)

    @property
    def log_upload_identifier(self) -> str:
        return self._log_upload_identifier

    @log_upload_identifier.setter
    def log_upload_identifier(self, value: str) -> None:
        if self._log_upload_identifier != value:
            self._log_upload_identifier = value
            self.log_upload_identifier_changed.emit(value)

    @property
    def exception(self) -> Optional[Exception]:
        return self._exception

    @exception.setter
    def exception(self, value: Exception):
        if self.exception != value:
            self._exception = value
            self.exception_changed.emit(value)

    def cancel(self) -> None:
        if not self._task:
            self._logger.warning("Attempt to cancel log export, but no export in progress")
            return

        self._task.cancel()

    def run(self):
        self._logger.info("Running log export of type %s", self.type)
        asyncio.run(self.async_run())

    async def async_run(self):
        try:
            self._task = asyncio.create_task(self.run_export())
            await self._task
            self.state = LogsState.FINISHED
        except CancelledError:
            self.state = LogsState.CANCELED
        except Exception as exception:
            self.exception = exception
            self.state = LogsState.FAILED
            raise

    async def run_export(self):
        self.state = LogsState.EXPORTING
        with tempfile.NamedTemporaryFile() as temp:
            temp_path = Path(temp.name)
            self._logger.debug("Exporting log data to a temporary file")
            self.export_progress = 0
            await self._do_export(temp_path)
            self.export_progress = 1

            self._logger.debug("Running store log method")
            self.state = LogsState.SAVING
            self.store_progress = 0
            await self.store_log(temp_path)
            self.store_progress = 1

    async def _do_export(self, log_file: Path):
        self._logger.info("Creating log export summary")
        summary = create_summary(self._hw, self._logger)

        bash_call = ["export_logs.bash", log_file]
        if summary:
            self._logger.debug("Log export summary created")
            bash_call.append(summary)
        else:
            self._logger.error("Log export summary failed to create")

        self._logger.debug("Running log export script")
        process = subprocess.Popen(bash_call)

        self._logger.debug("Waiting for log export to finish")
        # TODO: This is not nice, lets hope Python 3.8 will include working asyncio.process implementation
        # TODO: In python 3.8 asyncio.subprocess_shell workd, but is not cancelable.
        while process.returncode is None:
            try:
                await asyncio.sleep(0.1)
                process.wait(0.1)
            except subprocess.TimeoutExpired:
                pass
            except CancelledError:
                self._logger.debug("Killing log export due to being canceled")
                process.kill()
                raise

    @abstractmethod
    async def store_log(self, src: Path):
        ...


class UsbExport(LogsExport):
    async def store_log(self, src: Path):
        self.state = LogsState.SAVING
        save_path = get_save_path()
        if save_path is None or not save_path.parent.exists():
            raise FileNotFoundError(save_path)

        self._logger.debug("Copying temporary log file to usb")
        log_file_name = get_log_file_name(self._hw)
        await self._copy_with_progress(src, save_path / log_file_name)

    async def _copy_with_progress(self, src: Path, dst: Path):
        usb_remount(str(dst))

        with src.open("rb") as src_file, dst.open("wb") as dst_file:
            block_size = 4096
            total_size = src.stat().st_size
            while True:
                data = src_file.read(block_size)
                if not data:
                    break
                dst_file.write(data)
                self.store_progress = dst_file.tell() / total_size
                await asyncio.sleep(0)

    @property
    def type(self) -> StoreType:
        return StoreType.USB


class FileReader(BufferedReader):
    """
    This mimics file object and wraps read access while providing callback for current file position

    CHUNK_SIZE constant is used for file upload granularity control
    """

    CHUNK_SIZE = 8192

    def __init__(self, file, callback: Callable[[int, int], None] = None):
        self._total_size = Path(file.name).stat().st_size
        super().__init__(file, self._total_size)
        self._file = file
        self._callback = callback

    def read(self, size=-1):
        data = self._file.read(min(self.CHUNK_SIZE, size))
        if self._callback:
            self._callback(self._file.tell(), self._total_size)
        return data


class ServerUpload(LogsExport):
    async def store_log(self, src: Path):

        log_file_name = get_log_file_name(self._hw)
        self._logger.info("Uploading temporary log file to the server")

        async with aiohttp.ClientSession(headers={"user-agent": "OriginalPrusa3DPrinter"}) as session:
            self._logger.debug("Opening aiohttp client session")

            with src.open("rb") as file:
                data = aiohttp.FormData()
                data.add_field(
                    "logfile",
                    FileReader(file, callback=self._callback),
                    filename=log_file_name,
                    content_type="application/x-xz",
                )
                data.add_field("token", "12345")
                data.add_field("serial", "CZPX1419X009XC00271")

                async with session.post(url=defines.log_url, data=data) as response:
                    self._logger.debug("aiohttp post done")
                    response = await response.text()
                    self._logger.debug("Log upload response: %s", response)
                    response_data = json.loads(response)
                    self.log_upload_identifier = response_data["id"] if "id" in response_data else response_data["url"]

    @property
    def type(self) -> StoreType:
        return StoreType.UPLOAD

    def _callback(self, position: int, total_size: int):
        self._logger.debug("Current upload position: %s / %s bytes", position, total_size)
        self.store_progress = position / total_size
