import PIL.Image
import PIL.ImageTk
import time
import tkinter
import math
# from moviepy.decorators import convert_masks_to_RGB, requires_duration
from moviepy.video.VideoClip import VideoClip
from moviepy.video.compositing.CompositeVideoClip import clips_array
from moviepy.video.fx.resize import resize

from constants import DISPLAY_SIZE


class ResizingCanvas(tkinter.Canvas):
    # from https://stackoverflow.com/questions/22835289/
    def __init__(self, parent, **kwargs):
        tkinter.Canvas.__init__(self, parent, **kwargs)
        self.bind("<Configure>", self.on_resize)
        self.height = self.winfo_reqheight()
        self.width = self.winfo_reqwidth()

    def on_resize(self, event):
        # determine the ratio of old width/height to new width/height
        wscale = float(event.width)/self.width
        hscale = float(event.height)/self.height
        self.width = event.width
        self.height = event.height
        # resize the canvas
        self.config(width=self.width, height=self.height)
        # rescale all the objects tagged with the "all" tag
        self.scale("all", 0, 0, wscale, hscale)


class PreviewGUI:
    def __init__(self,
                 clips: [VideoClip],
                 choose: lambda: int,
                 display_size: (int, int) = DISPLAY_SIZE,
                 fps: int = 15):
        self.window = tkinter.Tk()
        self.window.title("Preview: Choose which version to use")
        self.display_size = display_size
        self._choose = choose
        self.fps = fps
        self.update_id = None
        self.is_full_screen = False
        self.num_versions = len(clips)

        # Create a canvas that can fit the above video source size
        self.canvas = ResizingCanvas(self.window,
                                     width=display_size[0],
                                     height=display_size[1],
                                     highlightthickness=0)
        self.canvas.pack(fill=tkinter.BOTH, expand=tkinter.YES)

        # Add handlers to canvas for input
        for key in [str(k) for k in range(1, len(clips) + 1)]:
            self.window.bind(key, self.on_number_key)
        self.window.bind("<Button-1>", self.on_click)
        self.window.bind("<Escape>", self.exit)
        self.window.bind('f', self.toggle_full_screen)
        self.window.bind('r', self.refresh_sources)
        self.window.bind("<Left>", self.scrub_backward)
        self.window.bind("<Right>", self.scrub_forward)
        self.window.bind("<Key-space>", lambda e: self.pause()
                         if self.is_playing else self.play())

        # Prepare the clips by combining them into a composite clip
        self.square_size = math.ceil(math.sqrt(len(clips)))
        segments = [
            [
                resize(clips[i + j], 1 / self.square_size)
                for j in range(self.square_size)
                if i + j < len(clips)
            ] for i in range(0, len(clips), self.square_size)
        ]

        self.native_video = resize(clips_array(segments), self.display_size)
        # TODO: fix fullscreen
        # self.fullscreen_video = resize(
        #   clips_array(segments), height=self.window.winfo_screenheight())
        self.video = self.native_video

        self.dt = 1.0 / fps
        self.t = 0
        self.is_playing = False
        self.display()

    def run(self):
        self.play()
        self.window.mainloop()
        self.window.destroy()

    def play(self):
        self.is_playing = True
        self.t0 = time.time() - self.t
        self.update()

    def pause(self):
        self.is_playing = False
        if self.update_id is not None:
            self.window.after_cancel(self.update_id)

    def scrub_backward(self, _: tkinter.Event = None):
        adjust = 5.0 if self.is_playing else 1.0 / self.fps
        if adjust > self.t:
            adjust = self.t
        self.t0 += adjust
        self.t -= adjust
        self.display()

    def scrub_forward(self, _: tkinter.Event = None):
        adjust = 5.0 if self.is_playing else 1.0 / self.fps
        remainder = self.video.duration - self.t
        if adjust > remainder:
            adjust = remainder

        self.t0 -= adjust
        self.t += adjust
        self.display()

    def exit(self, _: tkinter.Event = None):
        self.pause()
        self.window.quit()

    def on_click(self, event: tkinter.Event):
        x_dim, y_dim = self.display_size
        x = math.floor(event.x / x_dim * self.square_size)
        y = math.floor(event.y / y_dim * self.square_size)
        choice = y * self.square_size + x
        if choice < 0 or choice > self.num_versions:
            return
        else:
            self._choose(choice)
            self.exit(event)

    def on_number_key(self, event):
        self._choose(int(event.char) - 1)
        self.exit(event)

    def toggle_full_screen(self, _: tkinter.Event = None):
        pass
        """
        self.is_full_screen = not self.is_full_screen
        self.window.attributes("-fullscreen", self.is_full_screen)
        self.video = (self.fullscreen_video if self.is_full_screen
                      else self.native_video)
        """

    def refresh_sources(self, _: tkinter.Event = None):
        # TODO: refresh source clips
        # self.video = self.assemble_video(self.callback())
        pass

    def display(self):
        self.frame = self.video.get_frame(self.t)
        self.photo = PIL.ImageTk.PhotoImage(
            image=PIL.Image.fromarray(self.frame))
        self.canvas.create_image(0, 0, image=self.photo, anchor=tkinter.NW)
        self.canvas.update()

    def update(self):
        if not self.is_playing:
            return

        # Get the current frame from the video source
        start = time.time()
        self.t = start - self.t0
        if self.t >= self.video.duration:  # Repeat clips on loop
            self.t0 = time.time()
            self.t = 0

        self.display()

        # Repeat update after delay, respecting framerate
        stop = time.time()
        lost_time = stop - start
        wait = max(0, int(1000 * (self.dt - lost_time)))
        self.update_id = self.window.after(wait, self.update)
