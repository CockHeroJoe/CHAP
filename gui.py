import tkinter as tk
import tkinter.ttk as ttk
from ttkthemes import ThemedTk
from tkinter import filedialog
from functools import partial
import os.path

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

        self.window.geometry("800x600")

        def _update_config(new_config):
            config.__dict__.update(new_config
                                   if type(new_config) == dict
                                   else new_config.__dict__)
            self.config = config.copy()

        self.update_config = update or _update_config
        self.short_names = []

    def _generate_gui_elements(self):
        frames = [
            ttk.Frame(self.tabs),
            ScrollableFrame(self.tabs),
            ScrollableFrame(self.tabs)
        ]
        i = 0
        for attribute in self.config.ITEMS:
            value = self.config.__getattribute__(attribute)
            if attribute[0] == "_":
                continue
            elif (self.config.ITEMS.get("bmcfg") is not None
                    and self.config.bmcfg is not None
                    and attribute in ["bpm", "music", "duration"]):
                continue
            element = self._generate_gui_element(
                frames, attribute, value, i)
            if attribute not in ["rounds", "credits", "sources"]:
                self.components[attribute] = element
            i += len(element) + 2 if type(element) == list else 1

        frames[0].columnconfigure(1, weight=1)

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
            return RoundsTab(self, frame).draw()
        elif attribute == "sources":
            return SourcesTab(self, frame).draw()
        elif attribute == "credits":
            return CreditsTab(self, frame).draw()
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
            short_name_var = tk.StringVar(frame)
            short_name_var.set(value and os.path.basename(value))
            self.short_names.append(short_name_var)

            # TODO: if bmcfg is set, update round_config

            def find_or_replace():
                start_dir = os.path.dirname(value or ".")
                path = _get_path(exts, self.window, start_dir)
                if path == start_dir:
                    return
                variable.set(path)
                short_name_var.set(os.path.basename(path))
                if attribute == "bmcfg":
                    self.config.bmcfg = path
                    self.config.load_beatmeter_config()
                    self.redraw()

            box = ttk.Label(frame, textvariable=short_name_var)
            box.grid(row=i, column=1)
            exts = validation["exts"]
            button = ttk.Button(frame,
                                text="Find" if value is None else "Replace",
                                command=find_or_replace)
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
            for k, v in self.components.items()
        }

    def redraw(self):
        raise NotImplementedError(
            "This is an abstract method and hasn't been overridden!")

    def draw(self):
        raise NotImplementedError(
            "This is an abstract method and hasn't been overridden!")

    def set_name(self, name: str):
        raise NotImplementedError(
            "This is an abstract method and hasn't been overridden!")


class GUI(AbstractGUI):
    def __init__(self, output_config: OutputConfig):
        super().__init__(ThemedTk(theme="equilux"), output_config)
        self.name = tk.StringVar(self.window)
        self.set_name(output_config.name)
        self._settings_path = output_config._settings
        self.window.tk_setPalette(
            background="grey30",
            foreground="grey85",
            selectColor="black",
            highlightColor="black",
        )

        self.menubar = tk.Menu(self.window)
        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open)
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

    def open(self):
        path = _get_path([("YAML files", "*.yaml")], self.window)
        self._settings_path = path
        config = OutputConfig({"_settings": path}, True)
        self.config = config
        self.redraw()

    def start(self):
        config = self._get_gui_config()
        config["_settings"] = self._settings_path
        config = OutputConfig(config, False)
        self.update_config(config)
        self.window.destroy()
        make(config)

    def save(self):
        if self._settings_path == "":
            return self.save_as()

        config = self._get_gui_config()
        config["_settings"] = self._settings_path
        self.update_config(config)
        self.config.save()

    def save_as(self):
        path = filedialog.asksaveasfilename(
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
    def __init__(self,
                 window: tk.Tk,
                 round_config: RoundConfig = None,
                 set_name=lambda n: None,
                 update=None
                 ):
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
        path = filedialog.askdirectory(
            initialdir=start,
            title="Select a directory",
            parent=root
        )
    else:
        path = filedialog.askopenfilename(
            initialdir=start,
            title="Select a file",
            filetypes=exts,
            parent=root
        )
    return path or start


def _nf(s: str):
    """None Filter"""
    return None if s == "None" else s


class ScrollableFrame(ttk.Frame):
    # https://blog.tecladocode.com/tkinter-scrollable-frames/
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        canvas.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


class AbstractTab:
    def __init__(self, parent: AbstractGUI, frame: ScrollableFrame):
        self.parent = parent
        self.frame = frame.scrollable_frame
        self.sub_frame = ttk.Frame(self.frame)
        self.scrollbar = ttk.Scrollbar(self.frame)

    def draw(self):
        raise NotImplementedError(
            "This is an abstract method and hasn't been overridden!")

    def redraw(self):
        self.sub_frame.destroy()
        self.sub_frame = ttk.Frame(self.frame)
        self.draw()
        self.parent.window.update_idletasks()
        self.parent.window.update()


class RoundsTab(AbstractTab):
    def draw(self):
        value = self.parent.config.rounds
        value_list = []
        for v_i, v in enumerate(value):
            label = ttk.Label(self.sub_frame, text="{:02d}: ".format(v_i + 1))
            variable = tk.StringVar(self.sub_frame)
            variable.set(v.name)
            box = ttk.Button(
                self.sub_frame, command=partial(self.edit_round, v, variable),
                text="Edit")
            label.grid(row=v_i, column=0, padx=10, pady=3)
            label2 = ttk.Label(self.sub_frame, textvariable=variable)
            label2.grid(row=v_i, column=1)
            box.grid(row=v_i, column=2, padx=10, pady=3)
            value_list += [v.__dict__]
            box2 = ttk.Button(
                self.sub_frame,
                command=partial(self.remove_round, v_i),
                text="Remove")
            box2.grid(row=v_i, column=3)

        v_i = len(value_list)
        label = ttk.Label(
            self.sub_frame, text="{:02d}: ".format(len(value) + 1))
        label.grid(row=v_i, column=0, padx=10, pady=3)
        box = ttk.Button(self.sub_frame,
                         command=self.add_round,
                         text="Add")
        box.grid(row=v_i, column=1, padx=10, pady=3, sticky="w")
        self.sub_frame.grid(columnspan=4, rowspan=v_i+1, sticky="ew")
        self.parent.components["rounds"] = value_list

    def edit_round(self, config, variable):
        def _set_name(n: str): variable.set(n)
        RoundGUI(self.parent.window, config, _set_name)

    def add_round(self):
        def _new_round(config):
            self.parent.config.rounds.append(RoundConfig(config))
            self.redraw()
        RoundGUI(self.parent.window, update=_new_round)

    def remove_round(self, index):
        self.parent.config.rounds.pop(index)
        self.redraw()


class CreditsTab(AbstractTab):
    def draw(self):
        value = self.parent.config.credits
        value_dict = {"audio": [], "video": []}
        label = ttk.Label(self.sub_frame, text="Audio Credits",
                          font="Roboto 14 bold")
        label.grid(columnspan=5, pady=10)

        audio_frame = ttk.Frame(self.sub_frame)
        for v_i, v in enumerate(value.audio):
            label = ttk.Label(audio_frame, text="{:02d}:".format(v_i+1))
            label.grid(row=2*v_i, column=0, padx=10, pady=3)

            box3 = ttk.Button(
                audio_frame,
                command=partial(self.remove_audio_credit, v_i),
                text="Remove")
            box3.grid(row=2*v_i, column=4, sticky="e", padx=10, pady=3)

            artist_variable = tk.StringVar(audio_frame)
            artist_variable.set(v.artist)
            label2 = ttk.Label(audio_frame, text="Artist")
            label2.grid(row=2*v_i, column=1, padx=10, pady=3)
            box = ttk.Entry(audio_frame, textvariable=artist_variable)
            box.grid(row=2*v_i, column=2, padx=10, pady=3)

            song_variable = tk.StringVar(audio_frame)
            song_variable.set(v.song)
            label3 = ttk.Label(audio_frame, text="Song")
            label3.grid(row=2*v_i+1, column=1, padx=10, pady=3)
            box2 = ttk.Entry(audio_frame, textvariable=song_variable)
            box2.grid(row=2*v_i+1, column=2, padx=10, pady=3)

            value_dict["audio"] += [{"artist": artist_variable,
                                     "song": song_variable}]

        length = len(value_dict["audio"])
        label = ttk.Label(audio_frame,
                          text="{:02d}:".format(length+1))
        label.grid(row=2*length, column=0, padx=10, pady=3)
        box = ttk.Button(
            audio_frame, command=self.add_audio_credit, text="Add")
        box.grid(row=2*length, column=1, padx=10, pady=3, sticky="w")
        audio_frame.grid(sticky='ew', rowspan=2*length+1)

        label = ttk.Label(self.sub_frame, text="Video Credits",
                          font="Roboto 14 bold")
        label.grid(columnspan=5, pady=10)
        video_frame = ttk.Frame(self.sub_frame)
        grid_row = 0
        for v_i, v in enumerate(value.video):
            label = ttk.Label(video_frame,
                              text="{:02d}:".format(v_i+1))
            label.grid(row=grid_row, column=0, padx=10, pady=3)

            box7 = ttk.Button(
                video_frame,
                command=partial(self.remove_video_credit, v_i),
                text="Remove")
            box7.grid(row=grid_row, column=4, padx=10, pady=3)

            studio_variable = tk.StringVar(video_frame)
            studio_variable.set(v.studio)
            label2 = ttk.Label(video_frame, text="Studio")
            label2.grid(row=grid_row, column=1, padx=10, pady=3)
            box = ttk.Entry(video_frame, textvariable=studio_variable)
            box.grid(row=grid_row, column=2, padx=10, pady=3)
            grid_row += 1

            title_variable = tk.StringVar(video_frame)
            title_variable.set(v.title)
            label3 = ttk.Label(video_frame, text="Title")
            label3.grid(row=grid_row, column=1, padx=10, pady=3)
            box2 = ttk.Entry(video_frame, textvariable=title_variable)
            box2.grid(row=grid_row, column=2, padx=10, pady=3)
            grid_row += 1

            date_variable = tk.StringVar(video_frame)
            date_variable.set(v.date)
            label4 = ttk.Label(video_frame, text="Date")
            label4.grid(row=grid_row, column=1, padx=10, pady=3)
            box3 = ttk.Entry(video_frame, textvariable=date_variable)
            box3.grid(row=grid_row, column=2, padx=10, pady=3)
            grid_row += 1

            label5 = ttk.Label(video_frame, text="Performers")
            label5.grid(row=grid_row, column=1, padx=10, pady=3)
            performer_variables = []
            for p_i, performer in enumerate(v.performers):
                performer_variable = tk.StringVar(video_frame)
                performer_variable.set(performer)
                box4 = ttk.Entry(video_frame, textvariable=performer_variable)
                box4.grid(row=grid_row, column=2, padx=10, pady=3)
                box5 = ttk.Button(video_frame,
                                  command=partial(
                                      self.remove_performer, v_i, p_i),
                                  text="Remove")
                box5.grid(row=grid_row, column=3, padx=10, pady=3)
                performer_variables.append(performer_variable)
                grid_row += 1
            box6 = ttk.Button(video_frame,
                              command=partial(self.add_performer, v_i),
                              text="Add")
            box6.grid(row=grid_row, column=2, padx=10, pady=3, sticky="w")
            grid_row += 1

            value_dict["video"] += [{
                "studio": studio_variable,
                "title": title_variable,
                "date": date_variable,
                "performers": performer_variables,

            }]

        length = len(value_dict["video"])
        label = ttk.Label(video_frame, text="{:02d}:".format(length+1))
        label.grid(row=grid_row, column=0, padx=10, pady=3)
        box = ttk.Button(
            video_frame, command=self.add_video_credit, text="Add")
        box.grid(row=grid_row, column=1, padx=10, pady=3)
        video_frame.grid(sticky='ew', rowspan=4*len(value_dict["video"])+1)
        self.sub_frame.grid(columnspan=4,
                            rowspan=2*len(value_dict["audio"])+grid_row+2,
                            sticky="ew")

        self.parent.components["credits"] = value_dict

    def add_audio_credit(self):
        self.parent.config.credits.__dict__["audio"].append(AudioCredit())
        self.redraw()

    def remove_audio_credit(self, index):
        self.parent.config.credits.audio.pop(index)
        self.redraw()

    def add_video_credit(self):
        self.parent.config.credits.__dict__["video"].append(VideoCredit())
        self.redraw()

    def remove_video_credit(self, index):
        self.parent.config.credits.video.pop(index)
        self.redraw()

    def add_performer(self, video_index):
        self.parent.config.credits.video[video_index].performers.append("")
        self.redraw()

    def remove_performer(self, video_index, performer_index):
        self.parent.config.credits.video[video_index].performers.pop(
            performer_index)
        self.redraw()


class SourcesTab(AbstractTab):
    def draw(self):
        self.short_paths = []
        value = self.parent.config.sources
        value_list = []
        for v_i, v in enumerate(value):
            label = ttk.Label(self.sub_frame, text="{:02d}: ".format(v_i + 1))
            variable = tk.StringVar(self.sub_frame)
            variable.set(v)
            self.short_paths.append(tk.StringVar(self.sub_frame))
            self.short_paths[-1].set(os.path.basename(v))
            label.grid(row=v_i, column=0, padx=10, pady=3)
            label2 = ttk.Label(
                self.sub_frame,
                textvariable=self.short_paths[-1]
            )
            label2.grid(row=v_i, column=1, padx=10, pady=3, sticky="w")
            box = ttk.Button(self.sub_frame,
                             command=partial(self.replace_source, v_i),
                             text="Replace")
            box.grid(row=v_i, column=2, padx=10, pady=3)
            box2 = ttk.Button(
                self.sub_frame,
                command=partial(self.remove_source, v_i),
                text="Remove")
            box2.grid(row=v_i, column=3, padx=10, pady=3)
            value_list += [variable]

        v_i = len(value_list)
        label = ttk.Label(
            self.sub_frame, text="{:02d}: ".format(len(value) + 1))
        label.grid(row=v_i, column=0, padx=10, pady=3)
        variable = tk.StringVar(self.sub_frame)
        box = ttk.Button(self.sub_frame,
                         command=self.add_source,
                         text="Add")
        box.grid(row=v_i, column=1, padx=10, pady=3, sticky="w")

        self.sub_frame.grid(columnspan=4, rowspan=v_i+1, sticky="ew")
        self.parent.components["sources"] = value_list

    def add_source(self):
        path = _get_path(
            self.parent.config.ITEMS["sources"]["exts"], self.parent.window)
        if path != START_DIR:
            self.parent.config.sources.append(path)
            self.redraw()

    def replace_source(self, index):
        path = _get_path(
            self.parent.config.ITEMS["sources"]["exts"], self.parent.window)
        if path != START_DIR:
            self.parent.config.sources[index] = path
        self.parent.components["sources"][index].set(path)
        self.short_paths[index].set(os.path.basename(path))

    def remove_source(self, index):
        self.parent.config.sources.pop(index)
        self.redraw()
