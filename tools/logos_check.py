#!/usr/bin/env python3

import sys
import argparse
from pathlib import Path

from PIL import Image


class ImageCheck():
    def __init__(self, imgpath: Path) -> None:
        self.imgpath = imgpath
        self.image = Image.open(imgpath)

        self.fails: list[str] = []

    def check(self) -> bool:
        self.fails.clear()
        for fn_name in dir(self):
            if fn_name.startswith("check_"):
                getattr(self, fn_name)()

        if not self.fails:
            return True

        print(f"Image '{self.imgpath}' failed tests:")
        for fail in self.fails:
            print(f"  - {fail}")
        print()
        return False

    def check_type(self) -> None:
        format = self.image.format.lower()
        accepted_formats = ["png", "jpeg", "webp"]
        if format not in accepted_formats:
            self.fails.append(f"Image should be one of {', '.join(accepted_formats)} but is {format}")

    def check_dimensions(self) -> None:
        dim_min, dim_max = 96, 300
        dimensions_range = range(dim_min, dim_max+1)
        w, h = self.image.width, self.image.height
        if w not in dimensions_range or h not in dimensions_range:
            self.fails.append(f"Dimensions should be in [{dim_min}, {dim_max}] but are {w}×{h}")

    def check_ratio(self) -> None:
        w, h = self.image.width, self.image.height
        if w != h:
            self.fails.append(f"Image is not square but {w}×{h}")

    def check_filesize(self) -> None:
        filesize = self.imgpath.stat().st_size
        max_size = 80_000
        if filesize > max_size:
            self.fails.append(f"Filesize should be <={max_size/1000}kB but is {filesize/1000}kB")

    def check_compressed(self) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("logos", nargs="+", type=Path, help="Logos to check")
    args = parser.parse_args()

    total_result = True
    for logo in args.logos:
        checker = ImageCheck(logo)
        if checker.check() is not True:
            total_result = False

    if not total_result:
        sys.exit(1)

if __name__ == "__main__":
    main()
