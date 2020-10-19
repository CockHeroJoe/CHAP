import numpy as np
import pygame as pg
import threading
import time
from moviepy.decorators import convert_masks_to_RGB, requires_duration
from moviepy.video.io.preview import imdisplay

NUMBER_KEYS = [  # pg.key_code(str(k)) for k in range(1, 10)]
    # X = [
    pg.K_1,
    pg.K_2,
    pg.K_3,
    pg.K_4,
    pg.K_5,
    pg.K_6,
    pg.K_7,
    pg.K_8,
    pg.K_9,
]

@ requires_duration
@ convert_masks_to_RGB
def preview(clip, fps=15, audio=True, audio_fps=22050, audio_buffersize=3000,
            audio_nbytes=2, fullscreen=False):
    """
    Displays the clip in a window, at the given frames per second
    (of movie) rate. It will avoid that the clip be played faster
    than normal, but it cannot avoid the clip to be played slower
    than normal if the computations are complex. In this case, try
    reducing the ``fps``.

    Parameters
    ------------

    fps
      Number of frames per seconds in the displayed video.

    audio
      ``True`` (default) if you want the clip's audio be played during
      the preview.

    audio_fps
      The frames per second to use when generating the audio sound.

    fullscreen
      ``True`` if you want the preview to be displayed fullscreen.

    """
    if fullscreen:
        flags = pg.FULLSCREEN
    else:
        flags = 0

    # compute and splash the first image
    screen = pg.display.set_mode(clip.size, flags)

    audio = audio and (clip.audio is not None)

    if audio:
        # the sound will be played in parrallel. We are not
        # parralellizing it on different CPUs because it seems that
        # pygame and openCV already use several cpus it seems.

        # two synchro-flags to tell whether audio and video are ready
        videoFlag = threading.Event()
        audioFlag = threading.Event()
        # launch the thread
        audiothread = threading.Thread(target=clip.audio.preview,
                                       args=(audio_fps,
                                             audio_buffersize,
                                             audio_nbytes,
                                             audioFlag, videoFlag))
        audiothread.start()

    img = clip.get_frame(0)
    imdisplay(img, screen)
    if audio:  # synchronize with audio
        videoFlag.set()  # say to the audio: video is ready
        audioFlag.wait()  # wait for the audio to be ready

    t0 = time.time()
    for t in np.arange(1.0 / fps, clip.duration-.001, 1.0 / fps):

        img = clip.get_frame(t)

        for event in pg.event.get():
            if event.type == pg.QUIT or \
                    (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE):
                if audio:
                    videoFlag.clear()
                return None
            elif event.type == pg.MOUSEBUTTONDOWN:
                pos = pg.mouse.get_pos()
                if audio:
                    videoFlag.clear()
                return pos
            elif event.type == pg.KEYDOWN and event.key in NUMBER_KEYS:
                if audio:
                    videoFlag.clear()
                return abs(int(pg.key.name(event.key)))

        t1 = time.time()
        time.sleep(max(0, t - (t1-t0)))
        imdisplay(img, screen)
    return (-1, -1)