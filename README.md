# CHAP
Cock Hero Assembly Program

## Overview

This utility seeks to automate most of the creation process for "Cock Hero" videos. 

The process to create a video is:
- Download and [install this program](#Install).
- Download and install the [Beatmeter Generator](https://gitlab.com/SklaveDaniel/BeatmeterGenerator/).
- Download video for each round (about 5-10 videos *per round*).
- Download music for each round (about 10 songs total, one per round).
- Convert all music to `wav`s (you can use [this](https://online-audio-converter.com/))
    and organise one song per folder.
- For each song, manually create beat tracks and generate sound and images with the Beatmeter Generator 
    (organizing these outputs is why you want separate folders for each song).
- Create round config files for each round from the [example](docs/rooster_round01.yaml) ([more info](#round-config-files)).
- Run the Cock Hero Assembly Program with the round config filenames as arguments ([more info](#usage)).
- If mutltiple versions are generated for each clip (`--versions` is more than 1), select your prefered version 
        for each clip, using the GUI that pops up. **Note**: 4K inputs are *very* slow to preview.
- Wait (this may take several hours).
- Enjoy the final output video!

This is a work-in-progress. If you find a bug or would like a new feature, please see the [contributing section](#contributing).

## Example Output

Generated with `./main.py -s docs/rooster.yaml` 

!["Rooster Hero"](rooster-hero.gif)

Free Stock footage of roosters from [Videezy](http://www.videezy.com)

## Usage

The `main` program takes 1 or more [Round Config Files](#round-config-files) as the positional arguments.

Individual rounds are output by default, but are assembled into a complete video with a title screen,
round transitions and credits, if the `--assemble` (AKA `-a`) option is used.

### Example Invocations

- Use default settings and *don't assemble* 3-round video
    ```
    CHAP/main.py -o <YOUR_PROJECT_NAME> round01.yaml round02.yaml round03.yaml
    ```
- Use default settings and *assemble* 3-round video
    ```
    CHAP/main.py -ao <YOUR_PROJECT_NAME> round01.yaml round02.yaml round03.yaml
    ```
- Use default settings and *assemble* 3-round video from multiple versions
    ```
    CHAP/main.py -ao <YOUR_PROJECT_NAME> -v 4 round01.yaml round02.yaml round03.yaml
    ```
- Output in 4K at 60 FPS and assemble 2-round video
    ```
    CHAP/main.py -a -x 3840 -y 2160 -f 60 -o <YOUR_PROJECT_NAME> round01.yaml round02.yaml
    ```
- Assemble video from all rounds in folder "/path/to/rounds/"
    ```
    CHAP/main.py -ao <YOUR_PROJECT_NAME> /path/to/rounds/round*.yaml
    ```
- Provide options and poitional arguments with settings file instead
    ```
    CHAP/main.py -s /path/to/settings.yaml
    ```  

### Options

Any option that can be passed in through the command line can be passed in through the 
`--settings` option (as the path to a `.yaml` text file) instead. See [example](docs/rooster.yaml).

- `-x` or `--xdim`: The output width (in pixels) of generated video, default 1920
- `-y` or `--ydim`: The output height (in pixels) of generated video, default 1080
- `-f` or `--fps`: The output framerate (in frames per second) of generated video, default 30
- `-o` or `--output`: The output basename for generated video(s), default "Random XXXX"
- `-v` or `--versions`: The number of [versions](#versions) of each clip, default 1 (not displayed)
- `-r` or `--raw`: Output videos in as raw (uncompressed) `.avi` files with `png` codec
- `-a` or `--assemble`: Assemble generated rounds into full video (with title, transitions, 
    credit roll), default False
- `-c` or `--cache`: How often to save output videos:
    - default: "round" degrades quality slightly, but crashes only lose 1 round at most 
        (see  [recovery](#recovery)). Use with `--raw` to avoid quality degradation, if you have 
        enough disk space
    - option: "all" uses tonnes of memory (many gigs per round) and will crash on big projects
- `-d` or `--delete`: Delete intermediate files after assembly (if on), default False
- `-s` of `--settings`: Overrides all command-line options by supplying them in a text file

## Install

- Install Python 3
- Install [pygame](https://www.pygame.org/wiki/GettingStarted)
- Download CHAP source code and install it
    ```
    git clone https://github.com/CockHeroJoe/CHAP
    pip3 install -r CHAP/requirements.txt
    ```
- Configure ImageMagic to [allow for larger images](https://stackoverflow.com/questions/52075013/increasing-imagicks-max-resolution)

## Round Config Files

Each round is described by a `yaml` file. See the [example](docs/rooster_round01.yaml) for an example.

### Required Fields
- `duration`: The duration in seconds of the round (should match song length)
- `sources`: A list of paths for the source video files

### Optional Fields
- `name`: The name of the round, displayed during transitions between rounds
- `speed`: Number between 1 and 5 denoting how often cuts are made (default 3)
- `music`: The music track (filepath) to be played during the round
- `beats`: A sound file (filepath) with the click sound for the beats
    - typically generated by the [Beatmeter Generator](https://gitlab.com/SklaveDaniel/BeatmeterGenerator/)
- `beatmeter`: A folder full of an image sequence (organized by name) for the beats
    - typically generated by the [Beatmeter Generator](https://gitlab.com/SklaveDaniel/BeatmeterGenerator/)
- `bpm`: The overall bpm of the music track supplied in music field
- `audio_level`: Multiplier of original audio volume (fraction between 0 and infinity)
- `credits`: Information about sources and music fields
    - `audio`: Credit metadata about music sources (songs)
        - `artist`: The song's artist
        - `song`: The song's name
    - `video`: Credit metadata about video sources
        - `studio`: The production company / studio that filmed this video
        - `date`: The date the video was released
        - `title`: The title of this video
        - `performers`: A list of the performers (actors/stars) in this video

## Features

### Versions

This command-line option allows you to customize the random clips that are chosen.
- A GUI will open with the number of versions selected 
    (**Note**: exactly 1, 4, or 9 versions only recommended).
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

**Note**: Saving disabled by the `--cache`=`all` option.

Repeating the same compilation from the same working directory should only create new rounds. 
Rounds with the same name (each determined by `--output` and the filename of the round config `yaml`)
are reloaded. 

To replace a round, simply delete the unwanted round video (E.G. "Rooster Hero_r01.mp4")
before re-running the script.

### Credits

Credits data is optionally included in Round Config `.yaml`s. 

If any round has some credits data, then a scrolling credits screen will be added onto the final
output video, if the `--assemble` option is active.

Each field in a credit is optional, but if an field exists, then it should be full of data.
The fields are each processed as strings, including date, so any value is fine.

## Contributing

A direct PR to the `main` branch is fine, as is starting an issue on the issue tracker.
