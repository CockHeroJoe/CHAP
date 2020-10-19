import os
import yaml


class AudioCredit:
    def __init__(self, config: dict):
        self.artist = config.get("artist", None)
        self.song = config.get("song", None)

    def __str__(self):
        fields = [
            f for f in [
                self.artist,
                self.song,
            ] if f is not None
        ]
        return ("{}\n" * len(fields)).format(*fields)


class VideoCredit:
    def __init__(self, config: dict):
        self.studio = config.get("studio", None)
        self.title = config.get("title", None)
        self.date = config.get("date", None)
        self.performers = config.get("performers", None)

    def __str__(self):
        fields = [
            f for f in [
                self.studio,
                self.date,
                self.title,
                *self.performers
            ] if f is not None
        ]
        return ("{}\n" * (len(fields))).format(*fields)


class RoundCredits:
    def __init__(self, config: dict):
        self.audio = [AudioCredit(c) for c in config.get("audio", [])]
        self.video = [VideoCredit(c) for c in config.get("video", [])]


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
