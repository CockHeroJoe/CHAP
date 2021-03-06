import os
import sys
from contextlib import ExitStack, AbstractContextManager
from threading import Thread
import gc
from math import ceil

from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.audio.fx.volumex import volumex
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.resize import resize

from constants import TRANSITION_DURATION, FFMPEG_PRESET
from cutters import Interleaver, Skipper, Randomizer, Sequencer
from credit import make_credits
from utils import SourceFile,\
    get_black_clip,\
    get_round_name,\
    make_metadata_file,\
    make_text_screen,\
    make_background,\
    crossfade
from parsing import OutputConfig


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
    codec = "png" if output_config.raw else "mpeg4"
    output_name = output_config.name
    dims = (output_config.xdim, output_config.ydim)

    threads = []
    max_threads = output_config.threads

    if output_config.rounds == []:
        print("ERROR: No round configs provided")
        sys.exit(1)

    round_configs = output_config.rounds
    for round_config in round_configs:
        name = get_round_name(output_name, round_config.name, ext)
        if os.path.isfile(name):
            round_config._is_on_disk = True
            print("Reloaded round %s from disk" % name)

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
                    fps = bmcfg.fps if bmcfg else output_config.fps
                    beatmeter_folder = os.path.dirname(round_config.beatmeter)
                    beat_image_filenames = [
                        str(os.path.join(beatmeter_folder, filename))
                        for filename in sorted(os.listdir(
                            round_config.beatmeter)
                        )[:ceil(round_config.duration * fps)]
                    ]
                    beatmeter = stack.enter_context(ImageSequenceClip(
                        beat_image_filenames,
                        fps=fps
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
                print("Assembling beatmeter #{}...".format(r_i + 1))
                beatmeter_thread.start()

            # Assemble audio from music and beats
            audio = None
            if (round_config.music is not None
                    or round_config.beats is not None):
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
            print("Loading sources for round #{}...".format(r_i + 1))
            sources = [SourceFile(stack.enter_context(VideoFileClip(s)))
                       for s in round_config.sources]
            print("Shuffling input videos for round #{}...".format(r_i + 1))

            # Get list of clips cut from sources using chosen cutter
            Cutter = {
                "skip": Skipper,
                "interleave": Interleaver,
                "randomize": Randomizer,
                "sequence": Sequencer
            }[round_config.cut]
            cutter = Cutter(output_config, round_config, bmcfg, sources)
            clips = cutter.get_compilation()

            # Concatenate this round's video clips together and add beatmeter
            round_i = concatenate_videoclips(clips)
            if round_config.beatmeter is not None:
                print("Waiting for beatmeter #{}...".format(r_i + 1))
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
            round_i = crossfade([
                get_black_clip(dims),
                round_i,
                get_black_clip(dims),
            ])

            if output_config.cache == "round":
                # Save each round video to disk using a worker thread
                filename = get_round_name(output_name, round_config.name, ext)

                def save_round():  # Job for the worker thread
                    round_i.write_videofile(
                        filename,
                        codec=codec,
                        fps=output_config.fps,
                        preset=FFMPEG_PRESET,
                    )
                    stack.close()  # close all video files for this round

                round_config._is_on_disk = True
                thread = Thread(target=save_round, daemon=True)
                threads.append(thread)
                thread.start()

                # If too many threads are running, then
                if len(threads) >= max_threads:
                    # wait for first (thread that was started) to finish
                    first, threads = threads[0], threads[1:]
                    print("Waiting for round #{} to finish...".format(
                        r_i - max_threads + 2
                    ))
                    first.join()
            else:
                round_videos.append(round_i)  # Store round in memory instead

        print("All Rounds prepared")
        if threads != []:
            print("Waiting for all rounds to finish...")
        for thread in threads:
            thread.join()

        gc.collect()  # Free as much memory as possible

        # Add round transitions
        print("Assembling Round transitions...")
        round_transitions = [
            crossfade([
                get_black_clip(dims),
                make_text_screen(dims,
                                 "Round {}".format(r_i + 1) +
                                 ("\n" + round_config.name
                                  if round_config.name is not None else ""),
                                 TRANSITION_DURATION,
                                 make_background(stacks[r_i],
                                                 round_config.background,
                                                 dims)),
                get_black_clip(dims),
            ]) for r_i, round_config in enumerate(round_configs)
        ]

        # Add title
        # TODO: add output_config.title_duration
        #       and add output_config.title_background
        #       and round_config.transition_duration
        #       and modify background => round_config.transition_background
        # TODO: test backgrounds, add documentation in README
        print("Assembling Main Title...")
        title_text = "Cock Hero\n"
        title = make_text_screen(dims, title_text)
        title_text += output_name
        title2 = make_text_screen(dims, title_text)
        main_title_clips = [
            get_black_clip(dims),
            title,
            title2,
            get_black_clip(dims),
        ]
        main_title_video = crossfade(main_title_clips)

        # Add credits, if data is available
        credits_data_list = [r.credits for r in round_configs]
        credits_video_thread = None
        if credits_data_list != []:
            print("Assembling Credits...")
            if output_config.cache == "all":
                credits_video = make_credits(credits_data_list,
                                             dims[0],
                                             dims[1],
                                             stroke_color=None,
                                             gap=30)
            else:
                credits_video_filename = "%s_Credits.%s" % (output_name, ext)
                if not os.path.exists(credits_video_filename):
                    credits_video = make_credits(credits_data_list,
                                                 dims[0],
                                                 dims[1],
                                                 stroke_color=None,
                                                 gap=30)
                    credits_video_thread = Thread(
                        target=lambda: credits_video.write_videofile(
                            credits_video_filename,
                            codec=codec,
                            fps=output_config.fps,
                            preset=FFMPEG_PRESET,
                        ))
                    credits_video_thread.start()

                    if max_threads <= 1:
                        credits_video_thread.join()

        if output_config.assemble and output_config.cache == "all":
            print("Beginning Final Assembly")

            # Reload rounds from output files, if not still in memory
            rounds = [
                stacks[r_i].enter_context(VideoFileClip(
                    get_round_name(output_name, round_config.name, ext)))
                if round_config._is_on_disk else round_videos.pop()
                for r_i, round_config in enumerate(round_configs)
            ]

            # Gather together all the videos
            all_video = [None]*(2 * len(rounds))
            all_video[0::2] = round_transitions
            all_video[1::2] = rounds
            all_video = [main_title_video] + all_video
            if credits_data_list != []:
                all_video.append(credits_video)

            # Output final video
            temp_video_name = "%s_TEMP.%s" % (output_name, ext)
            concatenate_videoclips(all_video).write_videofile(
                temp_video_name,
                codec=codec,
                fps=output_config.fps,
                preset=FFMPEG_PRESET,
                threads=4,
            )

            # Prepare metadata file for chapter markers
            round_lengths = [video.duration for video in all_video]
            metadata_filename = output_name + ".ffmd"
            make_metadata_file(metadata_filename,
                               output_name,
                               round_lengths,
                               credits_data_list)

            # Add metadata
            # TODO: don't duplicate output file
            command = "ffmpeg {} {} {} {} {}".format(
                '-v quiet -stats -y',
                '-i "concat:%s"' % temp_video_name,
                '-i "%s"' % metadata_filename,
                '-c copy -map_metadata 1',
                '"%s.%s"' % (output_name, ext),
            )
            os.system(command)
            os.remove(temp_video_name)
            os.remove(metadata_filename)

        elif output_config.assemble:
            print("Writing Round Transitions and Main Title")

            # Write main title screen video
            main_title_filename = "{}_Title.{}".format(output_name, ext)
            main_title_thread = None
            if not os.path.exists(main_title_filename):
                # If it exists, don't remake it
                main_title_thread = Thread(
                    target=lambda: main_title_video.write_videofile(
                        main_title_filename,
                        codec=codec,
                        fps=output_config.fps,
                        preset=FFMPEG_PRESET,
                    ))
                if max_threads <= 1 and credits_video_thread is not None:
                    credits_video_thread.join()
                main_title_thread.start()
                if max_threads <= 1:
                    main_title_thread.join()

            # Write round transition videos
            threads = []
            for r_i, transition in enumerate(round_transitions):
                round_title_filename = get_round_name(
                    output_name,
                    round_configs[r_i].name + "_Title",
                    ext)
                # If they exist, don't remake them
                if not os.path.exists(round_title_filename):
                    def write_round_intro():
                        transition.write_videofile(
                            round_title_filename,
                            codec=codec,
                            fps=output_config.fps,
                            preset=FFMPEG_PRESET,
                        )

                    thread = Thread(target=write_round_intro)
                    threads.append(thread)
                    thread.start()
                    # If too many threads are running, then
                    if len(threads) >= max_threads:
                        # wait for first (thread that was started) to finish
                        first, threads = threads[0], threads[1:]
                        print("Waiting for intro #{} to finish...".format(
                            r_i - max_threads + 2
                        ))
                        first.join()

    if output_config.assemble:
        # TODO: Assemble this list as files are output/found
        main_title_filename = "%s_Title.%s" % (output_name, ext)
        intermediate_filenames = [main_title_filename]
        for r_i, round_config in enumerate(round_configs):
            round_name = round_config.name
            round_title_filename = get_round_name(
                output_name, round_name + "_Title", ext)
            intermediate_filenames.append(round_title_filename)
            round_filename = get_round_name(output_name, round_name, ext)
            intermediate_filenames.append(round_filename)
        if credits_data_list != []:
            intermediate_filenames.append(credits_video_filename)

        if output_config.cache != "all":
            print("Waiting for all parts to finish...")
            if main_title_thread is not None:
                main_title_thread.join()
            if credits_video_thread is not None:
                credits_video_thread.join()
            for thread in threads:
                thread.join()
            print("Beginning final assembly")

            # Prepare metadata file for chapter markers
            round_lengths = []
            for filename in intermediate_filenames:
                with VideoFileClip(filename) as video_file:
                    round_lengths.append(video_file.duration)
            metadata_filename = output_name + ".ffmd"
            make_metadata_file(metadata_filename, output_name,
                               round_lengths, credits_data_list)

            # TODO: Don't use inputs.txt intermediate file
            filelist_filename = "%s_inputs.txt" % output_name
            with open(filelist_filename, "w") as filelist_handle:
                filelist_handle.writelines([
                    "file '%s'\n" % intermediate_filename
                    for intermediate_filename in intermediate_filenames
                ])
                intermediate_filenames.append(filelist_filename)

            command = "ffmpeg {} {} {} {} {}".format(
                '-v quiet -stats -y -f concat',
                '-i "%s"' % filelist_filename,
                '-i "%s"' % metadata_filename,
                '-c copy -map_metadata 1',
                '"%s.%s"' % (output_name, ext),
            )
            os.system(command)

        if output_config.delete:
            # delete intermediate files
            print("Deleting Files")
            intermediate_filenames.append(metadata_filename)
            for intermediate_filename in intermediate_filenames:
                if os.path.exists(intermediate_filename):
                    os.remove(intermediate_filename)
