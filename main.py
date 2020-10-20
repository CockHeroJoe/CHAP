#! /usr/bin/env python3

import os
import random
import fnmatch

from contextlib import ExitStack
from moviepy.editor import concatenate_videoclips,\
    AudioFileClip,\
    ColorClip,\
    CompositeAudioClip,\
    CompositeVideoClip,\
    ImageClip,\
    ImageSequenceClip,\
    TextClip,\
    VideoClip,\
    VideoFileClip

from constants import TRANSITION_DURATION, CREDIT_DISPLAY_TIME
from interleave import interleave
from credit import make_credits
from utils import SourceFile,\
    get_black_clip,\
    get_round_name,\
    make_text_screen,\
    make_background,\
    crossfade
from parsing import OutputConfig,\
    RoundConfig,\
    parse_rounds,\
    parse_command_line_args


def main():
    output_config = OutputConfig(parse_command_line_args())
    ext = "avi" if output_config.raw else "mp4"
    codec = "png" if output_config.raw else None
    output_name = output_config.output

    if output_config.rounds == []:
        print("ERROR: No round configs provided")
        exit(1)

    round_configs = parse_rounds(output_config.rounds)
    for round_config in round_configs:
        name = get_round_name(output_name, round_config.filename, ext)
        if os.path.isfile(name):
            round_config.is_on_disk = True
            print("Reloaded round {} from disk".format(name))

    # shuffle clips for each round and attach beatmeter
    with ExitStack() as stack:
        round_videos = []
        for r_i, round_config in enumerate(round_configs):
            
            # Skip rounds that have been saved
            if round_config.is_on_disk:
                continue

            # Assemble beatmeter video from beat images
            beatmeter = None
            if round_config.beatmeter is not None:
                print("assembling beatmeter #{}...".format(r_i + 1))
                beatmeter = stack.enter_context(ImageSequenceClip(
                    round_config.beatmeter,
                    fps=output_config.fps
                ))
                # resize and fit beatmeter
                new_height = beatmeter.h * output_config.xdim / beatmeter.w
                beatmeter = beatmeter.resize((output_config.xdim, new_height))
                beatmeter = beatmeter.set_position(
                    ("center", output_config.ydim - 20 - beatmeter.h)
                )

            # Assemble audio from music and beats
            audio = None
            if round_config.music is not None or round_config.beats is not None:
                audio = [
                    stack.enter_context(AudioFileClip(clip))
                    for clip in [
                        round_config.beats,
                        round_config.music,
                    ]
                    if clip is not None
                ]

            # TODO: get duration, bpm from music track; generate beats & meter
            # TODO: OR use sklave Beatmeter Generator's json

            # Generate interleaved clips from sources
            print("loading sources for round #{}...".format(r_i + 1))
            sources = [SourceFile(stack.enter_context(VideoFileClip(s)))
                       for s in round_config.sources]
            print("shuffling input videos for round #{}...".format(r_i + 1))
            shuffled_clips = interleave(output_config, round_config, sources)

            # Concatenate this round's video clips together and add beatmeter
            round_i = concatenate_videoclips(shuffled_clips)
            if beatmeter is not None:
                round_i = CompositeVideoClip([round_i, beatmeter])
            if audio is not None:
                beat_audio = CompositeAudioClip(audio)
                level = round_config.audio_level
                if level > 1:
                    beat_audio.volumex(1 / level)
                else:
                    round_i.volumex(level)
                audio = CompositeAudioClip([beat_audio, round_i.audio])
                round_i = round_i.set_audio(audio)
            round_i = round_i.set_duration(round_config.duration)

            if output_config.cache == "round":
                name = get_round_name(output_name, round_config.filename, ext)
                round_i.write_videofile(name, codec=codec)
                round_config.is_on_disk = True
                stack.close()
            else:
                round_videos.append(round_i)

        if output_config.assemble:
            # Reload rounds from output files
            rounds = [
                stack.enter_context(VideoFileClip(
                    get_round_name(output_name, round_config.filename, ext)))
                if round_config.is_on_disk else round_videos.pop()
                for round_config in round_configs
            ]

            # Add round transitons
            dims = (output_config.xdim, output_config.ydim)
            round_transitions = [
                make_text_screen(dims,
                                 "Round {}".format(r_i + 1) +
                                 ("\n" + round_config.name
                                  if round_config.name is not None
                                  else ""),
                                 TRANSITION_DURATION,
                                 make_background(stack,
                                                 round_config.background,
                                                 dims)  # TODO: test background
                                 )
                for r_i, round_config in enumerate(round_configs)
            ]
            all_video = [None]*(3 * len(rounds))
            all_video[::3] = [get_black_clip(dims) for _ in range(len(rounds))]
            all_video[1::3] = round_transitions
            all_video[2::3] = rounds

            # Add title
            title_text = "Cock Hero\n"
            title = make_text_screen(dims, title_text, TRANSITION_DURATION)
            title_text += output_name
            title2 = make_text_screen(dims, title_text, TRANSITION_DURATION)
            all_video = [title, title2] + all_video

            # Add credits
            credits_data_list = [
                r.credits for r in round_configs
                if r.credits is not None
                and (r.credits.audio is not [] or r.credits.video is not [])
            ]
            if credits_data_list is not []:
                credits_video = make_credits(
                    credits_data_list, 0.70 * dims[0], stroke_color=None, gap=30)
                lines_per_second = dims[1] / CREDIT_DISPLAY_TIME
                def scroll(t): return ("center", -lines_per_second * t)
                credits_video = credits_video.set_position(scroll)
                credits_duration = credits_video.h / lines_per_second
                credits_video = credits_video.set_duration(credits_duration)
                all_video += [get_black_clip(dims), credits_video]

            # Output final video
            output = crossfade(all_video)
            name = "{}.{}".format(output_name, ext)
            output.write_videofile(name, codec=codec, fps=output_config.fps)

            # Delete intermediate files
            if output_config.delete:
                for round_config in round_configs:
                    if round_config.is_on_disk:
                        os.remove(get_round_name(
                            output_name, round_config.filename, ext))


if __name__ == "__main__":
    main()
