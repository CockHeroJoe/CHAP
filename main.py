#! /usr/bin/env python3
import os

from moviepy.config import change_settings

from parsing import OutputConfig, parse_command_line_args
from gui import GUI


# Overrride moviepy resolution bug
if os.name == "nt":
    import winreg as wr 
    key = wr.OpenKey(wr.HKEY_LOCAL_MACHINE, "SOFTWARE\\ImageMagick\\Current")
    binary = wr.QueryValueEx(key, "BinPath")[0] + "\\magick.exe"
    key.Close()
    change_settings({"IMAGEMAGICK_BINARY": binary})


def main():
    output_config = OutputConfig(parse_command_line_args())
    GUI(output_config)


if __name__ == "__main__":
    main()
