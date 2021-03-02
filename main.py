#! /usr/bin/env python3
import os

from moviepy.config import change_settings as moviepy_change_settings

from parsing import OutputConfig, parse_command_line_args
from gui import GUI
from run import make


# Override moviepy's binary filepath resolution bug in Windows
if os.name == "nt":
    import winreg as wr  # pylint: disable=import-error
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
    args = parse_command_line_args()
    output_config = OutputConfig(args)
    if args.execute:
        make(output_config)
    else:
        GUI(output_config)


if __name__ == "__main__":
    main()
