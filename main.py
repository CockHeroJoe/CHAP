#! /usr/bin/env python3

from parsing import OutputConfig, parse_command_line_args
from gui import GUI

#from moviepy.config import change_settings
#change_settings({"IMAGEMAGICK_BINARY": r"C:\\Program Files\\ImageMagick-7.0.10-Q16-HDRI\\magick.exe"})


def main():
    output_config = OutputConfig(parse_command_line_args())
    GUI(output_config)


if __name__ == "__main__":
    main()
