import math
import random
import pygame as pg

from moviepy.editor import clips_array, VideoFileClip

from constants import *
from utils import draw_progress_bar
from utils import OutputConfig
from round_parsing import RoundConfig
from preview import preview

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
            square_size = math.ceil(math.sqrt(versions))
            segments = [
                [
                    out_clips[i + j].resize(1 / square_size)
                    for j in range(square_size)
                    if i + j < len(out_clips)
                ] for i in range(0, len(out_clips), square_size)
            ]
            square = clips_array(segments).resize(DISPLAY_SIZE).without_audio()
            pg.display.set_caption("Choose which version to use")
            chosen = None
            while None == chosen:
                # Preview all versions
                result = preview(square, fps=output_config.fps / 10)

                # Check which version was chosen
                if result == None:
                    print("\rSwitching to single version for this round")
                    versions = 1
                    chosen = 0
                    pg.quit()
                    break
                elif type(result) == int:
                    chosen = result - 1
                else:
                    x = math.floor(result[0] / DISPLAY_SIZE[0] * square_size)
                    y = math.floor(result[1] / DISPLAY_SIZE[1] * square_size)
                    chosen = y * square_size + x
                if chosen < 0 or chosen >= len(out_clips):
                    print("Clip #{} not a valid clip in [1, {}]".format(
                        1 + chosen, len(out_clips)
                    ))
                    chosen = None
            clips.append(out_clips[chosen])
        else:
            clips.append(out_clip)

        accum_length += length
        draw_progress_bar(min(1, accum_length / round_config.duration), 80)
    print("\nDone!")

    return clips