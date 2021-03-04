
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.fx.resize import resize
from moviepy.video.VideoClip import ImageClip, TextClip

import datetime


class AudioCredit:
    def __init__(self, config: dict = {}):
        if type(config) != dict:
            config = config.__dict__

        self.artist = config.get("artist", None)
        self.song = config.get("song", None)

    def __str__(self):
        fields = [
            f for f in [
                self.artist,
                self.song,
            ] if f is not None
        ]
        return ("{}\n" * len(fields)).format(*fields)

    def validate(self):
        if type(self.artist) != str:
            raise ValueError(
                "wrong data type for artist ({self.artist}), must be str")
        elif type(self.song) != str:
            raise ValueError(
                "wrong data type for song ({self.song}), must be str")


class VideoCredit:
    def __init__(self, config: dict = {}):
        if type(config) != dict:
            config = config.__dict__

        self.studio = config.get("studio", None)
        self.title = config.get("title", None)
        self.date = config.get("date", None)
        self.performers = config.get("performers", [])

    def __str__(self):
        fields = [
            f for f in [
                self.studio,
                self.date,
                self.title,
                *self.performers
            ] if f is not None
        ]
        return ("{}\n" * len(fields)).format(*fields)

    def validate(self):
        if self.studio is not None and type(self.studio) != str:
            raise ValueError(
                "wrong data type for studio ({}), must be str".format(
                    self.studio))
        elif self.title is not None and type(self.title) != str:
            raise ValueError(
                "wrong data type for title ({}), must be str".format(
                    self.title))
        elif self.date is not None and (type(self.date) != str):
            raise ValueError(
                "wrong data type for date ({}), must be str".format(
                    self.date))
        elif type(self.performers) != list:
            raise ValueError(
                "wrong data type for performers ({}), must be list".format(
                    self.performers))
        for performer in self.performers:
            if type(performer) != str:
                raise ValueError(
                    "wrong data type for performer ({performer}), must be str"
                )
        if self.date is not None:
            try:
                datetime.datetime.strptime(self.date, "%Y.%m.%d")
            except ValueError:
                raise ValueError("Incorrect date format, should be YYYY-MM-DD")


class RoundCredits:
    def __init__(self, config: dict = None, _get=False):
        if None is config:
            config = {}
        if type(config) != dict:
            config = config.__dict__

        if _get:
            config = _apply_to_leaves(config, "get")

        self.audio = [AudioCredit(c) for c in config.get("audio", [])]
        self.video = [VideoCredit(c) for c in config.get("video", [])]

    def validate(self):
        for audio_credit in self.audio:
            audio_credit.validate()
        for video_credit in self.video:
            video_credit.validate()


def make_credits(
        credits_data: [RoundCredits],
        width,
        color='white',
        stroke_color='black',
        stroke_width=2,
        font='Impact-Normal',
        fontsize=60,
        gap=0
):
    """

    Parameters
    -----------

    credits_data
      A list of RoundCredits objects

    width
      Total width of the credits text in pixels

    gap
      Horizontal gap in pixels between the jobs and the names

    color
      Color of the text. See ``TextClip.list('color')``
      for a list    of acceptable names.

    font
      Name of the font to use. See ``TextClip.list('font')`` for
      the list of fonts you can use on your computer.

    fontsize
      Size of font to use

    stroke_color
      Color of the stroke (=contour line) of the text. If ``None``,
      there will be no stroke.

    stroke_width
      Width of the stroke, in pixels. Can be a float, like 1.5.


    Returns
    ---------

    image
      An ImageClip instance that looks like this and can be scrolled
      to make some credits:

          Executive Story Editor    MARCEL DURAND
             Associate Producers    MARTIN MARCEL
                                    DIDIER MARTIN
                Music Supervisor    JEAN DIDIER

    """
    def make_credit_texts(credit: str, first=""):
        num_lines = credit.count("\n")
        return [
            [first, credit],
            *([["\n", ""]] * num_lines),
            ["\n", "\n"]
        ]

    texts = []
    texts += [["\n", "\n"]] * 16
    for r_i in range(len(credits_data)):
        round_credits = credits_data[r_i]
        if round_credits.audio is not []:
            texts += make_credit_texts(
                str(round_credits.audio[0]),
                "ROUND {} MUSIC".format(r_i + 1))
            for audio_credit in round_credits.audio[1:]:
                texts += make_credit_texts(str(audio_credit))
        if round_credits.video is not []:
            texts += make_credit_texts(
                str(round_credits.video[0]),
                "ROUND {} VIDEOS".format(r_i + 1))
            for video_credit in round_credits.video[1:]:
                texts += make_credit_texts(str(video_credit))
        texts += [["\n", "\n"]] * 2

    # Make two columns for the credits
    left, right = ("".join(t) for t in zip(*texts))
    left, right = [TextClip(txt, color=color, stroke_color=stroke_color,
                            stroke_width=stroke_width, font=font,
                            fontsize=fontsize, align=al)
                   for txt, al in [(left, 'East'), (right, 'West')]]
    # Combine the columns
    cc = CompositeVideoClip([left, right.set_position((left.w + gap, 0))],
                            size=(left.w + right.w + gap, right.h),
                            bg_color=None)

    scaled = resize(cc, width=width)  # Scale to the required size

    # Transform the whole credit clip into an ImageClip
    imclip = ImageClip(scaled.get_frame(0))
    amask = ImageClip(scaled.mask.get_frame(0), ismask=True)

    return imclip.set_mask(amask)


def _apply_to_leaves(tree, method) -> dict:
    def _a2l(t):
        if type(t) is list:
            return [_a2l(e) for e in t]
        elif type(t) is dict:
            return {k: _a2l(v) for k, v in t.items()}
        else:
            return getattr(t, method)()
    return _a2l(tree)
