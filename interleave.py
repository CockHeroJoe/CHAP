import random
import pygame as pg

from moviepy.editor import VideoFileClip

from utils import draw_progress_bar
from parsing import RoundConfig, OutputConfig
from preview import preview, preview_all

def interleave(
        output_config: OutputConfig,
        round_config: RoundConfig,
        sources: [VideoFileClip]):
    versions = output_config.versions
    clips = []
    accum_length = 0
    max_multiple = 32 - round_config.speed ** 2
    min_multiple = 21 - round_config.speed * 4
    seconds_per_beat = 60 / round_config.bpm
    per_input_length = round_config.duration / len(round_config.sources)

    # Cut randomized clips from random videos in chronological order
    while accum_length < round_config.duration:
        # Select a random clip length that is a whole multiple of beats long
        curr_min_multiple = int(
            (1 - 0.66 * accum_length / round_config.duration) * min_multiple)
        curr_max_multiple = int(
            (1 - 0.66 * accum_length / round_config.duration) * max_multiple)
        length = max(4, 4 * seconds_per_beat *
                     round(random.randrange(curr_min_multiple, curr_max_multiple) / 4))

        # Cut multiple clips from various sources
        out_clips = []
        for _ in [chr(a + 97) for a in range(versions)]:
            # Get random file from list
            i = -1
            counter = 0
            while i == -1:
                i = random.randrange(0, len(sources))
                if sources[i].start + length > sources[i].clip.duration:
                    i = -1
                    counter += 1
                if counter >= 1000:
                    print("Warning: not enough source material (or buggy code)")
                    for src in sources:
                        src.start /= 2
            clip = sources[i].clip
            start = sources[i].start

            # Cut a subclip
            out_clip = clip.subclip(start, start + length).resize(
                (output_config.xdim, output_config.ydim)
            )
            out_clips.append(out_clip)

            # Advance all clips by simlar percentage of total duration
            for c in range(len(sources)):
                clip_c = sources[c].clip
                time_remaining_c = clip_c.duration - sources[c].start
                skip_length = length * (clip_c.duration / per_input_length - 1)
                skip_length /= len(sources) * versions
                time_required = round_config.duration - accum_length
                time_required -= length if c == i else 0
                max_skip = (time_remaining_c - time_required)
                max_skip /= versions
                random_skip = min(random.gauss(skip_length, length), max_skip)
                sources[c].start += max(0, random_skip)
                sources[c].start += length if c == i else 0

        # Select from versions using GUI editor
        if versions > 1:
            try:
                chosen = preview_all(out_clips)
            except InterruptedError as err:
                print("\r{}".format(err))
                versions = 1
                chosen = 0
            clips.append(out_clips[chosen])
        else:
            clips.append(out_clip)

        accum_length += length
        draw_progress_bar(min(1, accum_length / round_config.duration), 80)
    print("\nDone!")

    return clips
