import tkinter as tk
import tkinter.ttk as ttk
from ttkthemes import ThemedTk
from functools import partial

from parsing import OutputConfig, RoundConfig
from run import make
from credit import AudioCredit, RoundCredits, VideoCredit
from constants import START_DIR


class AbstractGUI():
    def __init__(self, window, config, update=None):
        self.components = {}
        self.window = window
        self.config = config.copy()
        self.tabs = ttk.Notebook(self.window)

        def _update_config(new_config):
            config.__dict__.update(new_config)
            self.config = config.copy()

        self.update_config = update or _update_config

    def _generate_gui_elements(self):
        frames = [ttk.Frame(self.tabs), ttk.Frame(
            self.tabs), ttk.Frame(self.tabs)]
        i = 0
        for attribute in self.config.ITEMS:
            value = self.config.__getattribute__(attribute)
            if attribute[0] == "_":
                continue
            element = self._generate_gui_element(
                frames, attribute, value, i)
            self.components[attribute] = element
            i += len(element) + 2 if type(element) == list else 1

        for frame in frames:
            frame.columnconfigure(1, weight=1)

        return frames

    def _generate_gui_element(self, frames, attribute, value, i):
        if attribute in ["credits", "rounds", "sources"]:
            if attribute == "credits":
                frame = frames[2]
            else:
                frame = frames[1]
        else:
            frame = frames[0]
            label = ttk.Label(frame, text=attribute.title())
            label.grid(row=i, column=0, sticky="w")

        validation = self.config.ITEMS[attribute]
        box = None
        if attribute == "rounds":
            sub_frame = ttk.Frame(frame)
            value_list = []
            for v_i, v in enumerate(value):
                label = ttk.Label(sub_frame, text="{:02d}: ".format(v_i + 1))
                variable = tk.StringVar(sub_frame)
                variable.set(v.name)
                box = ttk.Button(
                    sub_frame, command=lambda: RoundGUI(
                        self.window, v, lambda n: variable.set(n)),
                    text="Edit")
                label.grid(row=v_i, column=0)
                label2 = ttk.Label(sub_frame, textvariable=variable)
                label2.grid(row=v_i, column=1)
                box.grid(row=v_i, column=2)
                value_list += [v.__dict__]
                box2 = ttk.Button(
                    sub_frame,
                    command=partial(self.remove_round, v_i),
                    text="Remove")
                box2.grid(row=v_i, column=3)

            v_i = len(value_list)
            label = ttk.Label(
                sub_frame, text="{:02d}: ".format(len(value) + 1))
            label.grid(row=v_i, column=0)
            box = ttk.Button(sub_frame,
                             command=self.add_round,
                             text="Add")
            box.grid(row=v_i, column=1)
            sub_frame.grid(columnspan=4, rowspan=v_i+1, sticky="ew")
            return value_list
        elif attribute == "sources":
            sub_frame = ttk.Frame(frame)
            value_list = []
            for v_i, v in enumerate(value):
                label = ttk.Label(sub_frame, text="{:02d}: ".format(v_i + 1))
                variable = tk.StringVar(sub_frame)
                variable.set(v)
                box = ttk.Button(sub_frame,
                                 command=partial(self.replace_source, v_i),
                                 text="Replace")
                label.grid(row=v_i, column=0)
                label2 = ttk.Label(sub_frame, textvariable=variable)
                label2.grid(row=v_i, column=1)
                box.grid(row=v_i, column=2)
                value_list += [variable]
                box2 = ttk.Button(
                    sub_frame,
                    command=partial(self.remove_source, v_i),
                    text="Remove")
                box2.grid(row=v_i, column=3)

            v_i = len(value_list)
            label = ttk.Label(
                sub_frame, text="{:02d}: ".format(len(value) + 1))
            label.grid(row=v_i, column=0)
            variable = tk.StringVar(sub_frame)
            box = ttk.Button(sub_frame,
                             command=self.add_source,
                             text="Add")
            box.grid(row=v_i, column=1)
            sub_frame.grid(columnspan=4, rowspan=v_i+1, sticky="ew")
            return value_list
        elif attribute == "credits":
            value_dict = {"audio": [], "video": []}

            label = ttk.Label(frame, text="Audio Credits",
                              font="Roboto 14 bold")
            label.grid(columnspan=5)

            audio_frame = ttk.Frame(frame)
            for v_i, v in enumerate(value.audio):
                label = ttk.Label(audio_frame, text="{:02d}:".format(v_i+1))
                label.grid(row=2*v_i, column=0)

                artist_variable = tk.StringVar(audio_frame)
                artist_variable.set(v.artist)
                label2 = ttk.Label(audio_frame, text="Artist")
                label2.grid(row=2*v_i, column=1)
                box = ttk.Entry(audio_frame, textvariable=artist_variable)
                box.grid(row=2*v_i, column=2)

                song_variable = tk.StringVar(audio_frame)
                song_variable.set(v.song)
                label3 = ttk.Label(audio_frame, text="Song")
                label3.grid(row=2*v_i+1, column=1)
                box2 = ttk.Entry(audio_frame, textvariable=song_variable)
                box2.grid(row=2*v_i+1, column=2)

                value_dict["audio"] += [{"artist": artist_variable,
                                         "song": song_variable}]
                box3 = ttk.Button(
                    audio_frame,
                    command=partial(self.remove_audio_credit, v_i),
                    text="Remove")
                box3.grid(row=2*v_i, column=3)

            length = len(value_dict["audio"])
            label = ttk.Label(audio_frame,
                              text="{:02d}:".format(length+1))
            label.grid(row=2*length, column=0)
            box = ttk.Button(
                audio_frame, command=self.add_audio_credit, text="Add")
            box.grid(row=2*length, column=1)
            audio_frame.grid(sticky='ew', rowspan=2*length+1)

            label = ttk.Label(frame, text="Video Credits",
                              font="Roboto 14 bold")
            label.grid(columnspan=5)
            video_frame = ttk.Frame(frame)
            for v_i, v in enumerate(value.video):
                label = ttk.Label(video_frame,
                                  text="{:02d}:".format(v_i+1))
                label.grid(row=4*v_i, column=0)

                studio_variable = tk.StringVar(video_frame)
                studio_variable.set(v.studio)
                label2 = ttk.Label(video_frame, text="Studio")
                label2.grid(row=4*v_i, column=1)
                box = ttk.Entry(video_frame, textvariable=studio_variable)
                box.grid(row=4*v_i, column=2)

                title_variable = tk.StringVar(video_frame)
                title_variable.set(v.title)
                label3 = ttk.Label(video_frame, text="Title")
                label3.grid(row=4*v_i+1, column=1)
                box2 = ttk.Entry(video_frame, textvariable=title_variable)
                box2.grid(row=4*v_i+1, column=2)

                date_variable = tk.StringVar(video_frame)
                date_variable.set(v.date)
                label4 = ttk.Label(video_frame, text="Date")
                label4.grid(row=4*v_i+2, column=1)
                box3 = ttk.Entry(video_frame, textvariable=date_variable)
                box3.grid(row=4*v_i+2, column=2)

                performer_variable = tk.StringVar(video_frame)
                performer_variable.set(
                    "" if v.performers is None else v.performers[0])
                label5 = ttk.Label(video_frame, text="Performers")
                label5.grid(row=4*v_i+3, column=1)
                box4 = ttk.Entry(video_frame, textvariable=performer_variable)
                box4.grid(row=4*v_i+3, column=2)

                value_dict["video"] += [{
                    "studio": studio_variable,
                    "title": title_variable,
                    "date": date_variable,
                    "performers": [performer_variable],

                }]
                box5 = ttk.Button(
                    video_frame,
                    command=partial(self.remove_video_credit, v_i),
                    text="Remove")
                box5.grid(row=4*v_i, column=4)

            length = len(value_dict["video"])
            label = ttk.Label(video_frame, text="{:02d}:".format(length+1))
            label.grid(row=4*length, column=0)
            box = ttk.Button(
                video_frame, command=self.add_video_credit, text="Add")
            box.grid(row=4*length, column=1)
            video_frame.grid(sticky='ew', rowspan=4*len(value_dict["video"])+1)

            return value_dict
        elif attribute == "name":
            variable = tk.StringVar(frame)
            variable.set(value)
            def _set_name(_a, _b, _c): self.set_name(variable.get())
            variable.trace_add("write", _set_name)
            box = ttk.Entry(frame, textvariable=variable)
            box.grid(row=i, column=1, ipady=7, ipadx=9)
        elif validation["type"] == int:
            value_min = validation["min"]
            value_max = validation["max"]
            variable = tk.IntVar(frame)
            variable.set(value)
            box = ttk.Spinbox(frame, textvariable=variable,
                              from_=value_min, to=value_max)
            box.grid(row=i, column=1)
        elif validation["type"] == float:
            value_min = validation["min"]
            value_max = validation["max"]
            variable = tk.DoubleVar(frame)
            variable.set(value)
            box = ttk.Spinbox(frame, textvariable=variable,
                              from_=value_min, to=value_max,
                              increment=0.1)
            box.grid(row=i, column=1)
        elif validation["type"] == str and "choices" in validation:
            variable = tk.StringVar(frame)
            variable.set(value)
            choices = validation["choices"]
            box = ttk.Combobox(frame, textvariable=variable, values=choices)
            box.grid(row=i, column=1, ipadx=1)
        elif validation["type"] == bool:
            variable = tk.BooleanVar(frame)
            variable.set(value)
            box = ttk.Checkbutton(frame, variable=variable)
            box.grid(row=i, column=1)
        elif validation["type"] == str and "exts" in validation:
            variable = tk.StringVar(frame)
            variable.set(value)
            label2 = ttk.Label(frame, textvariable=variable)
            label2.grid(row=i, column=1)
            box = ttk.Label(frame, textvariable=variable)
            box.grid(row=i, column=1)
            exts = validation["exts"]
            button = ttk.Button(frame, text="Find" if value is None else "Replace",
                                command=lambda: variable.set(
                                    _get_path(exts, self.window, value)))
            button.grid(row=i, column=2)

        return variable

    def _get_gui_config(self):
        return {
            k: v if k == "rounds"
            else ([v2.get() for v2 in v] if type(v) is list
                  else (RoundCredits(v, True) if type(v) is dict
                        else _nf(v.get())
                        )
                  )
            for k, v in self.components.items()}

    def add_source(self):
        path = _get_path(self.config.ITEMS["sources"]["exts"], self.window)
        if path != START_DIR:
            self.config.sources.append(path)
            self.redraw()

    def replace_source(self, index):
        path = _get_path(self.config.ITEMS["sources"]["exts"], self.window)
        if path != START_DIR:
            self.config.sources[index] = path
        self.components["sources"][index].set(path)

    def remove_source(self, index):
        self.config.sources.pop(index)
        self.redraw()

    def add_round(self):
        def _new_round(config):
            self.config.rounds.append(RoundConfig(config))
            self.redraw()
        RoundGUI(self.window, update=_new_round)

    def remove_round(self, index):
        self.config.rounds.pop(index)
        self.redraw()

    def add_audio_credit(self):
        self.config.credits.__dict__["audio"].append(AudioCredit())
        self.redraw()

    def remove_audio_credit(self, index):
        self.config.credits.audio.pop(index)
        self.redraw()

    def add_video_credit(self):
        self.config.credits.__dict__["video"].append(VideoCredit())
        self.redraw()

    def remove_video_credit(self, index):
        self.config.credits.video.pop(index)
        self.redraw()

    def redraw(self):
        raise NotImplementedError(
            "This is an abstract method and hasn't been overidden!")

    def draw(self):
        raise NotImplementedError(
            "This is an abstract method and hasn't been overidden!")

    def set_name(self, name: str):
        raise NotImplementedError(
            "This is an abstract method and hasn't been overidden!")


class GUI(AbstractGUI):
    def __init__(self, output_config: OutputConfig):
        super().__init__(ThemedTk(theme="equilux"), output_config)
        self.name = tk.StringVar(self.window)
        self.set_name(output_config.name)
        self._settings_path = output_config._settings
        self.window.tk_setPalette(
            background="grey30", foreground="grey85", selectColor="black", highlightColor="black")

        self.menubar = tk.Menu(self.window)
        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="Run", command=self.start)
        file_menu.add_command(label="Save", command=self.save)
        file_menu.add_command(label="Save As", command=self.save_as)
        file_menu.add_command(label="Exit", command=self.window.quit)
        self.menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(self.menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.about)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        self.window.config(menu=self.menubar)

        self.draw()
        self.window.mainloop()

    def redraw(self):
        for frame in self.main_frames:
            frame.destroy()
        self.bottom_frame.destroy()
        self.draw()
        self.window.update_idletasks()
        self.window.update()

    def draw(self):
        self.main_frames = self._generate_gui_elements()
        self.tabs.add(self.main_frames[0], text='Settings')
        self.tabs.add(self.main_frames[1], text='Rounds')
        self.tabs.grid(sticky="nesw")

        self.bottom_frame = ttk.Frame(self.window)
        self.bottom_frame.grid(sticky="nesw")
        quit_button = ttk.Button(self.bottom_frame, command=self.window.quit,
                                 text="Exit")
        quit_button.grid(row=0, column=0, sticky="w")
        save_button = ttk.Button(
            self.bottom_frame, command=self.save, text="Save")
        save_button.grid(row=0, column=1, sticky="ew")
        start_button = ttk.Button(
            self.bottom_frame, command=self.start, text="Start")
        start_button.grid(row=0, column=2, sticky="e")
        self.bottom_frame.columnconfigure(0, weight=1)
        self.bottom_frame.columnconfigure(1, weight=1)
        self.bottom_frame.columnconfigure(2, weight=1)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

    def about(self):
        pass

    def start(self):
        config = self._get_gui_config()
        config = OutputConfig(config, False)
        self.update_config(config)
        make(config)

    def save(self):
        if self._settings_path == "":
            return self.save_as()

        config = self._get_gui_config()
        config["_settings"] = self._settings_path
        self.update_config(config)
        self.config.save()

    def save_as(self):
        path = tk.filedialog.asksaveasfilename(
            initialdir=START_DIR,
            title="Save As",
            filetypes=[("YAML files", "*.yaml")]
        )
        config = self._get_gui_config()
        config["_settings"] = path
        self.update_config(config)
        self.config.save()

    def set_name(self, name: str):
        self.name.set(name)
        self.window.title("CHAP: {}".format(name))


class RoundGUI(AbstractGUI):
    def __init__(self, window: tk.Tk, round_config: RoundConfig = None, set_name=lambda n: None, update=None):
        self.window = tk.Toplevel(window)
        self.window.attributes("-topmost", True)
        super().__init__(self.window, round_config or RoundConfig({
            "duration": 0,
            "sources": [],
            "bpm": 120,
            "speed": 3
        }), update)

        def _set_name(name: str):
            self.config.name = name
            self.window.title("CHAP: Round {}".format(self.config.name))
            set_name(name)
        self.set_name = _set_name
        self.set_name(self.config.name)
        self.draw()

    def redraw(self):
        for frame in self.main_frames:
            frame.destroy()
        self.bottom_frame.destroy()
        self.draw()
        self.window.update_idletasks()
        self.window.update()

    def draw(self):
        self.main_frames = self._generate_gui_elements()
        self.tabs.add(self.main_frames[0], text='Config')
        self.tabs.add(self.main_frames[1], text='Sources')
        self.tabs.add(self.main_frames[2], text='Credits')
        self.tabs.grid(sticky="nesw")

        self.bottom_frame = ttk.Frame(self.window)
        cancel = ttk.Button(
            self.bottom_frame, command=self.window.destroy, text="Cancel")
        cancel.grid(row=0, column=0, sticky="w")
        ok = ttk.Button(self.bottom_frame, command=self.ok, text="Ok")
        ok.grid(row=0, column=2, sticky="e")
        self.bottom_frame.grid(sticky="nesw")
        self.bottom_frame.columnconfigure(0, weight=1)
        self.bottom_frame.columnconfigure(2, weight=1)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

    def ok(self):
        config = self._get_gui_config()
        self.update_config(config)
        self.set_name(config["name"])
        self.window.destroy()


def _get_path(exts, root, start=START_DIR):
    if exts == []:
        path = tk.filedialog.askdirectory(
            initialdir=start,
            title="Select a directory",
            parent=root
        )
    else:
        path = tk.filedialog.askopenfilename(
            initialdir=start,
            title="Select a file",
            filetypes=exts,
            parent=root
        )
    return path or start


def _nf(s: str):
    """None Filter"""
    return None if s == "None" else s
