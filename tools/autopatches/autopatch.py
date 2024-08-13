#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
import toml

# add apps/tools to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from appslib.utils import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    get_catalog,
)

TOOLS_DIR = Path(__file__).resolve().parent.parent

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"
os.makedirs(".apps_cache", exist_ok=True)

login = (
    (TOOLS_DIR / ".github_login").open("r", encoding="utf-8").read().strip()
)
token = (
    (TOOLS_DIR / ".github_token").open("r", encoding="utf-8").read().strip()
)
github_api = "https://api.github.com"


def apps(min_level=4):
    for app, infos in get_catalog().items():
        if infos.get("state") == "working" and infos.get("level", -1) > min_level:
            infos["id"] = app
            yield infos


def app_cache_folder(app):
    return os.path.join(".apps_cache", app)


def git(cmd, in_folder=None):
    if not isinstance(cmd, list):
        cmd = cmd.split()
    if in_folder:
        cmd = ["-C", in_folder] + cmd
    cmd = ["git"] + cmd
    return subprocess.check_output(cmd, env=my_env).strip().decode("utf-8")


# Progress bar helper, stolen from https://stackoverflow.com/a/34482761
def progressbar(it, prefix="", size=60, file=sys.stdout):
    it = list(it)
    count = len(it)

    def show(j, name=""):
        name += "          "
        x = int(size * j / count)
        file.write(
            "%s[%s%s] %i/%i %s\r" % (prefix, "#" * x, "." * (size - x), j, count, name)
        )
        file.flush()

    show(0)
    for i, item in enumerate(it):
        yield item
        show(i + 1, item["id"])
    file.write("\n")
    file.flush()


def build_cache():
    for app in progressbar(apps(), "Git cloning: ", 40):
        folder = os.path.join(".apps_cache", app["id"])
        reponame = app["url"].rsplit("/", 1)[-1]
        git(f"clone --quiet --depth 1 --single-branch {app['url']} {folder}")
        git(
            f"remote add fork https://{login}:{token}@github.com/{login}/{reponame}",
            in_folder=folder,
        )


def apply(patch):
    patch_path = os.path.abspath(os.path.join("patches", patch, "patch.sh"))

    for app in progressbar(apps(), "Apply to: ", 40):
        folder = os.path.join(".apps_cache", app["id"])
        current_branch = git(f"symbolic-ref --short HEAD", in_folder=folder)
        git(f"reset --hard origin/{current_branch}", in_folder=folder)
        os.system(f"cd {folder} && bash {patch_path}")


def diff():
    for app in apps():
        folder = os.path.join(".apps_cache", app["id"])
        if bool(
            subprocess.check_output(f"cd {folder} && git diff", shell=True)
            .strip()
            .decode("utf-8")
        ):
            print("\n\n\n")
            print("=================================")
            print("Changes in : " + app["id"])
            print("=================================")
            print("\n")
            os.system(f"cd {folder} && git --no-pager diff")


def push(patch):
    title = (
        "[autopatch] "
        + open(os.path.join("patches", patch, "pr_title.md")).read().strip()
    )

    def diff_not_empty(app):
        folder = os.path.join(".apps_cache", app["id"])
        return bool(
            subprocess.check_output(f"cd {folder} && git diff", shell=True)
            .strip()
            .decode("utf-8")
        )

    def app_is_on_github(app):
        return "github.com" in app["url"]

    apps_to_push = [
        app for app in apps() if diff_not_empty(app) and app_is_on_github(app)
    ]

    with requests.Session() as s:
        s.headers.update({"Authorization": f"token {token}"})
        for app in progressbar(apps_to_push, "Forking: ", 40):
            app["repo"] = app["url"][len("https://github.com/") :].strip("/")
            fork_if_needed(app["repo"], s)
            time.sleep(2)  # to avoid rate limiting lol

        for app in progressbar(apps_to_push, "Pushing: ", 40):
            app["repo"] = app["url"][len("https://github.com/") :].strip("/")
            app_repo_name = app["url"].rsplit("/", 1)[-1]
            folder = os.path.join(".apps_cache", app["id"])
            current_branch = git(f"symbolic-ref --short HEAD", in_folder=folder)
            git(f"reset origin/{current_branch}", in_folder=folder)
            git(
                ["commit", "-a", "-m", title, "--author='Yunohost-Bot <>'"],
                in_folder=folder,
            )
            try:
                git(f"remote remove fork", in_folder=folder)
            except Exception:
                pass
            git(
                f"remote add fork https://{login}:{token}@github.com/{login}/{app_repo_name}",
                in_folder=folder,
            )
            git(f"push fork {current_branch}:{patch} --quiet --force", in_folder=folder)
            create_pull_request(app["repo"], patch, current_branch, s)
            time.sleep(4)  # to avoid rate limiting lol


def fork_if_needed(repo, s):
    repo_name = repo.split("/")[-1]
    r = s.get(github_api + f"/repos/{login}/{repo_name}")

    if r.status_code == 200:
        return

    r = s.post(github_api + f"/repos/{repo}/forks")

    if r.status_code != 200:
        print(r.text)


def create_pull_request(repo, patch, base_branch, s):
    PR = {
        "title": "[autopatch] "
        + open(os.path.join("patches", patch, "pr_title.md")).read().strip(),
        "body": "This is an automatic PR\n\n"
        + open(os.path.join("patches", patch, "pr_body.md")).read().strip(),
        "head": login + ":" + patch,
        "base": base_branch,
        "maintainer_can_modify": True,
    }

    r = s.post(github_api + f"/repos/{repo}/pulls", json.dumps(PR))

    if r.status_code != 200:
        print(r.text)
    else:
        json.loads(r.text)["html_url"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("the_patch", type=str, nargs="?", help="The name of the patch to apply")
    parser.add_argument("--cache", "-b", action="store_true", help="Init local git clone for all apps")
    parser.add_argument("--apply", "-a", action="store_true", help="Apply patch on all local clones")
    parser.add_argument("--diff", "-d", action="store_true", help="Inspect diff for all apps")
    parser.add_argument("--push", "-p", action="store_true", help="Push and create pull requests on all apps with non-empty diff")
    args = parser.parse_args()

    if not (args.cache or args.apply or args.diff or args.push):
        parser.error("We required --cache, --apply, --diff or --push.")

    if args.cache:
        build_cache()

    if args.apply:
        if not args.the_patch:
            parser.error("--apply requires the patch name to be passed")
        apply(args.the_patch)

    if args.diff:
        diff()

    if args.push:
        if not args.the_patch:
            parser.error("--push requires the patch name to be passed")
        push(args.the_patch)

main()
