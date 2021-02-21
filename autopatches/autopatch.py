#!/usr/bin/python3
import json
import sys
import requests
import os
import subprocess

catalog = requests.get("https://raw.githubusercontent.com/YunoHost/apps/master/apps.json").json()

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"
os.makedirs(".apps_cache", exist_ok=True)

login = open("login").read().strip()
token = open("token").read().strip()
github_api = "https://api.github.com"


def apps(min_level=4):

    for app, infos in catalog.items():
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
        x = int(size*j/count)
        file.write("%s[%s%s] %i/%i %s\r" % (prefix, "#"*x, "."*(size-x), j,  count, name))
        file.flush()
    show(0)
    for i, item in enumerate(it):
        yield item
        show(i+1, item["id"])
    file.write("\n")
    file.flush()


def build_cache():

    for app in progressbar(apps(), "Git cloning: ", 40):
        folder = os.path.join(".apps_cache", app["id"])
        reponame = app["url"].rsplit("/", 1)[-1]
        git(f"clone --quiet --depth 1 --single-branch {app['url']} {folder}")
        git(f"remote add fork https://{login}:{token}@github.com/{login}/{reponame}", in_folder=folder)


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
        if bool(subprocess.check_output(f"cd {folder} && git diff", shell=True).strip().decode("utf-8")):
            print("\n\n\n")
            print("=================================")
            print("Changes in : " + app["id"])
            print("=================================")
            print("\n")
            os.system(f"cd {folder} && git --no-pager diff")


def push(patch):

    title = "[autopatch] " + open(os.path.join("patches", patch, "pr_title.md")).read().strip()

    def diff_not_empty(app):
        folder = os.path.join(".apps_cache", app["id"])
        return bool(subprocess.check_output(f"cd {folder} && git diff", shell=True).strip().decode("utf-8"))

    def app_is_on_github(app):
        return "github.com" in app["url"]

    apps_to_push = [app for app in apps() if diff_not_empty(app) and app_is_on_github(app)]

    with requests.Session() as s:
        s.headers.update({"Authorization": f"token {token}"})
        for app in progressbar(apps_to_push, "Forking: ", 40):
            app["repo"] = app["url"][len("https://github.com/"):].strip("/")
            fork_if_needed(app["repo"], s)

        for app in progressbar(apps_to_push, "Pushing: ", 40):
            app["repo"] = app["url"][len("https://github.com/"):].strip("/")
            app_repo_name = app["url"].rsplit("/", 1)[-1]
            folder = os.path.join(".apps_cache", app["id"])
            current_branch = git(f"symbolic-ref --short HEAD", in_folder=folder)
            git(f"reset origin/{current_branch}", in_folder=folder)
            git(["commit", "-a", "-m", title, "--author='Yunohost-Bot <>'"], in_folder=folder)
            try:
                git(f"remote remove fork", in_folder=folder)
            except Exception:
                pass
            git(f"remote add fork https://{login}:{token}@github.com/{login}/{app_repo_name}", in_folder=folder)
            git(f"push fork {current_branch}:{patch} --quiet --force", in_folder=folder)
            create_pull_request(app["repo"], patch, current_branch, s)


def fork_if_needed(repo, s):

    repo_name = repo.split("/")[-1]
    r = s.get(github_api + f"/repos/{login}/{repo_name}")

    if r.status_code == 200:
        return

    r = s.post(github_api + f"/repos/{repo}/forks")

    if r.status_code != 200:
        print(r.text)


def create_pull_request(repo, patch, base_branch, s):

    PR = {"title": "[autopatch] " + open(os.path.join("patches", patch, "pr_title.md")).read().strip(),
          "body": "This is an automatic PR\n\n" + open(os.path.join("patches", patch, "pr_body.md")).read().strip(),
          "head": login + ":" + patch,
          "base": base_branch,
          "maintainer_can_modify": True}

    r = s.post(github_api + f"/repos/{repo}/pulls", json.dumps(PR))

    if r.status_code != 200:
        print(r.text)
    else:
        json.loads(r.text)["html_url"]


def main():

    action = sys.argv[1]
    if action == "--help":
        print("""
    Example usage:

# Init local git clone for all apps
./autopatch --build-cache

# Apply patch in all local clones
./autopatch --apply explicit-php-version-in-deps

# Inspect diff for all apps
./autopatch --diff

# Push and create pull requests on all apps with non-empty diff
./autopatch --push explicit-php-version-in-deps
""")

    elif action == "--build-cache":
        build_cache()
    elif action == "--apply":
        apply(sys.argv[2])
    elif action == "--diff":
        diff()
    elif action == "--push":
        push(sys.argv[2])
    else:
        print("Unknown action %s" % action)


main()
