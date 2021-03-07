import random

from moviepy.Clip import Clip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.resize import resize

from utils import draw_progress_bar, SourceFile
from parsing import RoundConfig, OutputConfig, BeatMeterConfig
from preview import PreviewGUI
from tkinter import TclError
from abc import ABCMeta, abstractmethod


class _AbstractCutter(metaclass=ABCMeta):

    def __init__(
        self,
        output_config: OutputConfig,
        round_config: RoundConfig,
        beatmeter_config: BeatMeterConfig,
        sources: [VideoFileClip]
    ) -> [Clip]:
        self.versions = output_config.versions
        self.output_config = output_config
        self.round_config = round_config
        self.sources = sources
        self.bmcfg = beatmeter_config
        self.per_input_length = round_config.duration / len(sources)
        self.all_sources_length = sum(map(lambda s: s.clip.duration, sources))
        self._index = 0

    @abstractmethod
    def get_source_clip_index(self, length: float) -> int:
        pass

    def get_compilation(self):
        duration = self.round_config.duration
        clips = []
        max_multiple = 32 - self.round_config.speed ** 2
        min_multiple = 21 - self.round_config.speed * 4
        seconds_per_beat = 60 / self.round_config.bpm

        # Cut randomized clips from random videos in chronological order

        section_index = 0
        subsection_index = 0
        sections = self.bmcfg.sections
        current_time = 0.0
        frame_time = 1.0 / self.output_config.fps
        while duration - current_time > frame_time:
            # Select random clip length that is a whole multiple of beats long
            if self.bmcfg and len(sections) >= 1:
                # Use beatmeter generator config: time cuts to beats perfectly
                if subsection_index == 0:
                    # compute number of subsections in this pattern and length
                    section = sections[section_index]
                    next_section_start = (sections[section_index + 1].start
                                          if section_index + 1 < len(sections)
                                          else section.stop)
                    section_length = next_section_start - section.start
                    subsection_length = section.pattern_duration or (
                        4 * 60 / (section.bpm or self.round_config.bpm))
                    subsection_length *= 2 ** (3 - self.round_config.speed)
                    if subsection_length >= section_length:
                        subsection_length = section_length
                    num_subsections = round(section_length / subsection_length)
                elif subsection_index == num_subsections:
                    # Go to next beat pattern section
                    subsection_index = 0
                    section_index += 1
                    continue

                length = subsection_length
                if section_index == 0 and subsection_index == 0:
                    # First cut in round is longer, since beat hasn't started
                    length += sections[0].start
                elif (section_index == len(sections) - 1
                        and subsection_index == num_subsections - 1):
                    # Last cut in round extended to match Base track length
                    length = duration - current_time
                elif subsection_index == num_subsections - 1:
                    # Last cut per section is adjusted to account for drift
                    # due to imperfect beat timings given in beatmeter config
                    length = sections[section_index + 1].start - current_time
                subsection_index += 1
            else:
                # Simple accelerating cuts if beatmeter config is not provided
                current_min_multiple = int(
                    (1 - 0.66 * current_time / duration) * min_multiple)
                current_max_multiple = int(
                    (1 - 0.66 * current_time / duration) * max_multiple)
                length = seconds_per_beat * max(4, round(
                    random.randrange(current_min_multiple,
                                     current_max_multiple)))

            # Cut multiple clips from various sources
            out_clips = []
            for _ in range(self.versions):
                # Advance all clips by simlar percentage of total duration
                self.advance_sources(length, current_time)

                # Get the next clip source
                i = self.get_source_clip_index(length)
                clip = self.sources[i].clip
                start = self.sources[i].start

                # Cut a subclip
                out_clip = resize(clip.subclip(start, start + length),
                                  (self.output_config.xdim,
                                   self.output_config.ydim))
                out_clips.append(out_clip)

            self.choose_version(out_clips)
            clips.append(out_clips[self._chosen or 0])

            current_time += length

            # TODO: move progress into GUI
            if self.versions > 1:
                draw_progress_bar(min(1, current_time / duration), 80)
        if self.versions > 1:
            print("\nDone!")

        return clips

    @abstractmethod
    def advance_sources(self, length: float, current_time: float):
        pass

    def choose_version(self, clips) -> int:
        self._chosen = None
        if self.versions > 1:
            try:
                PreviewGUI(clips, self._choose).run()
            except TclError:
                pass
            if self._chosen is None:
                print("\r{}".format("Preview disabled: choices randomized"))
                self.versions = 1
        return self._chosen

    def _choose(self, version: int):
        self._chosen = version

    def _set_start(self, source: SourceFile, start: float, length: float):
        random_start = SourceFile.get_random_start()
        if source.clip.duration > 3 * random_start:
            min_start = random_start
        else:
            min_start = 0
        source.start = max(min_start, start)


class _AbstractRandomSelector(_AbstractCutter):
    def get_source_clip_index(self, length: float) -> int:
        i = -1
        counter = 0
        while i == -1:
            i = random.randrange(0, len(self.sources))
            if self.sources[i].start + length > self.sources[i].clip.duration:
                i = -1
                counter += 1
            if counter >= 1000:
                print("Warning: not enough source material")
                for src in self.sources:
                    src.start /= 2
        return i


class Interleaver(_AbstractRandomSelector):
    def advance_sources(self, length: float, current_time: float):
        for source in self.sources:
            current_progress = current_time / self.round_config.duration
            time_in_source = current_progress * source.clip.duration
            deviation = self.versions * length
            randomized_start = random.gauss(time_in_source, deviation)
            self._set_start(source, randomized_start, length)


class Randomizer(_AbstractRandomSelector):
    def advance_sources(self, length: float, current_time: float):
        for source in self.sources:
            max_start = source.clip.duration - length * 2
            randomized_start = random.uniform(0, max_start)
            self._set_start(source, randomized_start, length)


class Sequencer(_AbstractCutter):
    def get_source_clip_index(self, length: float) -> int:
        source = self.sources[self._index]
        if source.start + length >= source.clip.duration:
            print("Warning: not enough source material")
            source.start /= 2
            return self.get_source_clip_index(length)
        else:
            index = self._index
            self._index += 1
            self._index %= len(self.sources)
            return index

    def advance_sources(self, length: float, current_time: float):
        source = self.sources[self._index]
        current_progress = current_time / self.round_config.duration
        time_in_source = current_progress * source.clip.duration
        randomized_start = random.gauss(time_in_source, self.versions * length)
        self._set_start(source, randomized_start, length)


class Skipper(_AbstractCutter):
    def get_source_clip_index(self, length: float) -> int:
        source = self.sources[self._index]
        if source.start + length >= source.clip.duration:
            self._index += 1
        if self._index >= len(self.sources):
            print("Warning: not enough source material")
            for source in self.sources:
                source.start /= 2
            self._index = 0
        return self._index

    def advance_sources(self, length: float, current_time: float):
        source = self.sources[self._index]
        length_fraction = source.clip.duration / self.all_sources_length
        completed_fraction = sum(map(
            lambda s: s.clip.duration,
            self.sources[:self._index]))
        completed_fraction /= self.all_sources_length
        current_progress = current_time / self.round_config.duration
        current_progress_in_source = ((current_progress - completed_fraction)
                                      / length_fraction)
        time_in_source = current_progress_in_source * source.clip.duration
        randomized_start = random.gauss(time_in_source, self.versions * length)
        self._set_start(source, randomized_start, length)
