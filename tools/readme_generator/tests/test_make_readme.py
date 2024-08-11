#!/usr/bin/env python3

import tempfile
import subprocess

from pathlib import Path

TEST_DIRECTORY = Path(__file__).resolve().parent

TEST_APP_NAME = "gotosocial_ynh"
TEST_APP_REPO = "https://github.com/yunohost-apps/gotosocial_ynh"
TEST_APP_COMMIT_ID = "8f788213b363a46a5b6faa8f844d86d4adac9446"


def test_running_make_readme():
    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)
        temporary_tested_app_directory = tempdir / TEST_APP_NAME

        subprocess.check_call(
            ["git", "clone", "-q", TEST_APP_REPO, temporary_tested_app_directory]
        )
        subprocess.check_call(
            ["git", "checkout", "-q", TEST_APP_COMMIT_ID],
            cwd=temporary_tested_app_directory,
        )

        # Now run test...
        subprocess.check_call(
            [
                TEST_DIRECTORY.parent / "make_readme.py",
                "-l",
                TEST_DIRECTORY.parent.parent.parent,
                temporary_tested_app_directory,
            ]
        )

        assert (
            open(TEST_DIRECTORY / "README.md").read()
            == open(temporary_tested_app_directory / "README.md").read()
        )


if __name__ == "__main__":
    test_running_make_readme()
