#!/usr/bin/env python3

import difflib
import tempfile
import subprocess

from pathlib import Path

CWD = Path(__file__).resolve().parent

TEST_APP_NAME = "gotosocial_ynh"
TEST_APP_REPO = "https://github.com/yunohost-apps/gotosocial_ynh"
TEST_APP_COMMIT_ID = "8f788213b363a46a5b6faa8f844d86d4adac9446"


def diff_files(file_a: Path, file_b: Path) -> bool:
    lines_a = file_a.open(encoding="utf-8").readlines()
    lines_b = file_b.open(encoding="utf-8").readlines()

    diffs = list(
        difflib.unified_diff(
            lines_a, lines_b, fromfile="README.before.md", tofile="README.after.md"
        )
    )
    print("".join(diffs))
    return len(diffs) == 0


def test_running_make_readme():
    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)
        DIRECTORY = tempdir / TEST_APP_NAME

        subprocess.check_call(["git", "clone", "-q", TEST_APP_REPO, DIRECTORY])
        subprocess.check_call(
            ["git", "checkout", "-q", TEST_APP_COMMIT_ID], cwd=DIRECTORY
        )

        # Now run test...
        subprocess.check_call([CWD.parent / "make_readme.py", DIRECTORY])

        assert diff_files(CWD / "README.md", DIRECTORY / "README.md")
        assert diff_files(CWD / "README_fr.md", DIRECTORY / "README_fr.md")


if __name__ == "__main__":
    test_running_make_readme()
