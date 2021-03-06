import os
import sys
import yaml
import argparse
import random
import json
from urllib.parse import unquote
from string import ascii_letters

from credit import RoundCredits
from constants import DEFAULT_FPS


def get_random_name():
    return "Random {}".format("".join([
        random.choice(ascii_letters)
        for _ in range(4)
    ]))


class BeatSection:
    def __init__(self, bmcfg_json_element):
        self.start = bmcfg_json_element["_1"]
        self.stop = bmcfg_json_element["_2"]
        self.bpm = bmcfg_json_element["_3"]["#val"].get("bpm", None)
        self.pattern_duration = bmcfg_json_element["_3"]["#val"].get(
            "patternDuration", None)

    def validate(self):
        if type(self.start) != float:
            raise ValueError("BM Section: wrong type for start "
                             + "({}), must be float".format(
                                 self.start))
        elif type(self.stop) != float:
            raise ValueError("BM Section: wrong type for stop "
                             + "({}), must be float".format(
                                 self.stop))
        elif self.bpm is not None and type(self.bpm) != float:
            raise ValueError("BM Section: wrong type for bpm "
                             + "({}), must be float".format(
                                 self.bpm))
        elif (self.pattern_duration is not None
              and type(self.pattern_duration) != float):
            raise ValueError("BM Section: wrong type for pattern_duration "
                             + "({}), must be float".format(
                                 self.pattern_duration))
        elif self.bpm is None and self.pattern_duration is None:
            raise ValueError("BM Section: undefined beat section")


class BeatMeterConfig:
    def __init__(self, bmcfg_json: dict):
        data = bmcfg_json["data"]
        self.sections = list(map(
            lambda e: BeatSection(e),
            list(filter(
                lambda e: e["play"],
                data["content"]["#elems"]
            ))[0]["content"]["#elems"]
        ))

        self.fps = data["flyingBeatmeter"
                        if data["flying"] else
                        "waveformBeatmeter"]["frames"]

        music_path = unquote(data["audio"]["#elems"][0])
        self.music = str(os.path.abspath(music_path))

        base_content = list(filter(lambda e: e["title"] == "Base",
                                   data["content"]["#elems"])
                            )[0]["content"]["#elems"][0]
        self.bpm = base_content["_3"]["#val"]["bpm"]
        self.duration = base_content["_2"]

    def validate(self):
        for section in self.sections:
            section.validate()
        if type(self.fps) != float:
            raise ValueError(
                "BMCFG: wrong type for fps ({}), must be float".format(
                    self.fps))
        elif type(self.music) != str:
            raise ValueError(
                "BMCFG: wrong type for music ({}), must be str".format(
                    self.music))
        elif type(self.bpm) != float:
            raise ValueError(
                "BMCFG: wrong type for bpm ({}), must be float".format(
                    self.bpm))
        elif type(self.duration) != float:
            raise ValueError(
                "BMCFG: wrong type for duration "
                + "({}), must be float".format(
                    self.duration))


class RoundConfig:
    # pylint: disable=no-member, access-member-before-definition
    ITEMS = {
        "name": {
            "type": str,
            "default": None,
        },
        "_is_on_disk": {
            "type": bool,
            "default": False,
        },
        "bpm": {
            "type": float,
            "min": 1,
            "max": 10000,
            "default": 120,
        },
        "duration": {
            "min": 1,
            "max": 10000,
            "type": float,
        },
        "speed": {
            "type": int,
            "min": 1,
            "max": 5,
            "default": 3,
        },
        "audio_level": {
            "type": float,
            "min": 0,
            "max": 10000000,
            "default": 0,
        },
        "cut": {
            "type": str,
            "default": "interleave",
            "choices": ["skip", "interleave", "randomize", "sequence"],
        },
        "beats": {
            "type": str,
            "default": None,
            "exts": [("MP3 files", "*.mp3"), ("WAV files", "*.wav")],
        },
        "beatmeter": {
            "type": str,
            "default": None,
            "exts": [],
        },
        "bmcfg": {
            "type": str,
            "default": None,
            "exts": [
                ("JSON files", "*.json"),
                ("Beatmeter Config Files", "*.bmcfg"),
            ],
        },
        "music": {
            "type": str,
            "default": None,
            "exts": [("WAV files", "*.wav"), ("MP3 files", "*.mp3")],
        },
        "background": {
            "type": str,
            "default": None,
            "exts": [("mp4 files", "*.mp4"), ("avi files", "*.avi")],
        },
        "sources": {
            "type": list,
            "exts": [("mp4 files", "*.mp4"), ("avi files", "*.avi")],
        },
        "credits": {
            "type": RoundCredits,
            "default": {"audio": [], "video": []},
        },
    }

    def __init__(self, config: dict or str, load=False):

        settings_folder = os.path.abspath(os.getcwd())
        if type(config) == str:
            round_folder = os.path.abspath(os.path.dirname(config))
            os.chdir(round_folder)
            if load:
                round_filename = os.path.basename(config)
                with open(round_filename) as config_file:
                    config = yaml.load(config_file)
        if config["bmcfg"] is not None:
            self.load_beatmeter_config(config)

        os.chdir(settings_folder)

        try:
            for attribute, validation in self.ITEMS.items():
                if "default" in validation:
                    value = config.get(attribute, validation["default"])
                else:
                    value = config[attribute]
                value = None if value is None else validation["type"](value)
                self.__setattr__(attribute, value)
        except ValueError as err:
            print("ERROR: Round {} invalid value: {}".format(self.name, err))
            sys.exit(1)
        except KeyError as err:
            print("ERROR: Round {} missing field: {}".format(self.name, err))
            sys.exit(1)

        if self.name is None:
            self.name = get_random_name()

        if "bpm" not in config:
            print("WARNING: Round {}, bpm not set, default 120".format(
                self.name))

        if "speed" not in config:
            print("WARNING: Round {}, speed not set, default 3".format(
                self.name))

    def load_beatmeter_config(self, config: dict):
        current_folder = os.path.abspath(os.getcwd())
        bmcfg_filepath = config["bmcfg"]
        bmcfg_folder = os.path.abspath(os.path.dirname(bmcfg_filepath))
        bmcfg_filename = os.path.basename(bmcfg_filepath)
        config["bmcfg"] = str(os.path.join(bmcfg_folder, bmcfg_filename))
        os.chdir(bmcfg_folder)
        with open(bmcfg_filename) as bmcfg_json:
            beatmeter_config = BeatMeterConfig(json.load(bmcfg_json))
        os.chdir(current_folder)
        self.beatmeter_config = beatmeter_config
        config["music"] = beatmeter_config.music
        config["bpm"] = beatmeter_config.bpm
        config["duration"] = beatmeter_config.duration

        if "beats" not in config:
            config["beats"] = str(os.path.join(bmcfg_folder, "beat_track.wav"))
        if "beatmeter" not in config:
            config["beatmeter"] = str(os.path.join(bmcfg_folder, "beats"))

    def validate(self):
        for item, validation in self.ITEMS.items():
            data = self.__getattribute__(item)
            _validate(item, data, validation)

        for src in self.sources:
            if not os.path.isfile(src):
                raise ValueError("source file {} does not exist".format(src))
        if (self.beatmeter and
            (not os.path.isdir(self.beatmeter)
             or os.listdir(self.beatmeter) == [])):
            raise ValueError(
                "beatmeter folder {} does not exist or is empty".format(
                    self.beatmeter))
        if self.beats and not os.path.isfile(self.beats):
            raise ValueError("beats file {} does not exist".format(self.beats))
        if self.music and not os.path.isfile(self.music):
            raise ValueError("music file {} does not exist".format(self.music))
        if self.bmcfg and not os.path.isfile(self.bmcfg):
            raise ValueError("bmcfg file {} does not exist".format(self.bmcfg))
        if self.bmcfg:
            self.beatmeter_config.validate()

    def copy(self):
        attributes = self.ITEMS.copy()
        attributes.update(self.__dict__)
        return RoundConfig(attributes)


class OutputConfig:
    # pylint: disable=no-member, access-member-before-definition
    ITEMS = {
        "name": {
            "type": str,
            "default": None,
            "help": "base file name and title of video",
        },
        "fps": {
            "type": float,
            "min": 1,
            "max": 360,
            "default": DEFAULT_FPS,
            "help": "output frames per second"
        },
        "xdim": {
            "type": int,
            "min": 1,
            "max": 10000,
            "default": 1920,
            "help": "output width (x pixels)"
        },
        "ydim": {
            "type": int,
            "min": 1,
            "max": 10000,
            "default": 1080,
            "help": "output height (y pixels)"
        },
        "versions": {
            "type": int,
            "min": 1,
            "max": 36,
            "default": 1,
            "help": "number of versions"
        },
        "cache": {
            "type": str,
            "choices": ["all", "round"],
            "default": "round",
            "help": "memory usage before dumping to disk"
        },
        "threads": {
            "type": int,
            "min": 1,
            "max": 8,
            "default": 1,
            "help": "number of active round workers on CPU"
        },
        "assemble": {
            "type": bool,
            "default": False,
            "help": "combine rounds, add title and credits"
        },
        "raw": {
            "type": bool,
            "default": False,
            "help": "save output losslessly"
        },
        "delete": {
            "type": bool,
            "default": False,
            "help": "delete intermediate files after assembly"
        },
        "_settings": {
            "type": str,
            "default": "",
            "help": "override command-line options with a yaml file",
            "exts": [("YAML files", "*.yaml")]
        },
        "rounds": {
            "type": list,
            "default": [],
            "help": "round configuration yaml files"
        },
    }

    def __init__(self, args, load=True):
        if type(args) != dict:
            args = args.__dict__

        current_folder = os.path.abspath(os.getcwd())
        settings_filepath = args["_settings"]
        if settings_filepath != "" and load:
            if not os.path.exists(settings_filepath):
                print("Settings file ({}) not found".format(
                    settings_filepath
                ))
                sys.exit(1)
            os.chdir(os.path.abspath(os.path.dirname(settings_filepath)))
            settings_filename = os.path.basename(settings_filepath)
            with open(settings_filename) as settings_filehandle:
                file_contents = yaml.full_load(settings_filehandle)
        else:
            file_contents = dict()

        if type(file_contents) == OutputConfig:
            self.__dict__.update(file_contents.__dict__)
        else:
            for attribute, validation in self.ITEMS.items():
                value = file_contents.get(attribute, validation["default"])
                args_value = args.get(attribute, value)
                if args_value != validation["default"]:
                    value = args_value  # overwrite settings with cmd args
                value = None if value is None else validation["type"](value)
                if attribute == "rounds":
                    for r_i, r in enumerate(value):
                        if type(r) == str or type(r) == dict:
                            value[r_i] = RoundConfig(r, True)
                        elif type(r) == RoundConfig:
                            value[r_i] = r
                        else:
                            print("ERROR: Settings invalid round: {}".format(
                                repr(r)
                            ))
                            sys.exit(1)
                self.__setattr__(attribute, value)
            if self.name is None:
                self.name = get_random_name()
        os.chdir(current_folder)
        try:
            self.validate()
        except ValueError as err:
            print("ERROR: Settings invalid value: {}".format(err))
            sys.exit(1)
        except KeyError as err:
            print("ERROR: Settings missing field: {}".format(err))
            sys.exit(1)

    def validate(self):
        for item, validation in self.ITEMS.items():
            data = self.__getattribute__(item)
            _validate(item, data, validation)

        if self.delete and not self.assemble:
            print("Cannot delete intermediate files; not assembling video")
            self.delete = False

        if self.delete and self.cache == "all":
            print("Cannot delete intermediate files; none will be created")
            self.delete = False

        for r in self.rounds:
            if r.name in [r2.name for r2 in self.rounds if r2 is not r]:
                raise ValueError("round names must be unique: " + r.name)

    def save(self):
        with open(self._settings, "w") as settings_filehandle:
            yaml.dump(self, settings_filehandle, sort_keys=False)

    def copy(self):
        attributes = self.ITEMS.copy()
        attributes.update(self.__dict__)
        return OutputConfig(attributes, False)


def _validate(item: str, data, validation: dict):
    if data is None:
        return
    if type(data) != validation["type"]:
        raise ValueError("wrong data type for {} ({}); must be {}".format(
            item, data, validation["type"]))
    elif type(data) in [int, float]:
        if data > validation["max"]:
            raise ValueError(
                "greater than maximum for {} ({}); must be <= {}".format(
                    item, data, validation["max"]))
        elif data < validation["min"]:
            raise ValueError(
                "less than minimum for {} ({}); must be >= {}".format(
                    item, data, validation["max"]))
    elif type(data) == str:
        choices = validation.get("choices", [])
        if choices != [] and data not in choices:
            raise ValueError(
                "invalid choice for {} ({}); must be one of [{}]".format(
                    item, data, ", ".join(choices)))
    elif item == "rounds":
        for i, d in enumerate(data):
            try:
                d.validate()
            except ValueError as err:
                print("ERROR: Round {} invalid value: {}".format(i + 1, err))
                sys.exit(1)
            except KeyError as err:
                print("ERROR: Round {} missing field: {}".format(i + 1, err))
                sys.exit(1)
    elif item == "credits":
        data.validate()


def parse_command_line_args() -> dict:
    parser = argparse.ArgumentParser()
    for attribute, validation in OutputConfig.ITEMS.items():
        if attribute == "rounds":
            continue
        short_name = "-" + (attribute[1]
                            if attribute == "_settings"
                            else attribute[0])
        name = "--" + attribute
        _help = validation["help"]
        _type = validation["type"]
        default = validation["default"]
        action = "store_true" if _type is bool else "store"
        parser.add_argument(short_name, name, help=_help,
                            action=action, default=default)

    parser.add_argument(
        "-e", "--execute",
        help="Execute directly, without GUI.",
        action="store_true",
        default=False)

    parser.add_argument(
        "rounds",
        metavar="<ROUND_NAME>_config.yaml",
        help=OutputConfig.ITEMS["rounds"]["help"],
        nargs='*',
        default=OutputConfig.ITEMS["rounds"]["default"])

    return parser.parse_args()
