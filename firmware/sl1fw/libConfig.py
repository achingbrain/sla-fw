# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import re
import zipfile
from abc import abstractmethod, ABC
from pathlib import Path
from readerwriterlock import rwlock
from typing import Optional, List, Dict, Type, Union, Any, Callable
import logging
import toml

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
        self._lower_to_normal: Dict[str, str] = {}
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
    def __init__(self, _type: List[Type], default, key=None, factory=False, doc=""):
        """
        Config value constructor

        :param _type: List of types this value can be instance of. (used to specify [int, float], think twice before passing multiple values)
        :param default: Default value. Can be function that receives configuration instance as the only parameter and returns default value.
        :param key: Key name in the configuration file. If set to None (default) it will be set to property name.
        :param factory: Whenever the value should be stored in factory configuration file.
        :param doc: Documentation string fro the configuration item
        """
        super().__init__(self.value_getter, self._property_setter, self.value_deleter)
        self.name = None
        self.key = key
        self.type = _type
        self.default_value = default
        self.factory = factory
        self.config: Optional[BaseConfig] = None
        self.default_doc = doc

    def base_doc(self) -> str:
        """
        Get base docstring describing the value

        :return: Docstring text
        """
        if type(self.default_value) in self.type:
            doc_default = str(self.default_value).lower()
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

    @property
    def value(self):
        """
        Get current value stored in configuration file

        Data are read from Config instance as value instances are per config type.

        :return: Value
        """
        return self.config.data_values[self.name]

    @value.setter
    def value(self, value):
        self.config.data_values[self.name] = value

    @property
    def factory_value(self):
        """
        Get current factory value stored in configuration file

        Data are read from Config instance as value instances are per config type.

        :return: Value
        """
        return self.config.data_factory_values[self.name]

    @factory_value.setter
    def factory_value(self, value):
        self.config.data_factory_values[self.name] = value

    def set_runtime(self, name: str, config: BaseConfig) -> None:
        """
        Set instance of the config, this value is part of and its name

        :param name: Name of this value in the config
        :param config: Instance of config object this value is part of
        """
        assert isinstance(config, BaseConfig)
        self.name = name
        if self.key is None:
            self.key = name
        self.config = config
        self.value = None
        self.factory_value = None

    def _property_setter(self, _: BaseConfig, val) -> None:
        """
        Implementation of property setter passed to parent constructor

        This is used to throw away _ parameter in order to simplify API.

        :param _: Class instance the property is set on
        :param val: New value
        """
        self.value_setter(val)

    def value_setter(self, val, write_override: bool = False, factory: bool = False, dry_run=False) -> None:
        """
        Config item value setter

        :param val: New value to set (must have already correct type)
        :param write_override: Set value even when config is read-only (!is_master) Used internally while reading config data from file.
        :param factory: Whenever to set factory value instead of normal value. Defaults to normal value
        :param dry_run: If set to true the value is not actually set. Used to check value consistency.
        """
        try:
            if not self.config.is_master and not write_override:
                raise Exception("Cannot write to read-only config !!!")
            if val is None:
                raise ValueError(f"Using default for key {self.name} as {val} is None")
            if type(val) not in self.type:
                raise ValueError(f"Using default for key {self.name} as {val} is {type(val)} but should be {self.type}")
            adapted = self.adapt(val)
            if adapted != val:
                self.config.logger.warning(f"Adapting config value {self.name} from {val} to {adapted}")
            self.check(adapted)

            if dry_run:
                return

            if factory:
                self.factory_value = adapted
            else:
                self.value = adapted
        except (ValueError, ConfigException) as exception:
            raise ConfigException(f"Setting config value {self.name} to {val} failed") from exception

    def value_getter(self, _: BaseConfig) -> None:
        """
        Configuration value getter

        :param _: Configuration class instance, ignored
        """
        with self.config.lock.gen_rlock():
            if self.value is not None:
                return self.value

            if self.factory_value is not None:
                return self.factory_value

            if type(self.default_value) not in self.type and isinstance(self.default_value, Callable):
                return self.default_value(self.config)
            else:
                return self.default_value

    def value_deleter(self, _: BaseConfig):
        """
        Deleter for configuration class instance

        If value is deleted, it is reset to default or factory default.

        :param _: Configuration class instance, ignored
        """
        self.value = None

    @property
    def file_key(self) -> str:
        """
        Getter for file key for the configuration item.

        :return: File key string for the configuration value
        """
        return self.key if self.key else self.name

    def is_default(self) -> bool:
        """
        Test for value being set to default

        :return: True if default, False otherwise
        """
        return self.value is None and self.factory_value is None

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"Value({repr(self.value)})"


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

    def __init__(self, _type: List[Type], *args, length: Optional[int] = None, **kwargs):
        """
        List configuration value constructor

        :param _type: List of acceptable inner value types
        :param length: Required list length, None means no check
        """
        super().__init__([list], *args, **kwargs)
        self.length = length
        self.inner_type = _type
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

    def __getattr__(self, item: str):
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

        if key in self._config.values:
            self._config.values[key].value_setter(value, dry_run=True)

        # Update changed or reset it if change is returning to original value
        if value == getattr(self._config, key):
            if key in self._changed:
                del self._changed[key]
        else:
            self._changed[key] = value

    def __delattr__(self, item):
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
                obj.set_runtime(var, self)
                self.values[var] = obj
                if not var.islower():
                    self._lower_to_normal[var.lower()] = var

    def __str__(self) -> str:
        res = [f"{self.__class__.__name__}: {self._file_path} ({self._factory_file_path}):"]
        for val in dir(self.__class__):
            o = getattr(self.__class__, val)
            if isinstance(o, property):
                res.append(f"\t{val}: {getattr(self, val)}")
        return "\n".join(res)

    def __getattr__(self, key: str):
        if key in self._lower_to_normal:
            self.logger.warning("Config getattr using fallback lowcase name")
            return object.__getattribute__(self, self._lower_to_normal[key])
        raise AttributeError(f'Key: "{key}" not in config')

    def __setattr__(self, key: str, value: Any):
        if key.startswith("_"):
            return object.__setattr__(self, key, value)

        if key in self._lower_to_normal:
            self.logger.warning("Config setattr using fallback lowcase name")
            object.__setattr__(self, self._lower_to_normal[key], value)
        else:
            object.__setattr__(self, key, value)

    def logAllItems(self) -> None:
        """
        Log all items to the logger

        DEPRECATED, use str(config) and write result to any destination
        """
        self.logger.info(str(self))

    def get_writer(self) -> ConfigWriter:
        """
        Helper to get config writer wrapping this config

        :return: Config writer instance wrapping this config
        """
        return ConfigWriter(self)

    def read_file(self, file_path: Optional[Path] = None) -> None:
        """
        Read config data from file

        :param file_path: Pathlib path to file
        """
        with self.lock.gen_wlock():
            try:
                if self._factory_file_path:
                    self._read_file(self._factory_file_path, factory=True)
                if file_path:
                    self._read_file(file_path)
                elif self._file_path:
                    self._read_file(self._file_path)
                else:
                    raise ValueError("file_path is None and no file_path was passed to constructor")
            except FileNotFoundError as exception:
                raise ConfigException("Failed to read config") from exception

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
                    val.value_setter(data[key], write_override=True, factory=factory)
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
        with self.lock.gen_wlock():
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
        with self.lock.gen_wlock():
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
            if (not factory or val.factory) and (not val.is_default() or nondefault):
                obj[val.key] = val.value
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

    # def defaultsSet(self) -> bool:
    #     """
    #     Require all factory values to be read
    #     """
    #     # TODO: Rename to is_default_set
    #     for val in self.values.values():
    #         if val.factory and val.factory_value is None:
    #             self.logger.warning("Value %s has no factory defaults despite being factory", val.name)
    #             return False
    #     return True

    def defaultsSet(self) -> bool:
        """
        Require at last one value to have factory default set
        :return: True of factory default were set, False otherwise
        """
        for val in self.values.values():
            if val.factory_value is not None:
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
    uvCurrent = FloatValue(700.8, minimum=0.0, maximum=800.0, doc="UV LED current, DEPRECATED.")
    uvPwm = IntValue(
        lambda self: int(round(self.uvCurrent / 3.2)),
        minimum=0,
        maximum=250,
        factory=True,
        doc="Calibrated UV LED PWM.",
    )
    uvCalibTemp = IntValue(40, minimum=30, maximum=50)
    uvCalibIntensity = IntValue(140, minimum=80, maximum=200)

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


class WizardData(Config):
    # following values are for quality monitoring systems
    osVersion = TextValue()
    a64SerialNo = TextValue()
    mcSerialNo = TextValue()
    mcFwVersion = TextValue()
    mcBoardRev = TextValue()
    towerHeight = IntValue(-1)
    tiltHeight = IntValue(-1)
    uvCurrent = FloatValue(700.8, minimum=0.0, maximum=800.0)
    uvPwm = IntValue(lambda self: int(round(self.uvCurrent / 3.2)), minimum=0, maximum=250)

    # following values are measured and saved in initial wizard
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow1 = IntListValue(list())
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow2 = IntListValue(list())
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow3 = IntListValue(list())
    # fans RPM when using default PWM
    wizardFanRpm = IntListValue(list())
    # UV LED temperature at the beginning of test (should be close to ambient)
    wizardTempUvInit = FloatValue(-1)
    # UV LED temperature after warmup test
    wizardTempUvWarm = FloatValue(-1)
    # ambient sensor temperature
    wizardTempAmbient = FloatValue(-1)
    # A64 temperature
    wizardTempA64 = FloatValue(-1)
    # measured fake resin volume in wizard (without resin with rotated platform)
    wizardResinVolume = IntValue(-1)
    # tower axis sensitivity for homing
    towerSensitivity = IntValue(-1)
    # wizard was successfully finished
    wizardDone = IntValue(0)

    # following values are measured and saved in automatic UV LED calibration
    uvSensorData = IntListValue(list())
    uvTemperature = FloatValue(-273.2)
    uvDateTime = TextValue("_NOT_SET_")
    uvMean = FloatValue(-1)
    uvStdDev = FloatValue(-1)
    uvMinValue = IntValue(-1)
    uvMaxValue = IntValue(-1)
    uvPercDiff = FloatListValue(list())

    uvFoundCurrent = FloatValue(700.8, minimum=0.0, maximum=800.0, key="uvFoundCurrent")
    uvFoundPwm = IntValue(lambda self: int(round(self.uvFoundCurrent / 3.2)), minimum=0, maximum=250, factory=True)


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
    calibrateInfoLayers = IntValue(10, doc="Number of calibration layers that will include the label with exposure time.")

    raw_calibrate_penetration = FloatValue(0.5, doc="How much to sing calibration text to object. [millimeters]")

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

    def load(self):
        try:
            with open(self.filename, "r") as f:
                data = toml.load(f)
        except FileNotFoundError:
            self.logger.warning("File '%s' not found", self.filename)
            data = {}
        except Exception:
            self.logger.exception("Failed to load toml file")
            data = {}
        return data

    def save(self, data):
        try:
            with open(self.filename, "w") as f:
                toml.dump(data, f)
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
