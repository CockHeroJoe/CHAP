import os
import random
import fnmatch
from contextlib import ExitStack, AbstractContextManager
from threading import Thread

from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.audio.fx.volumex import volumex
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.resize import resize
from moviepy.video.VideoClip import ColorClip, ImageClip, TextClip, VideoClip

from constants import TRANSITION_DURATION, CREDIT_DISPLAY_TIME
from cutters import Interleaver, Skipper, Randomizer
from credit import make_credits
from utils import SourceFile,\
    get_black_clip,\
    get_round_name,\
    make_text_screen,\
    make_background,\
    crossfade
from parsing import OutputConfig, RoundConfig

PRESET = "fast"


class StackList(AbstractContextManager):
    def __init__(self, num_rounds: int):
        self._stacks = [ExitStack() for _ in range(num_rounds)]

    def __exit__(self, *args, **kwargs):
        for stack in self._stacks:
            try:
                stack.close()
            except Exception as e:
                print("Error closing stack: " + str(e))

    def __getitem__(self, index: int):
        return self._stacks[index]


class ThreadWithReturnValue(Thread):
    def __init__(self, group=None, target=None, name=None, daemon=False,
                 args=(), kwargs={}, Verbose=None):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self._return = None

    def run(self):
        try:
            if self._target:
                self._return = self._target(*self._args, **self._kwargs)
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs

    def join(self, *args):
        Thread.join(self, *args)
        return self._return


def make(output_config: OutputConfig):
    ext = "avi" if output_config.raw else "mp4"
    codec = "png" if output_config.raw else None
    output_name = output_config.name

    threads = []
    max_threads = output_config.threads

    if output_config.rounds == []:
        print("ERROR: No round configs provided")
        exit(1)

    round_configs = output_config.rounds
    for round_config in round_configs:
        name = get_round_name(output_name, round_config.name, ext)
        if os.path.isfile(name):
            round_config._is_on_disk = True
            print("Reloaded round {} from disk".format(name))

    # shuffle clips for each round and attach beatmeter
    with StackList(len(round_configs)) as stacks:
        round_videos = []
        for r_i, round_config in enumerate(round_configs):
            stack = stacks[r_i]

            # Skip rounds that have been saved
            if round_config._is_on_disk:
                continue

            # Assemble beatmeter video from beat images
            bmcfg = (round_config.beatmeter_config
                     if round_config.bmcfg else None)
            if round_config.beatmeter is not None:

                def make_beatmeter():
                    beatmeter = stack.enter_context(ImageSequenceClip(
                        round_config.beatmeter,
                        fps=bmcfg.fps if bmcfg else output_config.fps
                    ))
                    # resize and fit beatmeter
                    new_height = (beatmeter.h * output_config.xdim
                                  / beatmeter.w)  # pylint: disable=no-member
                    beatmeter = resize(
                        beatmeter, (output_config.xdim, new_height))
                    beatmeter = beatmeter.set_position(
                        ("center", output_config.ydim - 20 - beatmeter.h)
                    )
                    return beatmeter

                beatmeter_thread = ThreadWithReturnValue(
                    target=make_beatmeter, daemon=True)
                print("assembling beatmeter #{}...".format(r_i + 1))
                beatmeter_thread.start()

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

            # Generate interleaved clips from sources
            print("loading sources for round #{}...".format(r_i + 1))
            sources = [SourceFile(stack.enter_context(VideoFileClip(s)))
                       for s in round_config.sources]
            print("shuffling input videos for round #{}...".format(r_i + 1))

            # Get list of clips cut from sources using chosen cutter
            Cutter = {
                "skip": Skipper,
                "interleave": Interleaver,
                "randomize": Randomizer,
            }[round_config.cut]
            cutter = Cutter(output_config, round_config, bmcfg, sources)
            clips = cutter.get_compilation()

            # Concatenate this round's video clips together and add beatmeter
            round_i = concatenate_videoclips(clips)

            if round_config.beatmeter is not None:
                beatmeter = beatmeter_thread.join()
                round_i = CompositeVideoClip([round_i, beatmeter])
            if audio is not None:
                beat_audio = CompositeAudioClip(audio)
                level = round_config.audio_level
                if level > 1:
                    beat_audio = volumex(beat_audio, 1 / level)
                else:
                    round_i = volumex(round_i, level)
                audio = CompositeAudioClip([beat_audio, round_i.audio])
                round_i = round_i.set_audio(audio)
            round_i = round_i.set_duration(round_config.duration)

            if output_config.cache == "round":
                name = get_round_name(output_name, round_config.name, ext)

                def save_round():
                    round_i.write_videofile(
                        name,
                        codec=codec,
                        fps=output_config.fps,
                        preset=PRESET,
                    )
                    stack.close()

                round_config._is_on_disk = True  # TODO: test this
                thread = Thread(target=save_round, daemon=True)
                threads.append(thread)
                thread.start()

                if len(threads) >= max_threads:
                    first, threads = threads[0], threads[1:]
                    print("Waiting for round #{} to finish writing...".format(
                        r_i - max_threads + 2
                    ))
                    first.join()
            else:
                round_videos.append(round_i)

        for thread in threads:
            thread.join()

        if output_config.assemble:
            # Reload rounds from output files, if not still in memory
            rounds = [
                stacks[r_i].enter_context(VideoFileClip(
                    get_round_name(output_name, round_config.name, ext)))
                if round_config._is_on_disk else round_videos.pop()
                for r_i, round_config in enumerate(round_configs)
            ]

            # Add round transitions
            dims = (output_config.xdim, output_config.ydim)
            round_transitions = [
                make_text_screen(dims,
                                 "Round {}".format(r_i + 1) +
                                 ("\n" + round_config.name
                                  if round_config.name is not None else ""),
                                 TRANSITION_DURATION,
                                 make_background(stacks[r_i],
                                                 round_config.background,
                                                 dims,
                                                 TRANSITION_DURATION))
                for r_i, round_config in enumerate(round_configs)
            ]
            all_video = [None]*(3 * len(rounds))
            all_video[::3] = [get_black_clip(dims) for _ in range(len(rounds))]
            all_video[1::3] = round_transitions
            all_video[2::3] = rounds

            # Add title
            title_text = "Cock Hero\n"
            # TODO: add output_config.title_duration
            #       and add output_config.title_background
            #       and round_config.transition_duration
            #       and modify background => round_config.transition_background
            # TODO: test backgrounds, add help in README
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
            output.write_videofile(
                name,
                codec=codec,
                fps=output_config.fps,
                preset=PRESET,
            )

            # Delete intermediate files
            if output_config.delete:
                for round_config in round_configs:
                    if round_config._is_on_disk:
                        os.remove(get_round_name(
                            output_name, round_config.name, ext))
