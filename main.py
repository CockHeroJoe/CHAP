#! /usr/bin/env python3
import os

from moviepy.config import change_settings as moviepy_change_settings

from parsing import OutputConfig, parse_command_line_args
from gui import GUI


# Override moviepy's binary filepath resolution bug in Windows
if os.name == "nt":
    import winreg as wr
    try:
        with wr.OpenKey(
                wr.HKEY_LOCAL_MACHINE,
                "SOFTWARE\\ImageMagick\\Current") as key:
            binary = wr.QueryValueEx(key, "BinPath")[0] + "\\magick.exe"
            moviepy_change_settings({"IMAGEMAGICK_BINARY": binary})
    except OSError:
        print(OSError)
        print("\nIs ImageMagic Installed?\n")
        exit(1)


def main():
    output_config = OutputConfig(parse_command_line_args())
    GUI(output_config)


if __name__ == "__main__":
    main()
