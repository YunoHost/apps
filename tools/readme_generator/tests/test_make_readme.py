import os
import tempfile
import subprocess

from pathlib import Path

CWD = Path(os.path.split(os.path.realpath(__file__))[0])
COMMIT_ID = "8f788213b363a46a5b6faa8f844d86d4adac9446"


def test_running_make_readme():
    with tempfile.TemporaryDirectory() as name:
        name = Path(name)
        DIRECTORY = name / "gotosocial_ynh"

        subprocess.check_call(
            [
                "git",
                "clone",
                "https://github.com/yunohost-apps/gotosocial_ynh",
                DIRECTORY,
                "-q",
            ]
        )
        subprocess.check_call(["git", "checkout", COMMIT_ID, "-q"], cwd=DIRECTORY)

        print(CWD)
        subprocess.check_call([CWD / "../make_readme.py", DIRECTORY])

        assert open(CWD / "README.md").read() == open(DIRECTORY / "README.md").read()
        assert (
            open(CWD / "README_fr.md").read() == open(DIRECTORY / "README_fr.md").read()
        )


if __name__ == "__main__":
    test_running_make_readme()
