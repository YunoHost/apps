import time
import json
import os
import shlex
import asyncio
import tempfile
import requests

from make_readme import generate_READMEs
from pathlib import Path

github_webhook_secret = open("github_webhook_secret", "r").read().strip()

login = open("login").read().strip()
token = open("token").read().strip()

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"
my_env["GIT_AUTHOR_NAME"] = "yunohost-bot"
my_env["GIT_AUTHOR_EMAIL"] = "yunohost@yunohost.org"
my_env["GIT_COMMITTER_NAME"] = "yunohost-bot"
my_env["GIT_COMMITTER_EMAIL"] = "yunohost@yunohost.org"


async def git(cmd, in_folder=None):
    if not isinstance(cmd, list):
        cmd = cmd.split()

    if in_folder:
        cmd = ["-C", in_folder] + cmd

    cmd = ["git"] + cmd
    cmd = " ".join(map(shlex.quote, cmd))
    print(cmd)

    command = await asyncio.create_subprocess_shell(
        cmd,
        env=my_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    data = await command.stdout.read()

    return data.decode().strip()


async def regen_readme(repository, branch):

    print()
    print(f"{repository} -> branch '{branch}'")
    print("=" * len(f"{repository} -> branch '{branch}'"))

    branches = requests.get(
        f"https://api.github.com/repos/{repository}/branches",
        headers={
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github+json",
        }
    ).json()

    branches = {x["name"] for x in branches}
    if "testing" in branches:
        branch = "testing"

    with tempfile.TemporaryDirectory() as folder:
        await git(
            [
                "clone",
                f"https://{login}:{token}@github.com/{repository}",
                "--single-branch",
                "--branch",
                branch,
                folder,
            ]
        )

        generate_READMEs(Path(folder))

        await git(["add", "README*.md"], in_folder=folder)
        await git(["add", "ALL_README.md"], in_folder=folder)

        diff_not_empty = await asyncio.create_subprocess_shell(
            " ".join(["git", "diff", "HEAD", "--compact-summary"]),
            cwd=folder,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        diff_not_empty = await diff_not_empty.stdout.read()
        diff_not_empty = diff_not_empty.decode().strip()
        if not diff_not_empty:
            print("nothing to do")
            return

        await git(
            [
                "commit",
                "-a",
                "-m",
                "Auto-update README",
                "--author='yunohost-bot <yunohost@yunohost.org>'",
            ],
            in_folder=folder,
        )
        await git(["push", "origin", branch, "--quiet"], in_folder=folder)

        print(f"Updated https://github.com/{repository}")


if __name__ == '__main__':
    apps = json.load(open("../../builds/default/v3/apps.json"))["apps"]

    for app, infos in apps.items():
        if "github.com" not in infos["git"]["url"]:
            continue

        time.sleep(2)
        asyncio.run(
            regen_readme(
                infos["git"]["url"].replace("https://github.com/", ""),
                infos["git"]["branch"],
            )
        )