# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import errno
import json
import logging
import re
import shutil
import tempfile
from abc import ABC, abstractmethod
from asyncio import CancelledError
from asyncio.subprocess import Process
from datetime import datetime
from io import BufferedReader
from pathlib import Path
from threading import Thread
from typing import Optional, Callable

import aiohttp
from PySignal import Signal
from aiohttp.client_exceptions import ClientConnectorError

from slafw import defines
from slafw.errors.errors import NotConnected, ConnectionFailed, NotEnoughInternalSpace, DisplayUsageError, NoExternalStorage
from slafw.functions.files import get_save_path, usb_remount
from slafw.functions.generate import display_usage_heatmap
from slafw.hardware.base.hardware import BaseHardware
from slafw.state_actions.logs.summary import create_summary
from slafw.states.logs import LogsState, StoreType


def get_logs_file_name(hw: BaseHardware) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    serial = re.sub("[^a-zA-Z0-9]", "_", hw.cpuSerialNo)
    return f"logs.{serial}.{timestamp}.tar.xz"


def export_configs(temp_dir: Path):
    if defines.wizardHistoryPath.is_dir():
        shutil.copytree(defines.wizardHistoryPath, temp_dir / defines.wizardHistoryPath.name)
    if defines.wizardHistoryPathFactory.is_dir():
        shutil.copytree(defines.wizardHistoryPathFactory, temp_dir / defines.wizardHistoryPathFactory.name)
    if defines.configDir.exists():
        shutil.copytree(defines.configDir, temp_dir / defines.configDir.name)
    if defines.factoryMountPoint.exists():
        shutil.copytree(defines.factoryMountPoint, temp_dir / defines.factoryMountPoint.name)
        shutil.copyfile(defines.expoPanelLogPath, temp_dir / defines.expoPanelLogFileName)


class LogsExport(ABC, Thread):
    # pylint: disable=too-many-instance-attributes
    def __init__(self, hw: BaseHardware):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self._state = LogsState.IDLE
        self.state_changed = Signal()
        self._export_progress: float = 0
        self.export_progress_changed = Signal()
        self._store_progress: float = 0
        self.store_progress_changed = Signal()
        self._task: Optional[asyncio.Task] = None
        self._exception: Optional[Exception] = None
        self.exception_changed = Signal()
        self._hw = hw
        self._uploaded_log_identifier: Optional[str] = None
        self.uploaded_log_identifier_changed = Signal()
        self._uploaded_log_url: Optional[str] = None
        self.uploaded_log_url_changed = Signal()
        self.proc: Optional[Process] = None

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
        return self._uploaded_log_identifier

    @log_upload_identifier.setter
    def log_upload_identifier(self, value: str) -> None:
        if self._uploaded_log_identifier != value:
            self._uploaded_log_identifier = value
            self.uploaded_log_identifier_changed.emit(value)
            with defines.last_log_token.open("w") as f:
                f.write(str(value))

    @staticmethod
    def last_log_upload_identifier() -> str:
        try:
            with defines.last_log_token.open("r") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    @property
    def log_upload_url(self) -> str:
        return self._uploaded_log_url

    @log_upload_url.setter
    def log_upload_url(self, value: str) -> None:
        if self._uploaded_log_url != value:
            self._uploaded_log_url = value
            self.uploaded_log_url_changed.emit(value)

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

        try:
            if self.proc:
                self.proc.kill()
        except ProcessLookupError:
            pass

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
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir_path = Path(tmpdirname)

            self._logger.debug("Exporting log data to a temporary file")
            self.export_progress = 0
            try:
                log_tar_file = await self._do_export(tmpdir_path)
                self.export_progress = 1
            except shutil.Error as exception:
                # shutil.Error concatenates the OSError errors like [(src, dst, str(why),]
                if exception.args:
                    code_re = re.compile(r"\[Errno\s*([0-9]*)\]")
                    args = exception.args[0]
                    for e in args:
                        why = e[-1]
                        error_no = int(code_re.search(why).group(1))
                        if error_no == errno.ENOSPC:
                            self._logger.error(why)
                            raise NotEnoughInternalSpace(why) from exception
                raise
            except OSError as exception:
                if exception.errno == errno.ENOSPC:
                    self._logger.error(exception.strerror)
                    raise NotEnoughInternalSpace(exception.strerror) from exception
                raise

            self._logger.debug("Running store log method")
            self.state = LogsState.SAVING
            self.store_progress = 0
            await self.store_log(log_tar_file)
            self.store_progress = 1

    async def _do_export(self, tmpdir_path: Path):
        logs_dir = tmpdir_path / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "log.txt"
        summary_file = logs_dir / "summary.json"
        display_usage_file = logs_dir / "display_usage.png"

        self._logger.info("Creating log export summary")
        summary = create_summary(self._hw, self._logger, summary_path = summary_file)
        if summary:
            self._logger.debug("Log export summary created")
        else:
            self._logger.error("Log export summary failed to create")

        self._logger.info("Creating display usage heatmap")
        try:
            display_usage_heatmap(
                    self._hw.exposure_screen.parameters,
                    defines.displayUsageData,
                    defines.displayUsagePalette,
                    display_usage_file)
        except DisplayUsageError as e:
            self._logger.warning("Display usage heatmap not exported: %s", e.reason)
        except Exception:
            self._logger.exception("Create display usage exception")

        self._logger.debug("Running log export script")
        self.proc = await self._run_log_export_process(log_file)

        self._logger.debug("Waiting for log export to finish")
        _, stderr = await self.proc.communicate()
        if self.proc.returncode != 0:
            error = "Log export jounalctl failed to create"
            if stderr:
                error += f" - {stderr.decode()}"
            self._logger.error(error)

        self._logger.debug("Waiting for configs export to finish")
        try:
            export_configs(logs_dir)
        except Exception:
            self._logger.exception("Config export exception")

        log_tar_file = tmpdir_path / get_logs_file_name(self._hw)
        self.proc = await asyncio.create_subprocess_shell(
            'tar -cf - -C "{0}" "{1}" | xz -T0 -0 > "{2}"'.format(str(tmpdir_path), logs_dir.name, str(log_tar_file)),
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await self.proc.communicate()
        if self.proc.returncode != 0:
            error = "Log compression failed"
            if stderr:
                error += f" - {stderr.decode()}"
            self._logger.error(error)

        self.proc = None

        if log_tar_file.is_file():
            return log_tar_file

    @staticmethod
    async def _run_log_export_process(log_file: Path) -> Process:
        return await asyncio.create_subprocess_shell(
            'export_logs.bash "{0}"'.format(str(log_file)),
            stderr=asyncio.subprocess.PIPE
        )


    @abstractmethod
    async def store_log(self, src: Path):
        ...


class UsbExport(LogsExport):
    async def store_log(self, src: Path):
        self.state = LogsState.SAVING
        save_path = get_save_path()
        if save_path is None or not save_path.parent.exists():
            raise NoExternalStorage()

        self._logger.debug("Copying temporary log file to usb")
        await self._copy_with_progress(src, save_path / src.name)

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
    def __init__(self, hw: BaseHardware, url: str):
        super().__init__(hw)
        self._url = url

    async def store_log(self, src: Path):

        self._logger.info("Uploading temporary log file to the server")

        async with aiohttp.ClientSession(headers={"user-agent": "OriginalPrusa3DPrinter"}) as session:
            self._logger.debug("Opening aiohttp client session")

            with src.open("rb") as file:
                data = aiohttp.FormData()
                data.add_field(
                    "logfile",
                    FileReader(file, callback=self._callback),
                    filename=src.name,
                    content_type="application/x-xz",
                )
                data.add_field("token", defines.log_upload_token)
                data.add_field("serial", self._hw.cpuSerialNo)

                try:
                    async with session.post(url=self._url, data=data) as response:
                        if response.status == 200:
                            self._logger.debug("aiohttp post done")
                            response_text = await response.text()
                            self._logger.debug("Log upload response: %s", response_text)
                            response_data = json.loads(response_text)
                            self.log_upload_identifier = response_data["id"] if "id" in response_data else response_data["url"]
                            self.log_upload_url = response_data["url"]
                        else:
                            strerror = f"Cannot connect to host {self._url} [status code: {response.status}]"
                            self._logger.error(strerror)
                            raise ConnectionFailed(strerror)
                except ClientConnectorError as exception:
                    self._logger.error(exception.strerror)
                    raise NotConnected(exception.strerror) from exception

    @property
    def type(self) -> StoreType:
        return StoreType.UPLOAD

    def _callback(self, position: int, total_size: int):
        self._logger.debug("Current upload position: %s / %s bytes", position, total_size)
        self.store_progress = position / total_size
