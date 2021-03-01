import sys
import random

from contextlib import ExitStack

from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.compositing.transitions import crossfadein
from moviepy.video.fx.resize import resize
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import TextClip, VideoClip, ColorClip

from constants import FADE_DURATION, TRANSITION_DURATION


class SourceFile:

    @staticmethod
    def get_random_start():
        """Skip first 15-25 seconds"""
        return 15 + random.random() * 10

    def __init__(self, clip):
        self.start = SourceFile.get_random_start()
        self.clip = clip


def get_black_clip(dims: (int, int), duration=2 * FADE_DURATION):
    return ColorClip(dims, (0, 0, 0), duration=duration)


def get_round_name(basename: str, rname: str, ext: str):
    return "{}_{}.{}".format(basename, rname, ext)


def make_text_screen(
        dimensions: (int, int),
        text: str,
        duration: float = TRANSITION_DURATION,
        background: VideoClip = None,
        font=70,
        color="white"):
    if background is None:
        background = get_black_clip(dimensions)
    return CompositeVideoClip([
        resize(background.set_duration(duration), dimensions),
        TextClip(
            text,
            fontsize=font,
            color=color
        ).set_position("center").set_duration(duration)
    ])


def make_background(
        exit_stack: ExitStack,
        background_filename: str,
        dimensions: (int, int),
        duration: float = TRANSITION_DURATION):
    if background_filename is None:
        return get_black_clip(dimensions, duration)
    return exit_stack.enter_context(VideoFileClip(background_filename))


def crossfade(videos: [VideoClip], fade_duration: float = FADE_DURATION) -> VideoClip:
    for v_i in range(1, len(videos)):
        videos[v_i] = crossfadein(videos[v_i], fade_duration).set_start(
            videos[v_i - 1].end - fade_duration
        )
    return CompositeVideoClip(videos)


def draw_progress_bar(percent: float, barLen: int = 20):
    """
    REQ: percent in interval [0, 1]
    """
    # https://stackoverflow.com/questions/3002085/python-to-print-out-status-bar-and-percentage
    assert percent >= 0 and percent <= 1
    sys.stdout.write("\r")
    sys.stdout.write("{:<{}} {:.0f}%".format(
        "." * int(barLen * percent), barLen, percent * 100))
    sys.stdout.flush()
