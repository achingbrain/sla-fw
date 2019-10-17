# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import re
import zipfile
from abc import abstractmethod, ABC
from pathlib import Path
from typing import Optional, List, Dict, Type, Union, Any, Callable

import toml
from readerwriterlock import rwlock

from sl1fw import defines


class ConfigException(Exception):
    """
    Exception used to signal problems with configuration
    """


class BaseConfig(ABC):
    """
    Base class of the configuration

    This contains bare minimum for use by Value class
    """

    @abstractmethod
    def __init__(self, is_master: bool = False):
        self.lower_to_normal_map: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)
        self.is_master = is_master
        self.lock = rwlock.RWLockRead()
        self.data_values = {}
        self.data_factory_values = {}


class Value(property, ABC):
    """
    Base class for values included in configuration files.

    This class does most of the configuration magic. It inherits from property, so that ints instances can be
    set and read as properties. Also it holds data describing the configuration key such as name, key, type, default...
    The current value and factory value are provided as properties as these values needs to be stored in the
    configuration object. Keep in mind that the property is instantiated at class definition time. Multiple instances of
    the same configuration class share the value instances.

    Apart from data the Value class also implements necessary methods for the property access and implements basic
    value get/set logic including type checking and default/factory value reading. Additional check can be implemented
    by classes inheriting from Value by override of adapt and check methods.
    """

    @abstractmethod
    def __init__(self, value_type: List[Type], default, key=None, factory=False, doc=""):
        """
        Config value constructor

        :param value_type: List of types this value can be instance of. (used to specify [int, float], think twice before passing multiple values)
        :param default: Default value. Can be function that receives configuration instance as the only parameter and returns default value.
        :param key: Key name in the configuration file. If set to None (default) it will be set to property name.
        :param factory: Whenever the value should be stored in factory configuration file.
        :param doc: Documentation string fro the configuration item
        """

        def getter(config: BaseConfig) -> value_type[0]:
            with config.lock.gen_rlock():
                return self.value_getter(config)

        def setter(config: BaseConfig, val: value_type[0]):
            # TODO: Take a write lock once we get rid of writable properties
            # with self.config.lock.gen_wlock():
            self.value_setter(config, val)

        def deleter(config: BaseConfig):
            self.set_value(config, None)

        super().__init__(getter, setter, deleter)

        self.name = None
        self.key = key
        self.type = value_type
        self.default = default
        self.factory = factory
        self.default_doc = doc

    def base_doc(self) -> str:
        """
        Get base docstring describing the value

        :return: Docstring text
        """
        if type(self.default) in self.type:
            doc_default = str(self.default).lower()
        else:
            doc_default = "<Computed>"
        return f"""{self.default_doc}
        
            :type: {" ".join([t.__name__ for t in self.type])}
        
            :default: {str(doc_default).lower()}
            :key: {self.key}
        """

    def check(self, val) -> None:
        """
        Check value to match config file specification.

        This is called after value adaptation. This method is supposed to raise exceptions when value is not as
        requested. Default implementation is fine with any value.

        :param val: Value to check
        """

    def adapt(self, val):
        """
        Adapt value being set

        This method adapts value before it is checked ad stored as new configuration value. This is can be used to
        adjust the value to new minimum/maximum. Default implementation is pass-through.

        :param val: Value to adapt
        :return: Adapted value
        """
        return val

    def get_value(self, config: BaseConfig) -> Any:
        """
        Get current value stored in configuration file

        Data are read from Config instance as value instances are per config type.

        :param config: Config to read from
        :return: Value
        """
        return config.data_values[self.name]

    def set_value(self, config: BaseConfig, value: Any) -> None:
        config.data_values[self.name] = value

    def get_factory_value(self, config: BaseConfig) -> Any:
        """
        Get current factory value stored in configuration file

        Data are read from Config instance as value instances are per config type.

        :param config: Config to read from
        :return: Value
        """
        return config.data_factory_values[self.name]

    def set_factory_value(self, config: BaseConfig, value: Any) -> None:
        config.data_factory_values[self.name] = value

    def get_default_value(self, config: BaseConfig) -> Any:
        if type(self.default) not in self.type and isinstance(self.default, Callable):
            if config:
                return self.default(config)
            else:
                return self.default
        else:
            return self.default

    def setup(self, config: BaseConfig, name: str) -> None:
        """
        Set instance of the config, this value is part of and its name

        :param config: Config this value is part of
        :param name: Name of this value in the config
        """
        self.name = name
        if self.key is None:
            self.key = name
        self.set_value(config, None)
        self.set_factory_value(config, None)

    def value_setter(
        self, config: BaseConfig, val, write_override: bool = False, factory: bool = False, dry_run=False
    ) -> None:
        """
        Config item value setter

        :param config: Config to read from
        :param val: New value to set (must have already correct type)
        :param write_override: Set value even when config is read-only (!is_master) Used internally while reading config data from file.
        :param factory: Whenever to set factory value instead of normal value. Defaults to normal value
        :param dry_run: If set to true the value is not actually set. Used to check value consistency.
        """
        try:
            if not config.is_master and not write_override:
                raise Exception("Cannot write to read-only config !!!")
            if val is None:
                raise ValueError(f"Using default for key {self.name} as {val} is None")
            if type(val) not in self.type:
                raise ValueError(f"Using default for key {self.name} as {val} is {type(val)} but should be {self.type}")
            adapted = self.adapt(val)
            if adapted != val:
                config.logger.warning(f"Adapting config value {self.name} from {val} to {adapted}")
            self.check(adapted)

            if dry_run:
                return

            if factory:
                self.set_factory_value(config, adapted)
            else:
                self.set_value(config, adapted)
        except (ValueError, ConfigException) as exception:
            raise ConfigException(f"Setting config value {self.name} to {val} failed") from exception

    def value_getter(self, config: BaseConfig) -> Any:
        """
        Configuration value getter

        :param config: Config to read from
        :return: Config value or factory value or default value
        """
        if self.get_value(config) is not None:
            return self.get_value(config)

        if self.get_factory_value(config) is not None:
            return self.get_factory_value(config)

        return self.get_default_value(config)

    @property
    def file_key(self) -> str:
        """
        Getter for file key for the configuration item.

        :return: File key string for the configuration value
        """
        return self.key if self.key else self.name

    def is_default(self, config: BaseConfig) -> bool:
        """
        Test for value being set to default

        :param config: Config to read from
        :return: True if default, False otherwise
        """
        return (self.get_value(config) is None or self.get_value(config) == self.get_default_value(config)) and (
            self.get_factory_value(config) is None or self.get_factory_value(config) == self.get_default_value(config)
        )


class BoolValue(Value):
    """
    Bool configuration value class

    Just sets bool type to base Value class constructor. Bools do not require special handling.
    """

    def __init__(self, default: Optional[bool], **kwargs):
        super().__init__([bool], default, **kwargs)
        self.__doc__ = self.base_doc()


class NumericValue(Value):
    """
    Numerical configuration value class

    Accepts minimum and maximum, implements value adaptation.
    """

    def __init__(self, *args, minimum: Optional = None, maximum: Optional = None, **kwargs):
        """
        Numeric config value constructor

        :param minimum: Minimal allowed value, None means no restriction
        :param maximum: Maximal allowed value, None means no restriction
        """
        super().__init__(*args, **kwargs)
        self.min = minimum
        self.max = maximum
        self.__doc__ = f"""{self.base_doc()}
            :range: {self.min} - {self.max}
        """

    def adapt(self, val: Optional[Union[int, float]]):
        """
        Adapt value to minimum and maximum

        :param val: Initial value
        :return: Adapted value
        """
        if self.max is not None and val > self.max:
            return self.max

        if self.min is not None and val < self.min:
            return self.min

        return val


class IntValue(NumericValue):
    """
    Integer configuration value
    """

    def __init__(self, *args, **kwargs):
        super().__init__([int], *args, **kwargs)


class FloatValue(NumericValue):
    """
    Float configuration value
    """

    def __init__(self, *args, **kwargs):
        super().__init__([float, int], *args, **kwargs)


class ListValue(Value):
    """
    List configuration value

    Add length to value properties.
    """

    def __init__(self, value_type: List[Type], *args, length: Optional[int] = None, **kwargs):
        """
        List configuration value constructor

        :param value_type: List of acceptable inner value types
        :param length: Required list length, None means no check
        """
        super().__init__([list], *args, **kwargs)
        self.length = length
        self.inner_type = value_type
        self.__doc__ = self.base_doc()
        self.__doc__ = f"""{self.base_doc()}
            :length: {self.length}
        """

    def check(self, val: Optional[List[int]]) -> None:
        """
        Check list value for correct internal type and number of elements

        :param val: Value to check
        """
        if any([type(x) not in self.inner_type for x in val]):
            raise ValueError(f"Using default for key {self.name} as {val} is has incorrect inner type")
        if self.length is not None and len(val) != self.length:
            raise ValueError(f"Using default for key {self.name} as {val} does not match required length")


class IntListValue(ListValue):
    """
    Integer list configuration value
    """

    def __init__(self, *args, **kwargs):
        super().__init__([int], *args, **kwargs)


class FloatListValue(ListValue):
    """
   Float list configuration value
   """

    def __init__(self, *args, **kwargs):
        super().__init__([float, int], *args, **kwargs)


class TextValue(Value):
    """
    Text list configuration value
    """

    def __init__(self, default: Optional[str] = "", regex: str = ".*", **kwargs):
        """
        Text list configuration value constructor

        :param regex: Regular expression the string has to match.
        """
        super().__init__([str], default, **kwargs)
        self.regex = re.compile(regex)
        self.__doc__ = f"""{self.base_doc()}
            :regex: {regex}
        """

    def check(self, val: str) -> None:
        """
        Check value for regular expression match

        :param val: Value to check
        """
        if not self.regex.fullmatch(val):
            raise ValueError(f'Value {self.name} cannot be set. Value "{val}" does not match "{self.regex}"')


class ValueConfig(BaseConfig):
    """
    ValueConfig is as interface implementing all the necessary stuff for ConfigWriter operations
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values: Dict[str, Value] = {}

    @abstractmethod
    def write(self, file_path: Optional[Path] = None):
        ...


class ConfigWriter:
    """
    Class used as helper for transactional config writing

    The class mimics underlying config class attributes for value reading ang writting. The changes are propagated
    to underlying config on commit.
    """

    def __init__(self, config: ValueConfig):
        """
        Config writer constructor

        :param config: Underling configuration object
        """
        self._config = config
        self._changed: Dict[str:Any] = {}
        self._deleted = set()

    def _get_attribute_name(self, key: str) -> str:
        """
        Adjust attribute name in case of legacy lowcase name

        :param key: Low-case or new key
        :return: Valid key
        """
        if key in vars(self._config) or key in vars(self._config.__class__):
            return key
        if key in self._config.lower_to_normal_map:
            self._config.logger.warning("Config setattr using fallback low-case name: %s", key)
            return self._config.lower_to_normal_map[key]
        raise AttributeError(f'Key: "{key}" not in config')

    def __getattr__(self, item: str):
        item = self._get_attribute_name(item)
        if item in self._changed:
            return self._changed[item]
        elif item in self._deleted:
            return None
        else:
            return getattr(self._config, item)

    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
            return

        key = self._get_attribute_name(key)
        if key in self._config.values:
            self._config.values[key].value_setter(self._config, value, dry_run=True)
        else:
            self._config.logger.debug("Writer: Skipping dry run write on non-value: %s", key)

        # Update changed or reset it if change is returning to original value
        if value == getattr(self._config, key):
            if key in self._changed:
                del self._changed[key]
        else:
            self._changed[key] = value

    def __delattr__(self, item):
        item = self._get_attribute_name(item)
        self._deleted.add(item)

    def update(self, values: Dict[str, Any]):
        for key, val in values.items():
            self.__setattr__(key, val)

    def commit_dict(self, values: Dict):
        self.update(values)
        self.commit()

    def commit(self, write: bool = True):
        """
        Save changes to underlying config and write it to file

        :param: write Whenever to write configuration file
        """
        with self._config.lock.gen_wlock():
            for key, val in self._changed.items():
                if key in self._config.values:
                    self._config.values[key].value_setter(self._config, val)
                else:
                    setattr(self._config, key, val)

        self._changed = {}
        if write:
            self._config.write()

    def changed(self, key=None):
        """
        Test for changes relative to underlying config.

        :param key: Test only for specific key. If not specified or None changes on all keys are checked.
        :return: True if changed, false otherwise
        """
        if key is None:
            return bool(self._changed)
        else:
            return key in self._changed


class Config(ValueConfig):
    """
    Main config class.

    Inherit this to create a configuration
    """

    VAR_ASSIGN_PATTERN = re.compile(r"(?P<name>\w+) *= *(?P<value>.+)")
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
                self.values[var] = obj
                if not var.islower():
                    self.lower_to_normal_map[var.lower()] = var

    def __str__(self) -> str:
        res = [f"{self.__class__.__name__}: {self._file_path} ({self._factory_file_path}):"]
        for val in dir(self.__class__):
            o = getattr(self.__class__, val)
            if isinstance(o, Value):
                value = self.values[val].get_value(self)
                factory = self.values[val].get_factory_value(self)
                default = self.values[val].get_default_value(self)
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
        with self.lock.gen_wlock():
            try:
                if self._factory_file_path:
                    if self._factory_file_path.exists():
                        self._read_file(self._factory_file_path, factory=True)
                    else:
                        self.logger.info("Factory config file does not exists: %s", self._factory_file_path)
                if file_path is None:
                    file_path = self._file_path
                if file_path is None:
                    raise ValueError("file_path is None and no file_path was passed to constructor")
                if file_path.exists():
                    self._read_file(file_path)
                else:
                    self.logger.info("Config file does not exists: %s", file_path)
            except Exception as exception:
                raise ConfigException("Failed to read configuration files") from exception

    def _read_file(self, file_path: Path, factory: bool = False) -> None:
        with file_path.open("r") as f:
            text = f.read()
        try:
            self.read_text(text, factory=factory)
        except Exception as exception:
            raise ConfigException('Failed to parse config file: "%s"', file_path) from exception

    def read_text(self, text: str, factory: bool = False) -> None:
        """
        Read config data from string

        :param text: Config text
        :param factory: Whenever to read factory configuration
        """
        # Drop inconsistent newlines, use \n
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split config to lines, process each line separately
        lines = []
        for line in text.split("\n"):
            # Drop empty lines
            line = line.strip()
            if not line:
                continue

            # Split line to variable name and value
            match = self.VAR_ASSIGN_PATTERN.match(line)
            if not match:
                self.logger.warning("Line ignored as it does not match name=value pattern:\n%s", line)
                continue
            name = match.groupdict()["name"].strip()
            value = match.groupdict()["value"].strip()

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
        text = "\n".join(lines)
        try:
            data = toml.loads(text)
        except toml.TomlDecodeError as exception:
            raise ConfigException("Failed to decode config content:\n %s", text) from exception

        for val in self.values.values():
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
                self.logger.exception("Setting config value %s to %s failed" % (val.name, val))
        if data:
            self.logger.warning("Extra data in configuration source: \n %s" % data)

    def write(self, file_path: Optional[Path] = None) -> None:
        """
        Write configuration file

        :param file_path: Optional file pathlib Path, default is to save to path set during construction
        """
        with self.lock.gen_rlock():
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
        with self.lock.gen_rlock():
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
        for val in self.values.values():
            if (not factory or val.factory) and (not val.is_default(self) or nondefault):
                obj[val.key] = val.value_getter(self)
        return obj

    def _write_file(self, file_path: Path, factory: bool = False):
        if not self.is_master:
            raise ConfigException("Cannot safe config that is not master")
        try:
            with file_path.open("w") as f:
                toml.dump(self.as_dictionary(nondefault=False, factory=factory), f)
        except Exception as exception:
            raise ConfigException("Failed to write config file") from exception

    def factory_reset(self) -> None:
        """
        Do factory rest

        This does not save the config. Explict call to save is necessary
        """
        with self.lock.gen_wlock():
            for val in self.values.values():
                val.value = None

    def is_factory_read(self) -> bool:
        """
        Require at last one value to have factory default set

        :return: True of factory default were set, False otherwise
        """
        for val in self.values.values():
            if val.get_factory_value(self) is not None:
                return True
        return False


class HwConfig(Config):
    # pylint: disable=R0902
    """
       Hardware configuration is read from /etc/sl1fw/hardware.cfg . Currently the content is parsed using a Toml
       parser with preprocessor that adjusts older custom configuration format if necessary. Members describe
       possible configuration options. These can be set using the

       key = value

       notation. For details see Toml format specification: https://en.wikipedia.org/wiki/TOML
    """

    def calcMicroSteps(self, mm: float) -> int:
        """
        Convert from millimeters to microsteps using current tower pitch.

        :param mm: Tower position in millimeters
        :return: Tower position in microsteps
        """
        return int(mm * self.microStepsMM)

    def calcMM(self, microSteps: int) -> float:
        """
        Convert microsteps to millimeters using current tower pitch.

        :param microSteps: Tower position in microsteps
        :return: Tower position in millimeters
        """
        return round(float(microSteps) / self.microStepsMM, 3)

    fanCheck = BoolValue(True, doc="Check fan function if set to True.")
    coverCheck = BoolValue(True, doc="Check for closed cover during printer movements and exposure if set to True.")
    MCversionCheck = BoolValue(True, doc="Check motion controller firmware version if set to True.")
    resinSensor = BoolValue(True, doc="If True the the resin sensor will be used to measure resin level before print.")
    autoOff = BoolValue(True, doc="If True the printer will be shut down after print.")
    mute = BoolValue(False, doc="Mute motion controller speaker if set to True.")
    screwMm = IntValue(4, doc="Pitch of the tower/platform screw. [mm]")

    @property
    def microStepsMM(self) -> float:
        """
        Get number of microsteps per millimeter suing current tower scre picth.

        :return: Number of microsteps per one millimeter
        """
        return 200 * 16 / int(self.screwMm)

    tiltHeight = IntValue(defines.defaultTiltHeight, doc="Position of the leveled tilt. [microsteps]")
    stirringMoves = IntValue(3, minimum=1, maximum=10, doc="Number of stirring moves")
    stirringDelay = IntValue(5, minimum=0, maximum=300)
    measuringMoves = IntValue(3, minimum=1, maximum=10)
    pwrLedPwm = IntValue(100, minimum=0, maximum=100, doc="Power LED brightness. [%]")

    MCBoardVersion = IntValue(6, minimum=5, maximum=6, doc="Motion controller board revision. Used to flash firmware.")

    # Advanced settings
    tiltSensitivity = IntValue(0, minimum=-2, maximum=2, doc="Tilt sensitivity adjustment")
    towerSensitivity = IntValue(0, minimum=-2, maximum=2, factory=True, doc="Tower sensitivity adjustment")
    limit4fast = IntValue(45, minimum=0, maximum=100, doc="Fast tearing is used if layer area is under this value. [%]")

    @property
    def whitePixelsThd(self) -> float:
        return 1440 * 2560 * self.limit4fast / 100.0

    calibTowerOffset = IntValue(
        lambda self: self.calcMicroSteps(defines.defaultTowerOffset),
        doc="Adjustment of zero on the tower axis. [microsteps]",
    )

    # Exposure setup
    blinkExposure = BoolValue(True, doc="If True the UV LED will be powered off when not used during print.")
    perPartes = BoolValue(False, doc="Expose areas larger than layerFill in two steps.")
    tilt = BoolValue(True, doc="Use tilt to tear off the layers.")
    upAndDownUvOn = BoolValue(False)

    trigger = IntValue(
        0, minimum=0, maximum=20, doc="Duration of electronic trigger durint the layer change. [tenths of a second]"
    )
    layerTowerHop = IntValue(
        0, minimum=0, maximum=8000, doc="How much to rise the tower during layer change. [microsteps]"
    )
    delayBeforeExposure = IntValue(
        0, minimum=0, maximum=300, doc="Delay between tear off and exposure. [tenths of a second]"
    )
    delayAfterExposure = IntValue(
        0, minimum=0, maximum=300, doc="Delay between exposure and tear off. [tenths of a second]"
    )
    upAndDownWait = IntValue(10, minimum=0, maximum=600, doc="Up&Down wait time. [seconds]")
    upAndDownEveryLayer = IntValue(0, minimum=0, maximum=500, doc="Do Up&Down every N layers, 0 means never.")
    upAndDownZoffset = IntValue(0, minimum=-800, maximum=800)
    upAndDownExpoComp = IntValue(0, minimum=-10, maximum=300)

    # Fans & LEDs
    fan1Rpm = IntValue(1800, minimum=500, maximum=3000, factory=True, doc="UV LED fan RPMs.")
    fan2Rpm = IntValue(3700, minimum=500, maximum=3700, factory=True, doc="Blower fan RPMs.")
    fan3Rpm = IntValue(1000, minimum=400, maximum=5000, factory=True, doc="Rear fan RPMs.")
    uvCurrent = FloatValue(0.0, minimum=0.0, maximum=800.0, doc="UV LED current, DEPRECATED.")
    uvPwm = IntValue(
        lambda self: int(round(self.uvCurrent / 3.2)),
        minimum=0,
        maximum=250,
        factory=True,
        doc="Calibrated UV LED PWM.",
    )
    uvWarmUpTime = IntValue(120, minimum=0, maximum=300, doc="UV LED calibration warmup time. [seconds]")
    uvCalibIntensity = IntValue(150, minimum=90, maximum=200, doc="UV LED calibration intensity.")
    uvCalibMinIntEdge = IntValue(90, minimum=80, maximum=150, doc="UV LED calibration minimum intensity at the edge.")

    # Tilt & Tower -> Tilt tune
    raw_tiltdownlargefill = IntListValue([5, 650, 1000, 4, 1, 0, 64, 3], length=8, key="tiltdownlargefill")
    raw_tiltdownsmallfill = IntListValue([5, 0, 0, 6, 1, 0, 0, 0], length=8, key="tiltdownsmallfill")
    raw_tiltup = IntListValue([2, 400, 0, 5, 1, 0, 0, 0], length=8, key="tiltup")

    @property
    def tuneTilt(self) -> List[List[int]]:
        return [self.raw_tiltdownlargefill, self.raw_tiltdownsmallfill, self.raw_tiltup]

    @tuneTilt.setter
    def tuneTilt(self, value: List[List[int]]):
        [self.raw_tiltdownlargefill, self.raw_tiltdownsmallfill, self.raw_tiltup] = value

    raw_calibrated = BoolValue(False, key="calibrated")

    @property
    def calibrated(self) -> bool:
        """
        Printer calibration state

        The value can read as False when set to True as further requirements on calibration are checked in the getter.

        :return: True if printer is calibrated, False otherwise
        """
        # TODO: Throw away raw_calibrated, judge calibrated based on tilt/tower height
        return self.raw_calibrated and self.tiltHeight % 64 == 0

    @calibrated.setter
    def calibrated(self, value: bool) -> None:
        self.raw_calibrated = value

    towerHeight = IntValue(
        lambda self: self.calcMicroSteps(defines.defaultTowerHeight), doc="Maximum tower height. [microsteps]"
    )
    tiltFastTime = FloatValue(5.5, doc="Time necessary to perform fast tear off.")
    tiltSlowTime = FloatValue(8.0, doc="Time necessary to perform slow tear off.")
    showWizard = BoolValue(True, doc="Display wizard at startup if True.")
    showUnboxing = BoolValue(True, doc="Display unboxing wizard at startup if True.")


class PrintConfig(Config):
    """
    Print configuration is read from config.ini located in the project zip file. Currently the content is parsed using
    a Toml parser with preprocessor that adjusts older custom configuration format if necessary. Members describe
    possible configuration options. These can be set using the

    key = value

    notation. For details see Toml format specification: https://en.wikipedia.org/wiki/TOML
    """

    def __init__(self, hw_config: HwConfig):
        super().__init__(is_master=True)
        self._hw_config = hw_config
        self.totalLayers = 0
        self.zipError = None
        self._data = dict()  # TODO: Is this necessary ?
        self._lines = list()  # TODO: Is this necessary ?
        self.modificationTime = None
        self.toPrint = None
        self._configFile = None
        self.origin = None
        self.zipName = None

    projectName = TextValue("no project", key="jobDir", doc="Name of the project.")

    expTime = FloatValue(8.0, doc="Exposure time. [s]")
    expTime2 = FloatValue(lambda self: self.expTime, doc="Exposure time 2. [s]")
    expTime3 = FloatValue(lambda self: self.expTime, doc="Exposure time 3. [s]")
    expTimeFirst = FloatValue(35.0, doc="First layer exposure time. [s]")

    layerHeight = FloatValue(-1, doc="Layer height, if not equal to -1 supersedes stepNum. [mm]")
    layerHeight2 = FloatValue(
        lambda self: self.layerHeight, doc="Layer height 2, if not equal to -1 supersedes stepNum2. [mm]"
    )
    layerHeight3 = FloatValue(
        lambda self: self.layerHeight, doc="Layer height 3, if not equal to -1 supersedes stepNum3. [mm]"
    )

    stepnum = IntValue(40, doc="Layer height [microsteps]")
    stepnum2 = IntValue(lambda self: self.layerMicroSteps, doc="Layer height 2 [microsteps]")
    stepnum3 = IntValue(lambda self: self.layerMicroSteps, doc="Layer height 3 [microsteps]")

    @property
    def layerMicroSteps(self) -> int:
        if self.layerHeight > 0.0099:
            return self._hw_config.calcMicroSteps(self.layerHeight)
        else:
            # historicky zmatlano aby sedelo ze pri 8 mm na otacku stepNum = 40 odpovida 0.05 mm
            return self.stepnum / (self._hw_config.screwMm / 4)

    @property
    def layerMicroSteps2(self) -> int:
        if self.layerHeight > 0.0099:
            return self._hw_config.calcMicroSteps(self.layerHeight2)
        else:
            # historicky zmatlano aby sedelo ze pri 8 mm na otacku stepNum = 40 odpovida 0.05 mm
            return self.stepnum2

    @property
    def layerMicroSteps3(self) -> int:
        if self.layerHeight > 0.0099:
            return self._hw_config.calcMicroSteps(self.layerHeight3)
        else:
            # historicky zmatlano aby sedelo ze pri 8 mm na otacku stepNum = 40 odpovida 0.05 mm
            return self.stepnum3

    layerHeightFirst = FloatValue(0.05)

    @property
    def layerMicroStepsFirst(self) -> int:
        return self._hw_config.calcMicroSteps(self.layerHeightFirst)

    slice2 = IntValue(9999998, doc="Layer number defining switch to parameters 2.")
    slice3 = IntValue(9999999, doc="Layer number defining switch to parameters 3.")
    fadeLayers = IntValue(
        10,
        minimum=3,
        maximum=200,
        key="numFade",
        doc="Number of layers used for transition from first layer exposure time to standard exposure time.",
    )

    calibrateTime = FloatValue(
        lambda self: self.expTime, doc="Time added to exposure per calibration region. [seconds]"
    )
    calibrateRegions = IntValue(0, doc="Number of calibration regions (2, 4, 6, 8, 9), 0 = off")
    calibrateInfoLayers = IntValue(
        10, doc="Number of calibration layers that will include the label with exposure time."
    )

    raw_calibrate_penetration = FloatValue(
        0.5, key="calibratePenetration", doc="How much to sing calibration text to object. [millimeters]"
    )

    @property
    def calibratePenetration(self) -> int:
        return int(self.raw_calibrate_penetration / defines.screenPixelSize)

    usedMaterial = FloatValue(
        defines.resinMaxVolume - defines.resinMinVolume,
        doc="Resin necessary to print the object. Default is full tank. [milliliters]",
    )
    layersSlow = IntValue(0, key="numSlow", doc="Number of layers that require slow tear off.")
    layersFast = IntValue(0, key="numFast", doc="Number of layers that do not require slow tear off.")

    # TODO: We can define totallayers as this, but we do not use it and later set it to number of images in the project.
    # @property
    # def totalLayers(self) -> int:
    #     return self.layersSlow + self.layersFast

    action = TextValue(doc="What to do with the project. Legacy value, currently discarded.")

    def parseFile(self, zipName: str) -> None:
        # zipError = TextValue("No data was read.")

        self._data = dict()
        self._lines = list()

        # for defaults
        if zipName is None:
            self.read_text("")
            return

        self.logger.debug("Opening project file '%s'", zipName)

        if not Path(zipName).exists():
            self.logger.error("Project lookup exception: file not exists: " + zipName)
            self.zipError = _("Project file not found.")
            return

        self.toPrint = []
        self.zipError = _("Can't read project data.")

        # TODO: Get project completition time from config file once it is available
        # TODO: modificationTime is not read from config. Thus it does not belong here.
        try:
            self.modificationTime = Path(zipName).stat().st_mtime
        except Exception as e:
            self.logger.exception("Cannot get project modification time:" + str(e))

        try:
            zf = zipfile.ZipFile(zipName, "r")
            self.read_text(zf.read(defines.configFile).decode("utf-8"))
            namelist = zf.namelist()
            zf.close()
        except Exception as e:
            self.logger.exception("zip read exception:" + str(e))
            return

        # Set paths
        dirName = os.path.dirname(zipName)
        self._configFile = os.path.join(dirName, "FAKE_" + defines.configFile)
        self.origin = self.zipName = zipName

        for filename in namelist:
            fName, fExt = os.path.splitext(filename)
            if fExt.lower() == ".png" and fName.startswith(self.projectName):
                self.toPrint.append(filename)

        self.toPrint.sort()
        self.totalLayers = len(self.toPrint)

        self.logger.debug("found %d layers", self.totalLayers)
        if self.totalLayers < 2:
            self.zipError = _("Not enough layers.")
        else:
            self.zipError = None


class TomlConfig:
    def __init__(self, filename):
        self.logger = logging.getLogger(__name__)
        self.filename = filename
        self.data = {}

    def load(self):
        try:
            with open(self.filename, "r") as f:
                self.data = toml.load(f)
        except FileNotFoundError:
            self.logger.warning("File '%s' not found", self.filename)
            self.data = {}
        except Exception:
            self.logger.exception("Failed to load toml file")
            self.data = {}
        return self.data

    def save_raw(self):
        with open(self.filename, "w") as f:
            toml.dump(self.data, f)

    def save(self, data):
        try:
            self.data = data
            self.save_raw()
        except Exception:
            self.logger.exception("Failed to save toml file")
            return False
        return True


class TomlConfigStats(TomlConfig):
    def __init__(self, filename, hw):
        super(TomlConfigStats, self).__init__(filename)
        self.hw = hw

    def load(self):
        data = super(TomlConfigStats, self).load()
        if not data:
            data["projects"] = 0
            data["layers"] = 0
            # this is not so accurate but better than nothing
            data["total_seconds"] = self.hw.getUvStatistics()[0]
        return data
