import os
import yaml
import argparse
import random

from string import ascii_letters

from credit import RoundCredits

class OutputConfig:
    def __init__(self, args):

        if args.settings is not None:
            with open(args.settings) as settings_file:
                file_contents = yaml.full_load(settings_file)
        else:
            file_contents = dict()

        self.output = file_contents.get("output", args.output)
        self.assemble = file_contents.get("assemble", args.assemble)
        self.fps = file_contents.get("fps", args.fps)
        self.xdim = file_contents.get("xdim", args.xdim)
        self.ydim = file_contents.get("ydim", args.ydim)
        self.versions = file_contents.get("versions", args.versions)
        self.raw = file_contents.get("raw", args.raw)
        self.cache = file_contents.get("cache", args.cache)
        self.delete = file_contents.get("delete", args.delete)

        if self.delete and not self.assemble:
            print("Cannot delete intermediate files; not assembling video")
            self.delete = False

        if self.delete and self.cache == "all":
            print("Cannot delete intermediate files; none will be created")
            self.delete = False


class RoundConfig:
    def __init__(self, config: dict, f_name: str):
        self.name = config.get("name", None)
        self.filename = f_name.rstrip(".yaml")
        self.is_on_disk = False
        self.bpm = config.get("bpm", 120)
        if "bpm" not in config:
            print("WARNING: Round {}, bpm not set, default 120".format(f_name))
        self.duration = config["duration"]
        if self.duration <= 0 or self.duration > 3600:
            raise ValueError("duration must be between 1 and 3600 seconds")
        self.speed = config.get("speed", 3)
        if "speed" not in config:
            print("WARNING: Round {}, speed not set, default 3".format(f_name))
        if self.speed not in range(1, 6):
            raise ValueError("speed must be integer between 1 and 5")
        self.sources = config["sources"]
        for src in self.sources:
            if not os.path.isfile(src):
                raise ValueError("source file {} does not exist".format(src))
        self.beats = config.get("beats", None)
        if self.beats and not os.path.isfile(self.beats):
            raise ValueError("beats file {} does not exist".format(self.beats))
        self.beatmeter = config.get("beatmeter", None)
        if (self.beatmeter and
            (not os.path.isdir(self.beatmeter)
             or os.listdir(self.beatmeter) == [])):
            raise ValueError(
                "beatmeter folder {} does not exist or is empty".format(
                    self.beatmeter))
        self.music = config.get("music", None)
        if self.music and not os.path.isfile(self.music):
            raise ValueError("music file {} does not exist".format(self.music))
        self.credits = RoundCredits(config.get("credits", None))
        self.background = config.get("background", None)

        try:
            self.audio_level = float(config.get("audio_level", 0))
        except ValueError:
            raise ValueError("audio_level must be a float")
        if self.audio_level < 0:
            raise ValueError("audio_level must be positive")


def parse_rounds(round_filenames: [str]) -> [RoundConfig]:
    round_configs = []
    for rnd in round_filenames:
        with open(rnd) as round_yaml:
            try:
                config_dict = yaml.full_load(round_yaml)
                round_configs.append(RoundConfig(config_dict, rnd))
            except ValueError as err:
                print("ERROR: Round {} invalid value: {}".format(rnd, err))
                exit(1)
            except KeyError as err:
                print("ERROR: Round {} missing field: {}".format(rnd, err))
                exit(1)
    return round_configs


def parse_command_line_args() -> dict:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-x", "--xdim", help="output width (x pixels)", type=int, default=1920)
    parser.add_argument(
        "-y", "--ydim", help="output height (y pixels)", type=int, default=1080)
    parser.add_argument(
        "-f", "--fps", help="output frames per second", type=int, default=30)
    parser.add_argument(
        "-o", "--output", help="output base file name and title of video",
        default="Random {}".format("".join([
            random.choice(ascii_letters)
            for _ in range(4)
        ])))
    parser.add_argument(
        "-v", "--versions", help="number of versions", type=int, default=1)
    parser.add_argument(
        "-r", "--raw", help="save output losslessly", type=bool, default=False)
    parser.add_argument("-a", "--assemble", action="store_true",
                        help="combine rounds, add title and credits",
                        default=False)
    parser.add_argument("-c", "--cache",  # TODO: add "clip" choice
                        help="memory usage before dumping to disk",
                        choices=["round", "all"], default="round")
    parser.add_argument("-d", "--delete", action="store_true",
                        help="delete intermediate files after assembly",
                        default=False)
    parser.add_argument("-s", "--settings",
                        help="override and provide command-line options",
                        default=None)
    parser.add_argument(
        "rounds", metavar="rnd.yaml", nargs="+", help="round config files")
    return parser.parse_args()
