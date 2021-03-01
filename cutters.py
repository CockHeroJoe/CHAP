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
        while current_time < duration:
            # Select a random clip length that is a whole multiple of beats long
            if self.bmcfg and len(sections) > 1:
                # Use beatmeter generator config to time cuts to beats perfectly
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
                    # Last cut in round is extended to match duration of Base track
                    length += duration - sections[-1].stop
                elif subsection_index == num_subsections - 1:
                    # Last cut per section is adjusted to account for drift due to
                    # imperfect beat timings given in beatmeter config
                    length = sections[section_index+1].start - current_time
                subsection_index += 1
            else:
                # Simple accelerating cuts if beatmeter config is not provided
                current_min_multiple = int(
                    (1 - 0.66 * current_time / duration) * min_multiple)
                current_max_multiple = int(
                    (1 - 0.66 * current_time / duration) * max_multiple)
                length = seconds_per_beat * max(4, round(
                    random.randrange(current_min_multiple, current_max_multiple)))

            # Cut multiple clips from various sources
            out_clips = []
            for _ in [chr(a + 97) for a in range(self.output_config.versions)]:
                # Get the next clip source
                i = self.get_source_clip_index(length)
                clip = self.sources[i].clip
                start = self.sources[i].start

                # Cut a subclip
                out_clip = resize(clip.subclip(start, start + length),
                                  (self.output_config.xdim,
                                   self.output_config.ydim))
                out_clips.append(out_clip)

                # Advance all clips by simlar percentage of total duration
                self.advance_sources(length, current_time, i)

            self.choose_version(out_clips)
            clips.append(out_clips[self._chosen or 0])

            current_time += length
            draw_progress_bar(
                min(1, current_time / duration), 80)
        print("\nDone!")

        return clips

    @abstractmethod
    def advance_sources(self, length: float, current_time: float, i: int):
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
                print("Warning: not enough source material (or buggy code)")
                for src in self.sources:
                    src.start /= 2
        return i


class Interleaver(_AbstractRandomSelector):
    def advance_sources(self, length: float, current_time: float, i: int):
        for c in range(len(self.sources)):
            clip_c = self.sources[c].clip
            time_remaining = clip_c.duration - self.sources[c].start
            skip_length = length * (clip_c.duration /
                                    self.per_input_length - 1)
            skip_length /= len(self.sources)
            skip_length /= self.output_config.versions
            time_required = self.round_config.duration - current_time
            time_required -= length if c == i else 0
            max_skip = (time_remaining - time_required)
            max_skip /= self.output_config.versions
            random_skip = min(random.gauss(
                skip_length, length), max_skip)
            self.sources[c].start += max(0, random_skip)
            self.sources[c].start += length if c == i else 0


class Randomizer(_AbstractRandomSelector):
    def advance_sources(self, length: float, current_time: float, i: int):
        for source in self.sources:
            source.start = random.uniform(
                SourceFile.get_random_start(),
                source.clip.duration - length * 2)


class Skipper(_AbstractCutter):

    def get_source_clip_index(self, length: float) -> int:
        for i, source in enumerate(self.sources):
            if source.start + length <= source.clip.duration:
                return i

        print("Warning: not enough source material (or buggy code)")
        for source in self.sources:
            source.start /= 2
        return self.get_source_clip_index(length)

    def advance_sources(self, length: float, current_time: float, i: int):
        source = self.sources[i]
        length_fraction = source.clip.duration / self.all_sources_length
        completed_fraction = (sum(
            map(lambda s: s.clip.duration, self.sources[:i]))
            / self.all_sources_length)
        current_progress = current_time / self.round_config.duration
        current_progress_in_source = ((current_progress - completed_fraction)
                                      / length_fraction)
        time_in_source = current_progress_in_source * source.clip.duration
        source.start = max(SourceFile.get_random_start(),
                           random.gauss(time_in_source,
                                        self.versions * length))
        """
        length_fraction = source.clip.duration / self.all_sources_length
        total_contribution = length_fraction * self.round_config.duration
        total_contribution *= self.versions
        assert total_contribution <= source.clip.duration
        skipped_amount = source.clip.duration - total_contribution
        num_cuts_expected = total_contribution / length
        expected_skip = skipped_amount / num_cuts_expected
        source.start += random.uniform(expected_skip / 2, expected_skip)
        """
