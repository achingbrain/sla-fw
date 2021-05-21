# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020-2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import toml

from sl1fw.configs.value import ValueConfig, Value, BoolValue, ListValue, TextValue
from sl1fw.configs.writer import ConfigWriter
from sl1fw.errors.errors import ConfigException


class Config(ValueConfig):
    """
    Main config class.

    Inherit this to create a configuration
    """

    VAR_ASSIGN_PATTERN = re.compile(r"(?P<name>\w+) *= *(?P<value>.+)")
    COMMENT_PATTERN = re.compile(r"#.*")
    ON_YES_PATTERN = re.compile(r"^(on|yes)$")
    OFF_NO_PATTERN = re.compile(r"^(off|no)$")
    NUM_LIST_ONLY = re.compile(r"\A([0-9.-]+ +)+[0-9.-]+\Z")
    NUM_SEP = re.compile(r"\s+")

    # match string whit is not true, false, number or valid string in ""
    # the structure is: EQUALS ANYTHING(but not "true",..) END
    # ANYTHING is (.+) preceded by negative lookahead
    # END is (?=\n|$) - positive lookahead, we want \n or $ to follow
    STRING_PATTERN = re.compile(
        r"\A(?!"  # NL(negative lookahead) in form (...|...|...)
        r"\Atrue\Z|"  # NL part1 - true and end of the line or input
        r"\Afalse\Z|"  # NL part2 - false and end of the line or input
        r"\A[0-9.-]+\Z|"  # NL part3 - number at end of the line or input
        r'\A".*"\Z|'  # NL part4 - string already contained in ""
        r"\A\[ *(?:[0-9.-]+ *, *)+[0-9.-]+ *,? *]\Z"  # NL part4 - number list already in []
        r")"  # end of NL
        r"(.+)\Z"  # the matched string + positive lookahead for end
    )
    SURE_STRING_PATTERN = re.compile(
        r"\A(?!"  # NL(negative lookahead) in form (...|...|...)
        r'\A".*"\Z|'  # NL part4 - string already contained in ""
        r"\A\[ *(?:[0-9.-]+ *, *)+[0-9.-]+ *,? *]\Z"  # NL part4 - number list already in []
        r")"  # end of NL
        r"(.+)\Z"  # the matched string + positive lookahead for end
    )

    def __init__(
        self, file_path: Optional[Path] = None, factory_file_path: Optional[Path] = None, is_master: bool = False
    ):
        """
        Configuration constructor

        :param file_path: Configuration file path
        :param factory_file_path: Factory configuration file path
        :param is_master: If True this instance in master, can write to the configuration file
        """
        if factory_file_path is None and file_path is None:
            is_master = True
        super().__init__(is_master=is_master)
        self._file_path = file_path
        self._factory_file_path = factory_file_path

        for var in vars(self.__class__):
            obj = getattr(self.__class__, var)
            if isinstance(obj, Value):
                obj.setup(self, var)
                self._values[var] = obj
                if not var.islower():
                    self._lower_to_normal_map[var.lower()] = var

    def __str__(self) -> str:
        res = [f"{self.__class__.__name__}: {self._file_path} ({self._factory_file_path}):"]
        for val in dir(self.__class__):
            o = getattr(self.__class__, val)
            if isinstance(o, Value):
                value = self._values[val].get_value(self)
                factory = self._values[val].get_factory_value(self)
                default = self._values[val].get_default_value(self)
                res.append(f"\t{val}: {getattr(self, val)} ({value}, {factory}, {default})")
            elif isinstance(o, property):
                res.append(f"\t{val}: {getattr(self, val)}")

        return "\n".join(res)

    def get_writer(self) -> ConfigWriter:
        """
        Helper to get config writer wrapping this config

        :return: Config writer instance wrapping this config
        """
        return ConfigWriter(self)

    def read_file(self, file_path: Optional[Path] = None) -> None:
        """
        Read config data from config file

        :param file_path: Pathlib path to file
        """
        with self._lock.gen_wlock():
            try:
                if self._factory_file_path:
                    if self._factory_file_path.exists():
                        self._read_file(self._factory_file_path, factory=True)
                    else:
                        self._logger.info("Factory config file does not exists: %s", self._factory_file_path)
                if file_path is None:
                    file_path = self._file_path
                if file_path is None:
                    raise ValueError("file_path is None and no file_path was passed to constructor")
                if file_path.exists():
                    self._read_file(file_path)
                else:
                    self._logger.info("Config file does not exists: %s", file_path)
            except Exception as exception:
                raise ConfigException("Failed to read configuration files") from exception

    def _read_file(self, file_path: Path, factory: bool = False) -> None:
        with file_path.open("r") as f:
            text = f.read()
        try:
            self.read_text(text, factory=factory)
        except Exception as exception:
            raise ConfigException('Failed to parse config file: "%s"' % file_path) from exception

    def read_text(self, text: str, factory: bool = False) -> None:
        """
        Read config data from string

        :param text: Config text
        :param factory: Whenever to read factory configuration
        """
        # Drop inconsistent newlines, use \n
        text = self._normalize_text(text)
        try:
            data = toml.loads(text)
        except toml.TomlDecodeError as exception:
            raise ConfigException("Failed to decode config content:\n %s" % text) from exception

        for val in self._values.values():
            try:
                key = None
                if val.file_key in data:
                    key = val.file_key
                elif val.file_key.lower() in data:
                    key = val.file_key.lower()
                if key is not None:
                    val.value_setter(self, data[key], write_override=True, factory=factory)
                    del data[key]
            except (KeyError, ConfigException):
                self._logger.exception("Setting config value %s to %s failed", val.name, val)
        if data:
            self._logger.warning("Extra data in configuration source: \n %s", data)

    def _normalize_text(self, text: str) -> str:
        """
        Normalize config text

        - Normalize newlines
        - Fix old config format to toml

        :param text: Raw config text
        :return: TOML compatible config text
        """
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split config to lines, process each line separately
        lines = []
        for line in text.split("\n"):
            # Drop empty lines and comments
            line = line.strip()
            if not line or self.COMMENT_PATTERN.match(line):
                continue

            # Split line to variable name and value
            match = self.VAR_ASSIGN_PATTERN.match(line)
            if not match:
                self._logger.warning("Line ignored as it does not match name=value pattern:\n%s", line)
                continue
            name = match.groupdict()["name"].strip()
            value = match.groupdict()["value"].strip()

            # Obtain possibly matching config value for type hints
            value_hint = None
            for val in self._values.values():
                if val.file_key == name:
                    value_hint = val
                elif val.file_key.lower() == name:
                    value_hint = val

            if isinstance(value_hint, BoolValue):
                # Substitute on, off, yes, no with true and false
                value = self.ON_YES_PATTERN.sub("true", value)
                value = self.OFF_NO_PATTERN.sub("false", value)
            elif isinstance(value_hint, ListValue) and self.NUM_LIST_ONLY.match(value):
                # Wrap number lists in [] and separate numbers by comma
                value = self.NUM_SEP.sub(r", ", value)
                value = f"[{value}]"
            elif isinstance(value_hint, TextValue):
                # Wrap strings in ""
                value = self.SURE_STRING_PATTERN.sub(r'"\1"', value)
            else:
                # This is an unknown value, lets guess

                # Substitute on, off, yes, no with true and false
                value = self.ON_YES_PATTERN.sub("true", value)
                value = self.OFF_NO_PATTERN.sub("false", value)

                # Wrap number lists in [] and separate numbers by comma
                if self.NUM_LIST_ONLY.match(value):
                    value = self.NUM_SEP.sub(r", ", value)
                    value = f"[{value}]"

                # Wrap possible strings in ""
                value = self.STRING_PATTERN.sub(r'"\1"', value)

            lines.append(f"{name} = {value}")
        return "\n".join(lines)

    def write(self, file_path: Optional[Path] = None) -> None:
        """
        Write configuration file

        :param file_path: Optional file pathlib Path, default is to save to path set during construction
        """
        with self._lock.gen_rlock():
            if file_path is None:
                file_path = self._file_path
            try:
                self._write_file(file_path, factory=False)
            except Exception as exception:
                raise ConfigException(f'Cannot save config to: "{file_path}"') from exception

    def write_factory(self, file_path: Optional[Path] = None) -> None:
        """
        Write factory configuration file

        :param file_path: Optional file pathlib Path, default is to save to path set during construction
        """
        with self._lock.gen_rlock():
            if file_path is None:
                file_path = self._factory_file_path

            self._write_file(file_path, factory=True)

    def as_dictionary(self, nondefault: bool = True, factory: bool = False):
        """
        Get config content as dictionary

        :param nondefault: Return only values that are not set to defaults
        :param factory: Return set of config values that are supposed to be stored in factory config
        """
        obj = {}
        for val in self._values.values():
            if (not factory or val.factory) and (not val.is_default(self) or nondefault):
                obj[val.key] = val.value_getter(self)
        return obj

    def _write_file(self, file_path: Path, factory: bool = False):
        self._logger.info("Writing config to %s", file_path)
        if not self._is_master:
            raise ConfigException("Cannot safe config that is not master")
        try:
            data = toml.dumps(self.as_dictionary(nondefault=False, factory=factory))
            if not file_path.exists() or file_path.read_text() != data:
                file_path.write_text(data)
            else:
                self._logger.info("Skipping config update as no change is to be written")

        except Exception as exception:
            raise ConfigException("Failed to write config file") from exception

    def factory_reset(self) -> None:
        """
        Do factory rest

        This does not save the config. Explict call to save is necessary
        """
        self._logger.info("Running factory reset on config")
        with self._lock.gen_wlock():
            for val in self._values.values():
                val.set_value(self, None)

    def is_factory_read(self) -> bool:
        """
        Require at last one value to have factory default set

        :return: True of factory default were set, False otherwise
        """
        for val in self._values.values():
            if val.get_factory_value(self) is not None:
                return True
        return False

    def get_altered_values(self) -> Dict[str, Tuple[Any, Any]]:
        """
        Get map of altered values

        These values were adjusted from the values set in config according to limits set in the configuration
        specification.

        :return: String -> (adapted, raw) mapping.
        """
        return {
            name: (value.get_value(self), value.get_raw_value(self))
            for name, value in self.get_values().items()
            if value.get_value(self) != value.get_raw_value(self)
        }
