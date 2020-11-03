import os
import yaml
import argparse
import random

from string import ascii_letters

from credit import RoundCredits


def get_random_name():
    return "Random {}".format("".join([
        random.choice(ascii_letters)
        for _ in range(4)
    ]))


class OutputConfig:
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
            "default": 30,
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
        "cache": {
            "type": str,
            "choices": ["all", "round"],
            "default": "round",
            "help": "memory usage before dumping to disk"
        },
        "_settings": {
            "type": str,
            "default": "",
            "help": "override and provide command-line options",
            "exts": [("YAML files", "*.yaml")]
        },
        "rounds": {
            "type": list,
            "default": [],
            "help": "rounds"
        },
    }

    def __init__(self, args, load=True):
        if type(args) != dict:
            args = args.__dict__

        if args["_settings"] != "" and load:
            with open(args["_settings"]) as settings_file:
                file_contents = yaml.full_load(settings_file)
        else:
            file_contents = dict()

        if type(file_contents) == OutputConfig:
            self.__dict__.update(file_contents.__dict__)
        else:
            rounds = args["rounds"] if "rounds" in args else []
            rounds = [RoundConfig(r) if type(r) == dict else r
                      for r in file_contents.get("rounds", rounds)]
            file_contents["rounds"] = rounds
            for attribute, validation in self.ITEMS.items():
                if attribute != "rounds":
                    args_value = args.get(attribute, validation["default"])
                    value = file_contents.get(attribute, args_value)
                else:
                    value = file_contents["rounds"]
                value = None if value is None else validation["type"](value)
                self.__setattr__(attribute, value)
            if self.name is None:
                self.name = get_random_name()
        try:
            self.validate()
        except ValueError as err:
            print("ERROR: Settings invalid value: {}".format(err))
            exit(1)
        except KeyError as err:
            print("ERROR: Settings missing field: {}".format(err))
            exit(1)

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
        with open(self._settings, "w") as settings_file:
            yaml.dump(self, settings_file, sort_keys=False)

    def copy(self):
        attributes = self.ITEMS.copy()
        attributes.update(self.__dict__)
        return OutputConfig(attributes, False)


class RoundConfig:
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

    def __init__(self, config: dict, load=False):
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
            exit(1)
        except KeyError as err:
            print("ERROR: Round {} missing field: {}".format(self.name, err))
            exit(1)

        if self.name is None:
            self.name = get_random_name()

        if "bpm" not in config:
            print("WARNING: Round {}, bpm not set, default 120".format(self.name))

        if "speed" not in config:
            print("WARNING: Round {}, speed not set, default 3".format(self.name))

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

    def copy(self):
        attributes = self.ITEMS.copy()
        attributes.update(self.__dict__)
        return RoundConfig(attributes)


def _validate(item: str, data, validation: dict):
    if data == None:
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
                exit(1)
            except KeyError as err:
                print("ERROR: Round {} missing field: {}".format(i + 1, err))
                exit(1)
    elif item == "credits":
        # TODO: add validation
        x = data.audio
        y = data.video
        print("Validate ME: ", x, y)


def parse_command_line_args() -> dict:
    parser = argparse.ArgumentParser()
    for attribute, validation in OutputConfig.ITEMS.items():
        if attribute in ["_settings", "rounds"]:
            continue
        short_name = "-" + attribute[0]
        name = "--" + attribute
        _help = validation["help"]
        _type = validation["type"]
        default = validation["default"]
        action = "store_true" if _type is bool else "store"
        parser.add_argument(short_name, name, help=_help,
                            action=action, default=default)

    parser.add_argument(
        "_settings",
        metavar="<YOUR_VIDEO_NAME>_config.yaml",
        help="settings file",
        nargs='?', 
        default=OutputConfig.ITEMS["_settings"]["default"])

    return parser.parse_args()
