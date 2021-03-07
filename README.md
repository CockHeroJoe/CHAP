# CHAP

Cock Hero Assembly Program

## Overview

This utility seeks to automate most of the creation process for "Cock Hero" videos.

## Example Output

Generated with [`docs/rooster.yaml`](rooster.yaml) configuration file.

!["Rooster Hero"](rooster-hero.gif)

Free Stock footage of roosters from [Videezy](http://www.videezy.com)
Public Domain music (The Entertainer) from [YouTube](https://youtu.be/fPmruHc4S9Q)

## Usage

The process to create a video is:

- Download and [install this program](#Install).
- Download and install the [Beatmeter Generator](https://gitlab.com/SklaveDaniel/BeatmeterGenerator/).
- Download and install [FFMpeg](https://ffmpeg.org/)
- Download video for each round (about 1-10 videos _per round_).
- Download music for each round (about 3-15 songs total, one per round).
- Convert all music to `wav`s (you can use [this](https://online-audio-converter.com/)).
- For each song, manually create beat tracks with the Beatmeter Generator:
  - Save config file in a reasonable folder (ideally one folder per round).
    - Save as `ARTIST.NAME-SONG.NAME-CREATION.DATE.bmcfg.json`, ideally.
    - This name format should make sharing these files easier.
  - Generate audio and video in a (the same, preferably) reasonable folder.
    - Name the beat track: `beat_track.wav`, ideally.
    - Name the subfolder for the beatmeter video's images `beats`, ideally.
    - Any other names will require those names to be manually selected later.
- Run the Cock Hero Assembly Program:
  - Select resolution, framerate for output.
  - Activate `assemble`.
  - Add the rounds:
    - Name the round something unique (don't have two rounds with the same name).
    - Set the `speed` and `cut` type.
    - Select the `bmcfg`, the beatmeter config JSON file generated by the Beatmeter Generator.
    - Add the source files.
    - Add credits for sources, if desired.
  - If you have enough CPU power and time, select `versions` = 4 or 9:
    - Multiple versions will be generated for each clip, when running.
    - A preview window will pop up for each clip, allowing you to choose your preferred version.
    - **Note**: 4K inputs are _very_ slow to preview!
  - If you have enough memory, set `threads` to the number of CPU cores that your machine has.
    - **Note**: 4K inputs may require more than 4GB per round minute per thread!
  - Save the configuration.
  - Run:
    - If `versions` is more than 1, select your preferred version of each clip.
      - Use keyboard or mouse to select version.
      - See [preview controls](#Preview-Controls) for details.
      - **Note** if multiple `versions` and `cache` is not `all`,
        then you may have to wait after each version for round video to be written
        before the next round's clips are previewed, depending on `threads`.
  - Wait (this may take several hours).
- Enjoy the final output video!

This is a work-in-progress. If you find a bug or would like a new feature, please see the [contributing section](#contributing). There is no guarantee that your concern will be addressed, but if it is legitimate and novel, filing an issue / bug report will be appreciated.

## Preview Controls

When the preview GUI is active, simply click the version desired, or exit the GUI to disable version selection and previewing for this round.

The following keyboard shortcuts allow you to control playback:

- `Space`: play/pause the video
- `1`, `2`, ...: select version (left-to-right, rows, top-to-bottom, starting at 1)
- `Left`/`Right`: Scrub backwards/forwards through video:
  - if paused, scrub frame-by-frame
  - if playing, scrub 5 seconds at a time
- `Escape`: same as exiting window (stop previewing, switch to 1 version)

## Install

### Using Windows Installer

Download the [installer]("https://github.com/CockHeroJoe/CHAP/releases/download/v2.0.2-alpha/CHAP.msi") and run it.

### From Source

- Install Python 3, version 3.4 or greater
- Download CHAP source code and install it
  ```
  git clone https://github.com/CockHeroJoe/CHAP
  pip3 install -r CHAP/requirements.txt
  ```
- Configure ImageMagic to [allow for larger images](https://stackoverflow.com/questions/52075013/increasing-imagicks-max-resolution)

## Advanced Usage

All features and options accessible via the main GUI are also accessible via the CLI.

To disable the GUI, use the `-e` (`--execute`) flag.

**Note**

Using the `assemble` option is convenient, but very slow. Instead, once all rounds and transitions are output, use ffmpeg to concatenate them together:

```
ffmpeg -f concat -safe 0 -i input.txt -c copy output.mp4
```

The `input.txt` file (that you must create) is simply a list of all the round files in the desired order. It looks like this:

```
file 'MyVideo_Title.mp4'
file 'MyVideo_Round1_Title.mp4'
file 'MyVideo_Round1.mp4'
...
file 'MyVideo_Round1_Title.mp4'
file 'MyVideo_RoundN.mp4'
file 'MyVideo_Credits.mp4'
```

### Configuration Files

Configuration file(s) (of `yaml` format) can be manually prepared and edited.
For power users, this may be faster than using the GUI. See [example](docs/rooster.yaml) settings config.

A Cock Hero video is defined by a top-level `settings.yaml` as well as many optional `round_config.yaml`s.
The contents of each `round_config.yaml` may be included directly in the `settings.yaml`, or their paths may be listed instead. All paths may be relative (to the config file containing them) or absolute.

#### Settings Configuration Files

The `settings.yaml` configuration file is optional. The same options can be directly passed in as command-line arguments. Command-line arguments overwrite those given in the configuration file.

For a list of allowed options and values, see [Command Line Options](#Command-Line-Options).

A `settings.yaml` configuration file can be generated and saved from the GUI (although it is more verbose, repetitive, and not as human readable).

#### Round Configuration Files

Each round is described by a `yaml` file. See the [example](docs/rooster_round01.yaml) for an example.

A round consists of a song and some videos, beats and beatmeter, as well as other metadata.

##### Required Fields

- `sources`: A list of paths for the source video files
- `duration`: The duration in seconds of the round (should match song length, usually)
  - **NOTE**: This is not required (and is _ignored_ and _overridden_) if `bmcfg` is set

##### Recommended Fields

- `name`: The name of the round, displayed during transitions between rounds
- `speed`: Number between 1 and 5 denoting how often cuts are made (default 3)
- `audio_level`: Multiplier of sources' audio volume (fraction between 0 and infinity)
- `credits`: Information about sources and music fields
  - `audio`: Credit metadata about music sources (songs)
    - `artist`: The song's artist
    - `song`: The song's name
  - `video`: Credit metadata about video sources
    - `studio`: The production company / studio that filmed this video
    - `date`: The date the video was released
    - `title`: The title of this video
    - `performers`: A list of the performers (actors/stars) in this video
- `bmcfg`: A JSON file describing the beatmeter
  - generated by the [Beatmeter Generator](https://gitlab.com/SklaveDaniel/BeatmeterGenerator/)
  - **Note**: This file makes all of the _following options redundant_ as well as `duration`

##### Optional Fields, made redundant by `bmcfg`

- `music`: The music track (filepath) to be played during the round
- `beats`: A `.wav` sound file (filepath) with the click sound for the beats (default `beat_track.wav`)
  - typically generated by the [Beatmeter Generator](https://gitlab.com/SklaveDaniel/BeatmeterGenerator/)
- `beatmeter`: A folder full of an image sequence (organized by name) for the beats (default `beats`)
  - typically generated by the [Beatmeter Generator](https://gitlab.com/SklaveDaniel/BeatmeterGenerator/)
- `bpm`: The overall bpm of the music track supplied in music field

### Command-line Options

- `-h` or `--help`: Display help message and exit
- `-s` or `--settings`: Supplies command-line options in a text file
- `-x` or `--xdim`: The output width (in pixels) of generated video, default 1920
- `-y` or `--ydim`: The output height (in pixels) of generated video, default 1080
- `-f` or `--fps`: The output framerate (in frames per second) of generated video, default 60
- `-n` or `--name`: The title of your video and output basename for generated video(s), default "Random XXXX"
- `-v` or `--versions`: The number of [versions](#versions) of each clip, default 1 (no preview)
- `-r` or `--raw`: Output videos as "raw" `.avi` files with `png` codec, default False
- `-a` or `--assemble`: Assemble generated rounds into full video (with title, transitions,
  credit roll), default False
- `-c` or `--cache`: How often to save output videos, default: "round":
  - "round": Save each round to disk after it is prepared, as well as transitions, title and credits
    - Saves memory and allows for faster processing, with multiple `--threads`
    - Allows for [recovery](#recovery) in case of crashes
  - "all": Store all videos in memory until final output
    - Saves disk space may be faster in the case that `--threads` is 1
    - Uses tonnes of memory (many gigs per round) and will crash on big projects
- `-t` or `--threads`: Sets number of concurrent threads to process rounds with, default 1
- `-d` or `--delete`: Delete intermediate files after assembly, default False
- `-e` or `--execute`: Skip main GUI and immediately execute assembly program, default False
- `rounds`: list of `round_config.yaml` filenames

### Example Invocations

- Use default settings and _don't assemble_ 3-round video
  ```
  CHAP/main.py -n <YOUR_PROJECT_NAME> round01.yaml round02.yaml round03.yaml
  ```
- Use default settings and _assemble_ 3-round video
  ```
  CHAP/main.py -an <YOUR_PROJECT_NAME> round01.yaml round02.yaml round03.yaml
  ```
- Use default settings and _assemble_ 3-round video from multiple versions
  ```
  CHAP/main.py -an <YOUR_PROJECT_NAME> -v 4 round01.yaml round02.yaml round03.yaml
  ```
- Output in 4K at 60 FPS and assemble 2-round video
  ```
  CHAP/main.py -a -x 3840 -y 2160 -f 60 -n <YOUR_PROJECT_NAME> round01.yaml round02.yaml
  ```
- Assemble video from all rounds in folder "/path/to/rounds/"
  ```
  CHAP/main.py -an <YOUR_PROJECT_NAME> /path/to/rounds/round*.yaml
  ```
- Provide options and positional arguments with settings file instead
  ```
  CHAP/main.py -s /path/to/settings.yaml
  ```

## Features

### Versions

This option allows you to customize the random clips that are chosen.

- A GUI will open with the number of versions selected
  (**Note**: exactly 1, 4, or 9 versions ONLY recommended).
- The clips will be previewed in the GUI, on repeat until one is chosen.
- Choose which version/clip is included by clicking on it or using the number keys
  <kbd>1</kbd> - <kbd>9</kbd> corresponding to the position from top left:
  |**1**|**2**|
  |-|-|
  |**3**|**4**|
- If preview window is exited or <kbd>Esc</kbd> is hit, the rest of the clips
  will be selected without user input (no more GUI / one version).
- The final output video will include only the clips selected.

### Recovery

**Note**: Saving and recovery are disabled by the `cache`=`all` option.

Repeating the same compilation from the same working directory should only create new rounds.
Rounds with the same name (each determined by `output` and the filename of the round config `yaml`)
are reloaded.

To replace a round, simply delete the unwanted round video (E.G. "Rooster Hero_r01.mp4")
before re-running the script.

### Credits

Credits data is optionally included in Round Config `.yaml`s.

If any round has some credits data, then a scrolling credits screen will be added onto the final
output video, if the `assemble` option is active.

Each field in a credit is optional, but if an field exists, then it should be full of data.
The fields are each processed as strings, including date, so any value is fine.

## Contributing

A direct PR to the `main` branch is fine, as is starting an issue on the issue tracker.
