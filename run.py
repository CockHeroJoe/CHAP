import os
import sys
from contextlib import ExitStack, AbstractContextManager
from concurrent.futures import ThreadPoolExecutor
from threading import Thread, Lock, Semaphore
import gc
from math import ceil

from moviepy.video import VideoClip
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.audio.fx.volumex import volumex
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.resize import resize

from constants import TRANSITION_DURATION, FFMPEG_PRESET
from cutters import get_cutter
from credit import make_credits
from utils import get_black_clip,\
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
                print("\r\nError closing stack: " + str(e))

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


def _write_video(
    stack: ExitStack,
    max_threads_semaphore: Semaphore,
    video: VideoClip,
    filename: str,
    codec: str,
    fps: float,
    ext: str,
):
    max_threads_semaphore.acquire()
    try:
        video.write_videofile(
            filename,
            fps=fps,
            codec=codec,
            preset=FFMPEG_PRESET,
        )
    except Exception as e:
        print("\r\nVideo (%s) failed to write: maybe not enough memory/disk"
              % filename)
        print(e)
        if os.path.exists(filename):
            os.remove(filename)
        temp_mp3_filename = filename[:-4] + "TEMP_MPY_wvf_snd.mp3"
        if os.path.exists(temp_mp3_filename):
            os.remove(temp_mp3_filename)
        filename = None
    finally:
        stack.close()  # close all video files for this round
        max_threads_semaphore.release()
    return filename


def _get_ext_codec(is_raw: bool):
    return ("avi" if is_raw else "mp4", "png" if is_raw else None)


def make_round(
    stack: ExitStack,
    output_config: OutputConfig,
    r_i: int,
    cutter_lock: Lock,
    max_threads_semaphore: Semaphore
):
    max_threads_semaphore.acquire()
    round_config = output_config.rounds[r_i]
    ext, codec = _get_ext_codec(output_config.raw)

    # Skip rounds that have been saved
    if round_config._is_on_disk:
        name = get_round_name(output_config.name, round_config.name, ext)
        max_threads_semaphore.release()
        return name

    # Assemble beatmeter video from beat images
    bmcfg = (round_config.beatmeter_config
             if round_config.bmcfg else None)
    if round_config.beatmeter is not None:
        print("\r\nAssembling beatmeter #{}...".format(r_i + 1))
        beatmeter_thread = ThreadWithReturnValue(
            target=lambda: make_beatmeter(
                stack,
                round_config.beatmeter,
                bmcfg.fps if bmcfg else output_config.fps,
                round_config.duration,
                (output_config.xdim, output_config.ydim),
            ),
            daemon=True,
        )
        beatmeter_thread.start()

    # Get list of clips cut from sources using chosen cutter
    # TODO: get duration, bpm from music track; generate beatmeter
    print("\r\nLoading sources for round #%i..." % (r_i + 1))
    cutter = get_cutter(stack, output_config, round_config)
    print("\r\nShuffling input videos for round #%i..." % (r_i+1))
    if output_config.versions > 1:
        # Await previous cutter, if still previewing
        cutter_lock.acquire()
        # TODO: pass in cutter lock to release on preview exit
        clips = cutter.get_compilation()
        cutter_lock.release()
    else:
        clips = cutter.get_compilation()

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

    # Concatenate this round's video clips together and add audio
    round_video = concatenate_videoclips(clips)
    if audio is not None:
        beat_audio = CompositeAudioClip(audio)
        level = round_config.audio_level
        if level > 1:
            beat_audio = volumex(beat_audio, 1 / level)
        else:
            round_video = volumex(round_video, level)
        audio = CompositeAudioClip([beat_audio, round_video.audio])
        round_video = round_video.set_audio(audio)

    # Add beatmeter, if supplied
    if round_config.beatmeter is not None:
        # Wait for beatmeter, if it exists
        print("\r\nWaiting for beatmeter #%i..." % (r_i + 1))
        beatmeter = beatmeter_thread.join()
        round_video = CompositeVideoClip([round_video, beatmeter])
    round_video = round_video.set_duration(round_config.duration)

    # Fade in and out
    round_video = crossfade([
        get_black_clip((output_config.xdim, output_config.ydim)),
        round_video,
        get_black_clip((output_config.xdim, output_config.ydim)),
    ])

    if output_config.cache == "round":
        # Save each round video to disk
        filename = get_round_name(output_config.name, round_config.name, ext)
        filename = _write_video(stack,
                                round_video,
                                filename,
                                codec,
                                output_config.fps,
                                ext)
        round_config._is_on_disk = filename is not None
        max_threads_semaphore.release()
        return filename
    else:  # output_config.cache == "all":
        max_threads_semaphore.release()
        return round_video  # Store round in memory instead


def make_beatmeter(
    stack: ExitStack,
    beatmeter: str,
    fps: float,
    duration: float,
    dims: (int, int),
):
    xdim, ydim = dims
    beat_image_filenames = [
        str(os.path.join(beatmeter, filename)) for filename in
        sorted(os.listdir(beatmeter))[:ceil(duration * fps)]
    ]
    beatmeter = stack.enter_context(ImageSequenceClip(
        beat_image_filenames,
        fps=fps
    ))
    # resize and fit beatmeter
    # pylint: disable=no-member
    new_height = (beatmeter.h * xdim / beatmeter.w)
    beatmeter = resize(beatmeter, (xdim, new_height))
    beatmeter = beatmeter.set_position(
        ("center", ydim - 20 - beatmeter.h)
    )
    return beatmeter


def make_transition_video(
    stack: ExitStack,
    output_config: OutputConfig,
    r_i: int
):
    dims = (output_config.xdim, output_config.ydim)
    round_config = output_config.rounds[r_i]

    # Add round transitions
    print("\r\nAssembling Round transitions...")
    return crossfade([
        get_black_clip(dims),
        make_text_screen(dims,
                         "Round {}".format(r_i + 1) +
                         ("\n" + round_config.name
                          if round_config.name is not None else ""),
                         TRANSITION_DURATION,
                         make_background(stack,
                                         round_config.background,
                                         dims)),
        get_black_clip(dims),
    ])


def make_title_video(stack: ExitStack, output_config: OutputConfig,):
    dims = (output_config.xdim, output_config.ydim)

    # Add title
    # TODO: add output_config.title_duration
    #       and add output_config.title_background
    #       and round_config.transition_duration
    #       and modify background => round_config.transition_background
    #       use stacks[-2] for title_background file loading
    # TODO: test backgrounds, add documentation in README
    print("\r\nAssembling Main Title...")
    title_text = "Cock Hero\n"
    title = make_text_screen(dims, title_text)
    title_text += output_config.name
    title2 = make_text_screen(dims, title_text)
    main_title_clips = [
        get_black_clip(dims),
        title,
        title2,
        get_black_clip(dims),
    ]
    return crossfade(main_title_clips)


def make_credits_video(stack: ExitStack, output_config: OutputConfig):
    output_name = output_config.name
    # Add credits, if data is available
    credits_data_list = [r.credits for r in output_config.rounds]
    credits_video = None
    if credits_data_list != []:
        print("\r\nAssembling Credits...")
        if output_config.cache == "all":
            credits_video = make_credits(credits_data_list,
                                         output_config.xdim,
                                         output_config.ydim,
                                         stroke_color=None,
                                         gap=30)
        else:
            ext, _ = _get_ext_codec(output_config.raw)
            credits_video_filename = "%s_Credits.%s" % (output_name, ext)
            if os.path.exists(credits_video_filename):
                print("\r\nReloaded %s from disk" % credits_video_filename)
                credits_video = stack.enter_context(
                    VideoFileClip(credits_video_filename))

            else:
                credits_video = make_credits(credits_data_list,
                                             output_config.xdim,
                                             output_config.ydim,
                                             stroke_color=None,
                                             gap=30)

    return credits_video


def make(output_config: OutputConfig):
    ext, codec = _get_ext_codec(output_config.raw)
    output_name = output_config.name
    max_threads = output_config.threads
    credits_data_list = [r.credits for r in output_config.rounds]

    if output_config.rounds == []:
        print("\r\nERROR: No round configs provided")
        sys.exit(1)

    round_configs = output_config.rounds
    for round_config in round_configs:
        name = get_round_name(output_name, round_config.name, ext)
        if os.path.exists(name):
            round_config._is_on_disk = True
            print("\r\nReloaded round %s from disk" % name)

    with StackList(len(round_configs) + 2) as stacks:
        # Shuffle clips for each round and attach beatmeters
        rounds = []
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            # Make each round with a worker thread
            cutter_lock = Lock()
            thread_count = Semaphore(max_threads)
            rounds = executor.map(lambda a: make_round(*a), [
                (stacks[r_i], output_config, r_i, cutter_lock, thread_count)
                for r_i in range(len(round_configs))
            ])
            rounds = [r if type(r) is str else r.result() for r in rounds]

        # Check that all intermediate videos were output correctly
        ok = True
        for r_i, r in enumerate(rounds):
            if r is None:
                ok = False
                print("\r\nERROR: Round %i was not prepared" % r_i)
        if not ok:
            sys.exit(1)

        print("\r\nAll Rounds prepared")
        gc.collect()  # Free as much memory as possible

        if output_config.assemble and output_config.cache == "all":
            credits_video = make_credits_video(stacks[-1], output_config)
            main_title_video = make_title_video(stacks[-2], output_config)
            round_transitions = [
                make_transition_video(stacks[r_i], output_config, r_i)
                for r_i in range(len(rounds))
            ]

            print("\r\nBeginning Final Assembly")

            # Reload rounds from output files, if not still in memory
            rounds = [
                stacks[r_i].enter_context(VideoFileClip(r))
                if type(r) is str else r for r, r_i in enumerate(rounds)
            ]

            # Gather together all the videos
            all_video = [None] * 2 * len(rounds)
            all_video[0::2] = round_transitions
            all_video[1::2] = rounds
            all_video = [main_title_video] + all_video
            if credits_video is not None:
                all_video.append(credits_video)

            # Output final video
            temp_video_name = "%s_TEMP.%s" % (output_name, ext)
            concatenate_videoclips(all_video).write_videofile(
                temp_video_name,
                codec=codec,
                fps=output_config.fps,
                preset=FFMPEG_PRESET,
                threads=output_config.threads,
            )

            # Prepare metadata file for chapter markers
            metadata_filename = output_name + ".ffmd"
            make_metadata_file(metadata_filename,
                               output_name,
                               [video.duration for video in all_video],
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

    if output_config.assemble and output_config.cache != "all":
        print("\r\nWriting Round Transitions and Main Title")
        # Write temporary videos using multiple workers
        with StackList(len(rounds) + 2) as stacks, ThreadPoolExecutor(
                max_workers=max_threads) as executor:

            # Write credits, if they exist
            thread_count = Semaphore(1)  # Use only one thread for now
            credits_video_filename = "%s_Credits.%s" % (output_name, ext)
            if not os.path.exists(credits_video_filename):
                # If it exists, don't remake it
                credits_video = make_credits_video(stacks[-1], output_config)
                if credits_video is not None:
                    credits_future = executor.submit(_write_video,
                                                     stacks[-1],
                                                     thread_count,
                                                     credits_video,
                                                     credits_video_filename,
                                                     codec,
                                                     output_config.fps,
                                                     ext)
                else:
                    credits_future = None
            else:
                print("\r\nReloaded Credits video from disk")
                credits_future = credits_video_filename

            # Write main title screen video
            main_title_filename = "{}_Title.{}".format(output_name, ext)
            if not os.path.exists(main_title_filename):
                # If it exists, don't remake it
                main_title_video = make_title_video(stacks[-2], output_config)
                main_title_future = executor.submit(_write_video,
                                                    stacks[-2],
                                                    thread_count,
                                                    main_title_video,
                                                    main_title_filename,
                                                    codec,
                                                    output_config.fps,
                                                    ext)
            else:
                print("\r\nReloaded Main Title video from disk")
                main_title_future = main_title_filename

            thread_count = Semaphore(max_threads)
            # Write round transitions
            round_title_futures = []
            for r_i in range(len(rounds)):
                round_title_filename = get_round_name(
                    output_name,
                    round_configs[r_i].name + "_Title",
                    ext)
                # If they exist, don't remake them
                if not os.path.exists(round_title_filename):
                    round_transition_video = make_transition_video(
                        stacks[r_i], output_config, r_i)
                    round_title_futures.append(executor.submit(
                        _write_video,
                        stacks[r_i],
                        thread_count,
                        round_transition_video,
                        round_title_filename,
                        codec,
                        output_config.fps,
                        ext))
                else:
                    print("\r\nReloaded Round %i (%s) from disk" %
                          (r_i + 1, round_title_filename))
                    round_title_futures.append(round_title_filename)

            print("\r\nWaiting for all parts to finish...")
            if credits_future is not None:
                credits_video_filename = (credits_future
                                          if type(credits_future) == str
                                          else credits_future.result())
            else:
                credits_video_filename = None
            main_title_filename = (main_title_future
                                   if type(main_title_future) == str
                                   else main_title_future.result())
            transition_filenames = [transition_future
                                    if type(transition_future) == str
                                    else transition_future.result()
                                    for transition_future
                                    in round_title_futures]

        # Assemble list of videos to concatenate
        intermediate_filenames = [None] * 2 * len(rounds)
        intermediate_filenames[0::2] = transition_filenames
        intermediate_filenames[1::2] = rounds
        intermediate_filenames = [main_title_filename] + intermediate_filenames
        if credits_video_filename is not None:
            intermediate_filenames.append(credits_video_filename)

        # Check that all intermediate videos were output correctly
        ok = True
        for f_i, filename in enumerate(intermediate_filenames):
            if filename is None:
                round_index = (f_i + 1) // 2
                if f_i == 0:
                    video_name = "Main Title"
                elif credits_video and f_i == len(intermediate_filenames) - 1:
                    video_name = "Credits"
                elif f_i % 2 == 1:  # If this is a round transition
                    video_name = "Round %i Intro" % round_index
                else:
                    video_name = "Round " + str(round_index)
                ok = False
                print("\r\nVideo %s was not prepared" % video_name)
        if not ok:
            sys.exit(1)

        print("\r\nBeginning final assembly")
        # Output intermediate filenames to file for FFMpeg
        filelist_filename = "%s_inputs.txt" % output_name
        with open(filelist_filename, "w") as filelist_handle:
            # TODO: Don't use inputs.txt intermediate file
            filelist_handle.writelines([
                "file '%s'\n" % intermediate_filename.replace("'", "\\'")
                for intermediate_filename in intermediate_filenames
            ])

        # Prepare metadata file for chapter markers
        round_lengths = []
        for filename in intermediate_filenames:
            with VideoFileClip(filename) as video_file:
                round_lengths.append(video_file.duration)
        metadata_filename = output_name + ".ffmd"
        make_metadata_file(metadata_filename,
                           output_name,
                           round_lengths,
                           credits_data_list)

        command = "ffmpeg {} {} {} {} {}".format(
            '-v quiet -stats -y -f concat -safe 0',
            '-i "%s"' % filelist_filename,
            '-i "%s"' % metadata_filename,
            '-c copy -map_metadata 1',
            '"%s.%s"' % (output_name, ext),
        )
        os.system(command)
        intermediate_filenames.append(metadata_filename)
        intermediate_filenames.append(filelist_filename)
    elif output_config.cache == "all":
        intermediate_filenames = [temp_video_name, metadata_filename]

    # Delete intermediate files
    if output_config.delete or output_config.cache == "all":
        # TODO: no intermediate files with cache == "all"
        print("\r\nDeleting Files")
        for intermediate_filename in intermediate_filenames:
            if os.path.exists(intermediate_filename):
                os.remove(intermediate_filename)

    print("\r\n%s Ready! CH Assembly Program exiting." % output_name)
