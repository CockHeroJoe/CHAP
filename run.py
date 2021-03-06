import os
import sys
from contextlib import ExitStack, AbstractContextManager
from threading import Thread
import gc

from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.audio.fx.volumex import volumex
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.resize import resize

from constants import TRANSITION_DURATION
from cutters import Interleaver, Skipper, Randomizer, Sequencer
from credit import make_credits
from utils import SourceFile,\
    get_black_clip,\
    get_time_components,\
    get_round_name,\
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
    codec = "png" if output_config.raw else None
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
                        preset="ultrafast",
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

        # Add credits, if data is available
        credits_data_list = [
            r.credits for r in round_configs
            if r.credits is not None
            and (r.credits.audio != [] or r.credits.video != [])
        ]
        credits_video_thread = None
        if credits_data_list != []:
            print("Assembling Credits...")
            credits_video = make_credits(credits_data_list,
                                         dims[0],
                                         dims[1],
                                         stroke_color=None,
                                         gap=30)

            credits_video_filename = "{}_Credits.{}".format(output_name, ext)
            if output_config.cache != "all":
                if not os.path.exists(credits_video_filename):
                    credits_video_thread = Thread(
                        target=lambda: credits_video.write_videofile(
                            credits_video_filename,
                            codec=codec,
                            fps=output_config.fps,
                            preset="slow",
                        ))
                    credits_video_thread.start()

                    if max_threads <= 1:
                        credits_video_thread.join()

        if output_config.assemble and output_config.cache == "all":
            print("Beginning Final Assembly")

            # Reload rounds from output files, if not still in memory
            print("Reloading Rounds...")
            rounds = [
                stacks[r_i].enter_context(VideoFileClip(
                    get_round_name(output_name, round_config.name, ext)))
                if round_config._is_on_disk else round_videos.pop()
                for r_i, round_config in enumerate(round_configs)
            ]

            # Gather together all the videos
            all_video = [None]*(3 * len(rounds))
            all_video[0::2] = round_transitions
            all_video[1::2] = rounds
            all_video = main_title_clips + all_video
            if credits_data_list != []:
                all_video.append(credits_video)

            # Output final video
            output = concatenate_videoclips(all_video)
            name = "{}.{}".format(output_name, ext)
            output.write_videofile(
                name,
                codec=codec,
                fps=output_config.fps,
                preset="slow",
                threads=4
            )
        elif output_config.assemble:
            print("Writing Round Transitions and Main Title")

            # Write main title screen video
            main_title_filename = "{}_Title.{}".format(output_name, ext)
            main_title_thread = None
            if not os.path.exists(main_title_filename):
                # If it exists, don't remake it
                main_title_thread = Thread(
                    target=lambda: crossfade(main_title_clips).write_videofile(
                        main_title_filename,
                        codec=codec,
                        fps=output_config.fps,
                        preset="slow",
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
                            preset="slow",
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

            # Prepare metadata file
            metadata_filename = output_name + ".ffmd"
            with open(metadata_filename, "w") as metadata_filehandle:
                metadata_filehandle.writelines([
                    ";FFMETADATA1\n",
                    "title=%s\n" % output_name,
                    "artist=The One True Cock Hero\n",  # TODO: add performers?
                ])

                current_time_index = 0.0
                for filename_i, filename in enumerate(intermediate_filenames):

                    # Adjust time indices using length of next video to concat
                    previous_time_index = current_time_index
                    with VideoFileClip(filename) as video_file:
                        current_time_index += video_file.duration

                    round_index = (filename_i + 1) // 2
                    if filename_i == 0:
                        chapter_name = "Main Title"
                    elif (filename_i == len(intermediate_filenames) - 1
                          and credits_data_list != []):
                        chapter_name = "Credits"
                    elif filename_i % 2 == 1:  # If this is a round transition
                        chapter_name = "Round %d Intro" % round_index
                    else:
                        chapter_name = "Round " + str(round_index)

                    metadata_filehandle.writelines([
                        "#\n",
                        "# %s\n" % chapter_name.upper(),
                        "#\n",
                        "[CHAPTER]\n",
                        "TIMEBASE=1/1000\n",
                        "# %s start at %02i:%02i:%02i.%02i\n" % (
                            chapter_name,
                            *get_time_components(previous_time_index)
                        ),
                        "START=%i\n" % (previous_time_index * 1000),
                        "# %s ends at %02i:%02i:%02i.%02i\n" % (
                            chapter_name,
                            *get_time_components(current_time_index - 0.001),
                        ),
                        "END=%i\n" % (current_time_index * 1000 - 1),
                        "title=%s\n" % chapter_name,
                    ])

                metadata_filehandle.writelines([
                    "#\n",
                    "# END OF METADATA\n",
                    "#\n",
                    "[STREAM]\n"
                    "title=%s\n" % output_name,
                ])

            # TODO: Don't use inputs.txt intermediate file
            filelist_filename = "inputs.txt"
            with open(filelist_filename, "w") as filelist_handle:
                filelist_handle.writelines([
                    "file '%s'\n" % intermediate_filename
                    for intermediate_filename in intermediate_filenames
                ])
                intermediate_filenames.append(filelist_filename)

            command = "ffmpeg {} {} -c copy {} {}".format(
                "-v quiet -stats -f concat -y -safe 0",
                "-i %s -i %s" % (filelist_filename, metadata_filename),
                "-map_metadata 1",
                output_name + "." + ext
            )
            os.system(command)

        if output_config.delete:
            # delete intermediate files
            print("Deleting Files")
            for intermediate_filename in intermediate_filenames:
                if os.path.exists(intermediate_filename):
                    os.remove(intermediate_filename)
